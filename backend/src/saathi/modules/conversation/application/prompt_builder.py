"""Builds the system prompt in fixed layers. The platform rules always come first and the
tenant's text can never close or escape its own section.

    1. platform_rules_v1.md            fixed, not tenant-editable
    2. <tenant_instructions>           persona, brand rules, custom instructions, banned topics
    3. language instruction
    4. <context>                       retrieved document chunks (untrusted data)
"""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=4)
def load_platform_rules(version: str = "v1") -> str:
    text = (PROMPTS_DIR / f"platform_rules_{version}.md").read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("<!--")).strip()


def _neutralise(text: str) -> str:
    """Tenant/document text cannot open or close tags (prompt-injection hardening)."""
    # Look-alike angle quotes keep the text readable but can never form a tag.
    return text.replace("<", "\u2039").replace(">", "\u203a").strip()


@dataclass(frozen=True, slots=True)
class TenantPromptParts:
    bot_name: str
    business_name: str
    persona: str = ""
    brand_rules: str = ""
    custom_instructions: str = ""
    banned_topics: tuple[str, ...] = field(default_factory=tuple)


def build_system_prompt(parts: TenantPromptParts, *, language: str, context: str) -> str:
    tenant_lines = [
        f"Assistant name: {_neutralise(parts.bot_name)}",
        f"Business: {_neutralise(parts.business_name)}",
    ]
    if parts.persona:
        tenant_lines.append(f"Persona and tone: {_neutralise(parts.persona)}")
    if parts.brand_rules:
        tenant_lines.append(f"Brand rules: {_neutralise(parts.brand_rules)}")
    if parts.custom_instructions:
        tenant_lines.append(f"Additional instructions: {_neutralise(parts.custom_instructions)}")
    if parts.banned_topics:
        topics = ", ".join(_neutralise(t) for t in parts.banned_topics)
        tenant_lines.append(f"Never discuss: {topics}")

    return "\n\n".join(
        [
            load_platform_rules(),
            "<tenant_instructions>\n" + "\n".join(tenant_lines) + "\n</tenant_instructions>",
            f"Reply language: {_neutralise(language)}",
            "<context>\n" + _neutralise(context) + "\n</context>",
        ]
    )
