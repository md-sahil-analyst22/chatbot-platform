# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Builds the instructions ('system prompt') sent to the AI model - the ONLY place that
#       does (R9).
# Order: 1) our fixed platform rules, 2) the tenant's text inside <tenant_instructions>, 3)
#        reply language, 4) document text inside <context>.
# Security: '<' and '>' in tenant or document text are replaced by look-alikes, so nobody can
#           close a section and inject new instructions.
# ─────────────────────────────────────────────────────────────────────────────────────────────
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

# Folder with the platform rules files (prompts/platform_rules_v1.md).
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=4)
# Read the rules file once (cached), dropping <!-- comment --> lines.
def load_platform_rules(version: str = "v1") -> str:
    text = (PROMPTS_DIR / f"platform_rules_{version}.md").read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("<!--")).strip()


# 🔒 Replace < and > so text can never form a tag.
def _neutralise(text: str) -> str:
    """Tenant/document text cannot open or close tags (prompt-injection hardening)."""
    # Look-alike angle quotes keep the text readable but can never form a tag.
    return text.replace("<", "\u2039").replace(">", "\u203a").strip()


@dataclass(frozen=True, slots=True)
# The pieces of tenant text that go into the prompt.
class TenantPromptParts:
    bot_name: str
    business_name: str
    persona: str = ""
    brand_rules: str = ""
    custom_instructions: str = ""
    banned_topics: tuple[str, ...] = field(default_factory=tuple)


# Assemble the four layers in the fixed order.
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

    # Platform rules ALWAYS come first, so tenant text can't override them.
    return "\n\n".join(
        [
            load_platform_rules(),
            "<tenant_instructions>\n" + "\n".join(tenant_lines) + "\n</tenant_instructions>",
            f"Reply language: {_neutralise(language)}",
            "<context>\n" + _neutralise(context) + "\n</context>",
        ]
    )
