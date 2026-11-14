"""Supabase Storage adapter (implements ObjectStore). Settings: SUPABASE_*.

Two buckets: a PRIVATE one for raw uploads (documents) and a PUBLIC one for assets that the
widget shows anonymously (logos). The service-role key bypasses Storage RLS, so it is used only
here, on the server, and never sent to a browser (R17). Tenant separation is enforced by the
mandatory "t/{tenant_id}/..." key prefix, validated on every call.
"""

import re
from typing import Literal

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from saathi.platform.errors import (
    ConfigurationError,
    NotFoundError,
    ProviderError,
    ProviderTimeoutError,
    ValidationError,
)
from saathi.platform.storage import object_store_registry

Visibility = Literal["private", "public"]

# "t/<tenant>/<more segments>": safe characters only. A segment can't start with ".", so
# "." and ".." (path traversal) and empty segments never match.
_SEGMENT = r"[A-Za-z0-9_\-][A-Za-z0-9_.\-]{0,199}"
_KEY = re.compile(rf"t/{_SEGMENT}(/{_SEGMENT})+")


class SupabaseStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUPABASE_", env_file=".env", extra="ignore")

    url: str | None = None
    service_role_key: SecretStr | None = None
    storage_private_bucket: str = "documents"
    storage_public_bucket: str = "public-assets"
    storage_timeout_seconds: float = 30.0


def _check_key(key: str) -> str:
    if not _KEY.fullmatch(key):
        raise ValidationError("invalid storage key")
    return key


class SupabaseObjectStore:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        project_url: str,
        service_role_key: str,
        bucket: str,
        public: bool,
        timeout_s: float = 30.0,
    ) -> None:
        self._http = http
        self._base = f"{project_url.rstrip('/')}/storage/v1/object"
        self._bucket = bucket
        self._public = public
        self._headers = {"Authorization": f"Bearer {service_role_key}", "apikey": service_role_key}
        self._timeout = timeout_s

    def _url(self, key: str) -> str:
        return f"{self._base}/{self._bucket}/{_check_key(key)}"

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        url = self._url(key)
        try:
            r = await self._http.post(
                url,
                headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"},
                content=data,
                timeout=self._timeout,
            )
            r.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("object storage timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("object storage upload failed") from exc

    async def get(self, key: str) -> bytes:
        url = self._url(key)
        try:
            r = await self._http.get(url, headers=self._headers, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("object storage timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("object storage download failed") from exc
        if _is_not_found(r):
            raise NotFoundError("object not found")
        if r.is_error:
            raise ProviderError("object storage download failed")
        return r.content

    async def delete(self, key: str) -> None:
        url = self._url(key)
        try:
            r = await self._http.delete(url, headers=self._headers, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("object storage timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("object storage delete failed") from exc
        if r.is_error and not _is_not_found(r):  # deleting a missing object is a no-op
            raise ProviderError("object storage delete failed")

    def public_url(self, key: str) -> str | None:
        if not self._public:
            return None
        return f"{self._base}/public/{self._bucket}/{_check_key(key)}"


def _is_not_found(r: httpx.Response) -> bool:
    if r.status_code == 404:
        return True
    # Supabase Storage often reports a missing object as 400 with statusCode "404" in the body.
    if r.status_code == 400:
        try:
            return str(r.json().get("statusCode")) == "404"
        except (ValueError, AttributeError):
            return False
    return False


@object_store_registry.register("supabase")
def create_supabase_store(http: httpx.AsyncClient, visibility: Visibility) -> SupabaseObjectStore:
    s = SupabaseStorageSettings()
    key = s.service_role_key.get_secret_value() if s.service_role_key else ""
    if not s.url or not key:  # empty counts as missing: fail closed (R16)
        raise ConfigurationError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    public = visibility == "public"
    return SupabaseObjectStore(
        http,
        project_url=s.url,
        service_role_key=key,
        bucket=s.storage_public_bucket if public else s.storage_private_bucket,
        public=public,
        timeout_s=s.storage_timeout_seconds,
    )
