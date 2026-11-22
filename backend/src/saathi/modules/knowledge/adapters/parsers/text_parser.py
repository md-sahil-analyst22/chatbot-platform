# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Reads plain text (.txt) and Markdown (.md) files (P2.3).
# Markdown '# Heading' lines are kept as they are, so the chunker can cut at them. Plain text is
#   used as-is. The upload check already made sure the file is valid UTF-8.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Plain-text / Markdown parser adapter (P2.3). Standard library only."""

# From saathi.modules.knowledge.adapters — parser registry: parser_registry = document parsers.
from saathi.modules.knowledge.adapters import parser_registry

# From saathi.modules.knowledge.ports.providers — parser contracts: ParsedDocument = a parsed
#   document; ParsedPage = one parsed page.
from saathi.modules.knowledge.ports.providers import ParsedDocument, ParsedPage


# The text reader.
class TextParser:
    # It reads .txt and .md files.
    supported_extensions = frozenset({".txt", ".md"})

    # Text bytes -> one page.
    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        # Decode strictly (upload already checked it; a BOM is dropped).
        text = data.decode("utf-8-sig")
        # One page with the whole text.
        return ParsedDocument(
            pages=[ParsedPage(number=1, text=text)], metadata={"filename": filename}
        )


# Register under the name 'text'.
@parser_registry.register("text")
# The factory the registry calls.
def create_text_parser() -> TextParser:
    # Create the parser (no settings).
    return TextParser()
