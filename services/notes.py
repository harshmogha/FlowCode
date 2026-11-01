"""Notes: optional text (with formulas between $ signs) that any block can carry.
A note becomes a comment in the generated code and a // comment in the algorithm text."""
import re

MAX_NOTE = 1000
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean(note) -> str:
    """The note as safe plain text (empty string when there is none)."""
    if not isinstance(note, str):
        return ""
    text = note.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL.sub("", text).strip()[:MAX_NOTE]


def comment_lines(note) -> list:
    """Lines for a code comment: the $ signs around formulas are dropped."""
    text = clean(note).replace("$", "")
    return [line.rstrip() for line in text.split("\n")] if text else []


def one_line(note) -> str:
    return " ".join(part.strip() for part in comment_lines(note) if part.strip())
