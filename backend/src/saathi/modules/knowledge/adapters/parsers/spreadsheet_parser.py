# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Reads tables: CSV files (standard library) and Excel .xlsx files (openpyxl), P2.3.
# Row-to-text: the first row is the header; every other row becomes one line
#   'Service: GST filing | Fee: ₹1,500 | Time: 3 days', so each row can be found and quoted on
#   its own, with its column names.
# Excel: each sheet is one 'page' with a '# Sheet name' heading. Formulas are read as their last
#   saved values (data_only), never evaluated. Macros (.xlsm) are not accepted at upload.
# Limits: at most 20,000 rows per sheet and 50 sheets (bounded job, R33).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""CSV / XLSX parser adapters (P2.3). XLSX requires the 'ingestion' extra."""

# csv — reads comma-separated files.
import csv

# io — in-memory files.
import io

# From saathi.modules.knowledge.adapters — parser registry: parser_registry = document parsers.
from saathi.modules.knowledge.adapters import parser_registry

# From saathi.modules.knowledge.adapters.parsers.docx_parser — shared table helper:
#   table_rows_to_text = rows -> 'Header: value' lines.
from saathi.modules.knowledge.adapters.parsers.docx_parser import table_rows_to_text

# From saathi.modules.knowledge.ports.providers — parser contracts: ParsedDocument = a parsed
#   document; ParsedPage = one parsed page.
from saathi.modules.knowledge.ports.providers import ParsedDocument, ParsedPage

# At most this many rows per sheet/file.
MAX_ROWS = 20_000
# At most this many sheets per workbook.
MAX_SHEETS = 50
# Longest cell text kept (a giant cell is usually pasted junk).
_MAX_CELL_CHARS = 2000


# Cell value -> clean text.
def _cell(value: object) -> str:
    # Empty cells.
    if value is None:
        # Nothing.
        return ""
    # Everything else as text, trimmed and bounded.
    return str(value).strip()[:_MAX_CELL_CHARS]


# The CSV reader.
class CsvParser:
    # It only reads .csv files.
    supported_extensions = frozenset({".csv"})

    # CSV bytes -> one page of 'Header: value' lines.
    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        # Decode (upload already checked it is UTF-8; a BOM is dropped).
        text = data.decode("utf-8-sig")
        # Guess the delimiter (',' ';' tab '|'); fall back to ',' if unsure.
        try:
            # Look at the start of the file.
            dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(
                text[:4096], delimiters=",;\t|"
            )
        # Couldn't tell.
        except csv.Error:
            # Standard comma-separated.
            dialect = csv.excel
        # The rows, bounded.
        rows: list[list[str]] = []
        # Read row by row...
        for i, row in enumerate(csv.reader(io.StringIO(text), dialect)):
            # ...stop at the limit (+1 for the header).
            if i > MAX_ROWS:
                # Stop.
                break
            # Keep the cleaned cells.
            rows.append([_cell(c) for c in row])
        # One page with a line per row.
        return ParsedDocument(
            pages=[ParsedPage(number=1, text="\n".join(table_rows_to_text(rows)))],
            metadata={"filename": filename, "rows": max(0, len(rows) - 1)},
        )


# The Excel reader.
class XlsxParser:
    # It only reads .xlsx files.
    supported_extensions = frozenset({".xlsx"})

    # XLSX bytes -> one page per sheet.
    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        # openpyxl — reads Excel files.
        import openpyxl  # lazy: only the worker image needs this dependency

        # read_only = streams rows (low memory); data_only = saved values, formulas never run.
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        # The pages.
        pages: list[ParsedPage] = []
        # Always close the workbook (read-only mode keeps the file open).
        try:
            # Each sheet, bounded...
            for number, sheet in enumerate(workbook.worksheets[:MAX_SHEETS], start=1):
                # ...its rows as text, bounded.
                rows: list[list[str]] = []
                # Read row by row...
                for i, row in enumerate(sheet.iter_rows(values_only=True)):
                    # ...stop at the limit (+1 for the header).
                    if i > MAX_ROWS:
                        # Stop.
                        break
                    # Keep the cleaned cells.
                    rows.append([_cell(c) for c in row])
                # Drop fully empty rows (Excel often has blank padding rows).
                rows = [r for r in rows if any(r)]
                # The sheet's lines.
                lines = table_rows_to_text(rows)
                # Skip empty sheets.
                if not lines:
                    # Next sheet.
                    continue
                # One page: '# Sheet name' heading, then the rows.
                pages.append(
                    ParsedPage(number=number, text=f"# {sheet.title}\n\n" + "\n".join(lines))
                )
        # Release the file handle.
        finally:
            # Close it.
            workbook.close()
        # The document.
        return ParsedDocument(pages=pages, metadata={"filename": filename})


# Register the CSV reader under 'csv'.
@parser_registry.register("csv")
# The factory the registry calls.
def create_csv_parser() -> CsvParser:
    # Create the parser (no settings).
    return CsvParser()


# Register the Excel reader under 'xlsx'.
@parser_registry.register("xlsx")
# The factory the registry calls.
def create_xlsx_parser() -> XlsxParser:
    # Create the parser (no settings).
    return XlsxParser()
