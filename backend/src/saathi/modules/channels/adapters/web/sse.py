# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Formats one 'Server-Sent Event', the format used to stream a reply word by word to the
#       widget.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Server-Sent Events formatting for the widget stream."""

# json — reads and writes JSON text.
import json

# From typing — type-hint helpers: Any = any type.
from typing import Any


# Turn an event name + data into the text format browsers understand.
def sse_event(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
