"""Parse structured markdown into editor actions for Benchling's mediocre editor.

The parser converts markdown-like content from Claude into a sequence of
EditorAction objects that BenchlingBrowser can execute via keyboard
interactions and toolbar buttons.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto


class BlockType(Enum):
    HEADER1 = auto()
    HEADER2 = auto()
    SUBHEADER = auto()
    PARAGRAPH = auto()
    BULLET = auto()
    TABLE = auto()
    BLANK = auto()


@dataclass
class TextSegment:
    """A piece of inline text, optionally bold."""

    text: str
    bold: bool = False


@dataclass
class EditorAction:
    """A single block-level action for the Benchling editor."""

    block_type: BlockType
    segments: list[TextSegment] = field(default_factory=list)
    indent_level: int = 0
    table_data: list[list[str]] = field(default_factory=list)


def parse_inline(text: str) -> list[TextSegment]:
    """Split text into segments of bold and non-bold runs."""
    segments: list[TextSegment] = []
    pattern = re.compile(r"\*\*(.+?)\*\*")
    last_end = 0
    for match in pattern.finditer(text):
        if match.start() > last_end:
            segments.append(TextSegment(text=text[last_end : match.start()]))
        segments.append(TextSegment(text=match.group(1), bold=True))
        last_end = match.end()
    if last_end < len(text):
        segments.append(TextSegment(text=text[last_end:]))
    return segments or [TextSegment(text="")]


def _parse_table_block(lines: list[str]) -> list[list[str]]:
    """Parse pipe-delimited markdown table lines into a 2D list of strings."""
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip().strip("|")
        if re.match(r"^[\s\-:|]+$", stripped):
            continue
        cells = [c.strip() for c in stripped.split("|")]
        rows.append(cells)
    return rows


def parse_content(text: str) -> list[EditorAction]:
    """Convert markdown text to a list of editor actions."""
    lines = text.split("\n")
    actions: list[EditorAction] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            actions.append(EditorAction(block_type=BlockType.BLANK))
            i += 1
            continue

        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            table_data = _parse_table_block(table_lines)
            if table_data:
                actions.append(
                    EditorAction(block_type=BlockType.TABLE, table_data=table_data)
                )
            continue

        if line.startswith("### "):
            segments = parse_inline(line[4:].strip())
            actions.append(
                EditorAction(block_type=BlockType.SUBHEADER, segments=segments)
            )
            i += 1
            continue

        if line.startswith("## "):
            segments = parse_inline(line[3:].strip())
            actions.append(
                EditorAction(block_type=BlockType.HEADER2, segments=segments)
            )
            i += 1
            continue

        if line.startswith("# "):
            segments = parse_inline(line[2:].strip())
            actions.append(
                EditorAction(block_type=BlockType.HEADER1, segments=segments)
            )
            i += 1
            continue

        bullet_match = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if bullet_match:
            indent_str, content = bullet_match.groups()
            indent_level = len(indent_str) // 2
            segments = parse_inline(content)
            actions.append(
                EditorAction(
                    block_type=BlockType.BULLET,
                    segments=segments,
                    indent_level=indent_level,
                )
            )
            i += 1
            continue

        segments = parse_inline(line.strip())
        actions.append(EditorAction(block_type=BlockType.PARAGRAPH, segments=segments))
        i += 1

    return actions
