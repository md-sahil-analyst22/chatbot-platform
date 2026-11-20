# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: File storage on Supabase: a private bucket for documents and a public bucket for logos.
# Security: 🔒 Uses the server-only secret key. Every file path must start with t/<tenant>/ and
#           can't climb out with '..'.
# Used by: Phase 2 (document uploads) and Phase 4 (logos).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Supabase Storage adapter (implements ObjectStore). Settings: SUPABASE_*.

Two buckets: a PRIVATE one for raw uploads (documents) and a PUBLIC one for assets that the
widget shows anonymously (logos). The service-role key bypasses Storage RLS, so it is used only
here, on the server, and never sent to a browser (R17). Tenant separation is enforced by the
mandatory "t/{tenant_id}/..." key prefix, validated on every call.
"""

# re — regular expressions (text patterns).
import re

# From typing — type-hint helpers: Literal = only these exact values.
from typing import Literal

# httpx — the HTTP client we use to call other web services.
import httpx

# From pydantic — checks data against declared types and rules: SecretStr = text that hides
#   itself when printed or logged.
from pydantic import SecretStr

# From pydantic_settings — reads settings from environment variables and .env: BaseSettings =
#   parent class for a group of settings; SettingsConfigDict = where settings are read from (.env,
#   prefix).
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   NotFoundError = 404 not found; ProviderError = a vendor failed; ProviderTimeoutError = a
#   vendor was too slow; ValidationError = 422 invalid input.
from saathi.platform.errors import (
    ConfigurationError,
    NotFoundError,
    ProviderError,
    ProviderTimeoutError,
    ValidationError,
)

# From saathi.platform.storage — file storage contract and registry: object_store_registry =
#   file storage vendors.
from saathi.platform.storage import object_store_registry

# The two kinds of bucket.
Visibility = Literal["private", "public"]

# "t/<tenant>/<more segments>": safe characters only. A segment can't start with ".", so
# "." and ".." (path traversal) and empty segments never match.
_SEGMENT = r"[A-Za-z0-9_\-][A-Za-z0-9_.\-]{0,199}"
# Allowed file paths: t/<tenant>/<more parts>, safe characters only.
_KEY = re.compile(rf"t/{_SEGMENT}(/{_SEGMENT})+")


# Supabase address, secret key and bucket names from .env (SUPABASE_*).
class SupabaseStorageSettings(BaseSettings):
    # Read SUPABASE_* variables from .env (e.g. SUPABASE_URL) and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="SUPABASE_", env_file=".env", extra="ignore")

    # SUPABASE_URL: the project's address.
    url: str | None = None
    # 🔒 SUPABASE_SERVICE_ROLE_KEY: the server-only secret key (hidden when printed).
    service_role_key: SecretStr | None = None
    # Bucket for private uploads (documents).
    storage_private_bucket: str = "documents"
    # Bucket for public files (logos).
    storage_public_bucket: str = "public-assets"
    # Give up on a storage call after 30 seconds.
    storage_timeout_seconds: float = 30.0


# 🔒 Refuse any path that doesn't match the safe pattern.
def _check_key(key: str) -> str:
    # The whole path must match the safe pattern...
    if not _KEY.fullmatch(key):
        # ...otherwise refuse it.
        raise ValidationError("invalid storage key")
    # Safe: return it unchanged.
    return key


# Talks to Supabase Storage's web API.
class SupabaseObjectStore:
    # Created by create_supabase_store() below with:
    def __init__(
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        *,
        project_url: str,
        # the secret key,
        service_role_key: str,
        # the bucket name,
        bucket: str,
        # whether the bucket is public,
        public: bool,
        # and the time limit per call.
        timeout_s: float = 30.0,
    ) -> None:
        # Remember the HTTP client.
        self._http = http
        # The Storage API's base address, e.g.
        #   https://<project>.supabase.co/storage/v1/object.
        self._base = f"{project_url.rstrip('/')}/storage/v1/object"
        # Remember the bucket.
        self._bucket = bucket
        # Remember whether it's public.
        self._public = public
        # 🔒 Headers that prove we're the server (secret key); only ever sent to Supabase.
        self._headers = {"Authorization": f"Bearer {service_role_key}", "apikey": service_role_key}
        # Remember the time limit.
        self._timeout = timeout_s

    # Build the full address of a file (after checking its path).
    def _url(self, key: str) -> str:
        # <base>/<bucket>/<checked path>.
        return f"{self._base}/{self._bucket}/{_check_key(key)}"

    # Upload (or overwrite) a file.
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        # Build (and check) the file's address.
        url = self._url(key)
        # Try the upload:
        try:
            # POST the bytes...
            r = await self._http.post(
                # to that address,
                url,
                # with our headers, the file type, and 'x-upsert' = overwrite if it exists,
                headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"},
                # the file's bytes,
                content=data,
                # within the time limit.
                timeout=self._timeout,
            )
            # An error status counts as a failure.
            r.raise_for_status()
        # Too slow:
        except httpx.TimeoutException as exc:
            # 504-style 'timed out' error.
            raise ProviderTimeoutError("object storage timed out") from exc
        # Any other network/HTTP problem:
        except httpx.HTTPError as exc:
            # 502-style 'upload failed' error.
            raise ProviderError("object storage upload failed") from exc

    # Download a file; missing -> NotFoundError.
    async def get(self, key: str) -> bytes:
        # Build (and check) the address.
        url = self._url(key)
        # Try the download:
        try:
            # GET the file.
            r = await self._http.get(url, headers=self._headers, timeout=self._timeout)
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("object storage timed out") from exc
        # Network problem:
        except httpx.HTTPError as exc:
            # download-failed error.
            raise ProviderError("object storage download failed") from exc
        # Supabase says it doesn't exist:
        if _is_not_found(r):
            # 404 not found.
            raise NotFoundError("object not found")
        # Any other error status:
        if r.is_error:
            # download failed.
            raise ProviderError("object storage download failed")
        # Success: return the bytes.
        return r.content

    # Delete a file; deleting a missing file is fine.
    async def delete(self, key: str) -> None:
        # Build (and check) the address.
        url = self._url(key)
        # Try the delete:
        try:
            # DELETE the file.
            r = await self._http.delete(url, headers=self._headers, timeout=self._timeout)
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("object storage timed out") from exc
        # Network problem:
        except httpx.HTTPError as exc:
            # delete-failed error.
            raise ProviderError("object storage delete failed") from exc
        if r.is_error and not _is_not_found(r):  # deleting a missing object is a no-op
            # Any other error status -> delete failed.
            raise ProviderError("object storage delete failed")

    # Public address for logos; private documents have none.
    def public_url(self, key: str) -> str | None:
        # A private bucket...
        if not self._public:
            # ...has no public address.
            return None
        # Public files live at <base>/public/<bucket>/<path>.
        return f"{self._base}/public/{self._bucket}/{_check_key(key)}"


# Supabase reports 'not found' in two ways; recognise both.
def _is_not_found(r: httpx.Response) -> bool:
    # Plain 404:
    if r.status_code == 404:
        # not found.
        return True
    # Supabase Storage often reports a missing object as 400 with statusCode "404" in the body.
    if r.status_code == 400:
        # Try to read the JSON body...
        try:
            # ...and check whether it says statusCode 404.
            return str(r.json().get("statusCode")) == "404"
        # Body isn't the JSON we expected:
        except (ValueError, AttributeError):
            # then it's not a 'not found'.
            return False
    # Any other status: not a 'not found'.
    return False


# Register this factory under the name 'supabase' (STORAGE_PROVIDER=supabase).
@object_store_registry.register("supabase")
# Registry factory: refuses to start without the URL and secret key.
def create_supabase_store(http: httpx.AsyncClient, visibility: Visibility) -> SupabaseObjectStore:
    # Read the SUPABASE_* settings.
    s = SupabaseStorageSettings()
    # The secret key as plain text (empty if missing).
    key = s.service_role_key.get_secret_value() if s.service_role_key else ""
    if not s.url or not key:  # empty counts as missing: fail closed (R16)
        # Refuse to start without them.
        raise ConfigurationError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    # Which bucket was asked for.
    public = visibility == "public"
    # Build the store with:
    return SupabaseObjectStore(
        # the HTTP client,
        http,
        # the project address,
        project_url=s.url,
        # the secret key,
        service_role_key=key,
        # the public or the private bucket,
        bucket=s.storage_public_bucket if public else s.storage_private_bucket,
        # whether it's public,
        public=public,
        # and the configured time limit.
        timeout_s=s.storage_timeout_seconds,
    )
