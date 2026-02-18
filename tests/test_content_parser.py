"""Tests for the content parser module."""

from __future__ import annotations

from benchling_agent.clients.content_parser import (
    BlockType,
    TextSegment,
    parse_content,
    parse_inline,
)


class TestParseInline:
    def test_plain_text(self):
        segments = parse_inline("hello world")
        assert segments == [TextSegment(text="hello world")]

    def test_bold(self):
        segments = parse_inline("**bold**")
        assert segments == [TextSegment(text="bold", bold=True)]

    def test_mixed(self):
        segments = parse_inline("before **bold** after")
        assert len(segments) == 3
        assert segments[0] == TextSegment(text="before ")
        assert segments[1] == TextSegment(text="bold", bold=True)
        assert segments[2] == TextSegment(text=" after")

    def test_multiple_bold(self):
        segments = parse_inline("**a** and **b**")
        assert len(segments) == 3
        assert segments[0].bold is True
        assert segments[1].bold is False
        assert segments[2].bold is True

    def test_empty(self):
        segments = parse_inline("")
        assert segments == [TextSegment(text="")]


class TestParseContent:
    def test_header1(self):
        actions = parse_content("# Purpose")
        assert len(actions) == 1
        assert actions[0].block_type == BlockType.HEADER1
        assert actions[0].segments[0].text == "Purpose"

    def test_header2(self):
        actions = parse_content("## Materials")
        assert len(actions) == 1
        assert actions[0].block_type == BlockType.HEADER2

    def test_subheader(self):
        actions = parse_content("### Sub Section")
        assert len(actions) == 1
        assert actions[0].block_type == BlockType.SUBHEADER

    def test_paragraph(self):
        actions = parse_content("Regular paragraph text.")
        assert len(actions) == 1
        assert actions[0].block_type == BlockType.PARAGRAPH
        assert actions[0].segments[0].text == "Regular paragraph text."

    def test_bullet_list(self):
        text = "- Item one\n- Item two"
        actions = parse_content(text)
        assert len(actions) == 2
        assert all(a.block_type == BlockType.BULLET for a in actions)
        assert actions[0].indent_level == 0
        assert actions[1].indent_level == 0

    def test_nested_bullets(self):
        text = "- Parent\n  - Child\n    - Grandchild"
        actions = parse_content(text)
        assert len(actions) == 3
        assert actions[0].indent_level == 0
        assert actions[1].indent_level == 1
        assert actions[2].indent_level == 2

    def test_blank_line(self):
        text = "Line one\n\nLine two"
        actions = parse_content(text)
        assert len(actions) == 3
        assert actions[1].block_type == BlockType.BLANK

    def test_table(self):
        text = (
            "| Sample | Conc |\n"
            "|--------|------|\n"
            "| A1     | 50.2 |\n"
            "| A2     | 48.7 |"
        )
        actions = parse_content(text)
        assert len(actions) == 1
        assert actions[0].block_type == BlockType.TABLE
        assert actions[0].table_data == [
            ["Sample", "Conc"],
            ["A1", "50.2"],
            ["A2", "48.7"],
        ]

    def test_bold_in_paragraph(self):
        actions = parse_content("**Purpose:** Evaluate PCR conditions.")
        assert len(actions) == 1
        seg = actions[0].segments
        assert seg[0].text == "Purpose:"
        assert seg[0].bold is True
        assert seg[1].text == " Evaluate PCR conditions."
        assert seg[1].bold is False

    def test_full_document(self):
        text = (
            "# Purpose\n"
            "Evaluate amplification.\n"
            "\n"
            "## Materials\n"
            "- Q5 Polymerase\n"
            "- Primers (10 uM)\n"
            "  - Forward\n"
            "  - Reverse\n"
            "\n"
            "| Sample | Result |\n"
            "|--------|--------|\n"
            "| A1     | Pass   |"
        )
        actions = parse_content(text)
        types = [a.block_type for a in actions]
        assert BlockType.HEADER1 in types
        assert BlockType.HEADER2 in types
        assert BlockType.BULLET in types
        assert BlockType.TABLE in types
        assert BlockType.BLANK in types
        assert BlockType.PARAGRAPH in types

    def test_asterisk_bullets(self):
        actions = parse_content("* Item one\n* Item two")
        assert len(actions) == 2
        assert all(a.block_type == BlockType.BULLET for a in actions)
