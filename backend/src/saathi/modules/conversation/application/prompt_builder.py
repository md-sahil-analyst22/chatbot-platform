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

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; field = per-field options such as a default empty list.
from dataclasses import dataclass, field

# From functools — tools for working with functions: lru_cache = remembers a function's result
#   so the work runs once.
from functools import lru_cache

# From pathlib — file and folder paths: Path = a file or folder path.
from pathlib import Path

# Folder with the platform rules files (prompts/platform_rules_v1.md).
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


# Remember up to 4 loaded rule versions, so the file is read only once.
@lru_cache(maxsize=4)
# Read the rules file once (cached), dropping <!-- comment --> lines.
def load_platform_rules(version: str = "v1") -> str:
    # Read e.g. prompts/platform_rules_v1.md.
    text = (PROMPTS_DIR / f"platform_rules_{version}.md").read_text(encoding="utf-8")
    # Drop lines starting with '<!--' (notes for developers) and trim.
    return "\n".join(line for line in text.splitlines() if not line.startswith("<!--")).strip()


# 🔒 Replace < and > so text can never form a tag.
def _neutralise(text: str) -> str:
    """Tenant/document text cannot open or close tags (prompt-injection hardening)."""
    # Look-alike angle quotes keep the text readable but can never form a tag.
    return text.replace("<", "\u2039").replace(">", "\u203a").strip()


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# The pieces of tenant text that go into the prompt.
class TenantPromptParts:
    # The bot's name.
    bot_name: str
    # The business name.
    business_name: str
    # Personality and tone.
    persona: str = ""
    # Brand rules.
    brand_rules: str = ""
    # Extra instructions.
    custom_instructions: str = ""
    # Topics never to discuss.
    banned_topics: tuple[str, ...] = field(default_factory=tuple)


# Assemble the four layers in the fixed order.
def build_system_prompt(parts: TenantPromptParts, *, language: str, context: str) -> str:
    # The tenant's lines, each neutralised:
    tenant_lines = [
        # the bot's name,
        f"Assistant name: {_neutralise(parts.bot_name)}",
        # the business name.
        f"Business: {_neutralise(parts.business_name)}",
    ]
    # If a persona is set...
    if parts.persona:
        # ...add it.
        tenant_lines.append(f"Persona and tone: {_neutralise(parts.persona)}")
    # If brand rules are set...
    if parts.brand_rules:
        # ...add them.
        tenant_lines.append(f"Brand rules: {_neutralise(parts.brand_rules)}")
    # If extra instructions are set...
    if parts.custom_instructions:
        # ...add them.
        tenant_lines.append(f"Additional instructions: {_neutralise(parts.custom_instructions)}")
    # If there are banned topics...
    if parts.banned_topics:
        # ...join them with commas...
        topics = ", ".join(_neutralise(t) for t in parts.banned_topics)
        # ...and add them.
        tenant_lines.append(f"Never discuss: {topics}")

    # Platform rules ALWAYS come first, so tenant text can't override them.
    return "\n\n".join(
        # The four layers, in this fixed order:
        [
            # 1) our platform rules,
            load_platform_rules(),
            # 2) the tenant's lines inside <tenant_instructions>,
            "<tenant_instructions>\n" + "\n".join(tenant_lines) + "\n</tenant_instructions>",
            # 3) the reply language,
            f"Reply language: {_neutralise(language)}",
            # 4) retrieved document text inside <context>.
            "<context>\n" + _neutralise(context) + "\n</context>",
        ]
    )
