#!/usr/bin/env python3
"""Convert cognitive_substrate.usda to CLAUDE.md.

Self-contained converter with no dependencies beyond stdlib.
Adapted from Orchestra's retriever.py (regex parsing) and usda_writer.py (string escaping).

Usage:
    python usda_to_claude_md.py              # Generate CLAUDE.md
    python usda_to_claude_md.py --dry-run    # Print to stdout
    python usda_to_claude_md.py --verify     # Diff against current
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# USDA Parser
# ---------------------------------------------------------------------------

@dataclass
class Prim:
    """A USD prim with attributes and children."""
    name: str
    kind: str = ""
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class USDAParser:
    """Regex-based USDA parser. Extracts prim hierarchy and typed attributes."""

    # Match a prim definition: def "Name" ( metadata ) { body }
    # or: def "Name" { body }
    _PRIM_RE = re.compile(
        r'def\s+"([^"]+)"\s*'       # def "Name"
        r'(?:\(([^)]*)\)\s*)?'       # optional ( metadata )
        r'\{',                        # opening brace
        re.DOTALL,
    )

    # Attribute patterns
    _STRING_ATTR = re.compile(
        r'custom\s+string\s+(\w+)\s*=\s*'
        r'(?:"""(.*?)"""|"([^"]*)")',
        re.DOTALL,
    )
    _STRING_ARRAY_ATTR = re.compile(
        r'custom\s+string\[\]\s+(\w+)\s*=\s*\[(.*?)\]',
        re.DOTALL,
    )
    _INT_ATTR = re.compile(
        r'custom\s+int\s+(\w+)\s*=\s*(-?\d+)',
    )
    _KIND_RE = re.compile(r'kind\s*=\s*"([^"]*)"')

    def parse(self, text: str) -> Prim:
        """Parse USDA text and return the root prim."""
        # Strip the file header
        header_end = text.find('def "')
        if header_end == -1:
            raise ValueError("No prim definitions found")
        body = text[header_end:]
        prims = self._parse_prims(body)
        if not prims:
            raise ValueError("Failed to parse root prim")
        return prims[0]

    def _parse_prims(self, text: str) -> list:
        """Recursively parse all prims at the current nesting level."""
        prims = []
        pos = 0
        while pos < len(text):
            m = self._PRIM_RE.search(text, pos)
            if not m:
                break

            name = m.group(1)
            metadata = m.group(2) or ""
            brace_start = m.end()

            # Find matching closing brace
            body_end = self._find_matching_brace(text, brace_start - 1)
            if body_end == -1:
                break

            body = text[brace_start:body_end]

            prim = Prim(name=name)

            # Extract kind from metadata
            kind_m = self._KIND_RE.search(metadata)
            if kind_m:
                prim.kind = kind_m.group(1)

            # Extract attributes from body
            prim.attrs = self._parse_attrs(body)

            # Extract child prims
            prim.children = self._parse_prims(body)

            prims.append(prim)
            pos = body_end + 1

        return prims

    def _find_matching_brace(self, text: str, open_pos: int) -> int:
        """Find the closing brace matching the one at open_pos."""
        depth = 0
        i = open_pos
        in_string = False
        in_triple = False
        while i < len(text):
            c = text[i]

            # Handle triple-quoted strings
            if not in_string and text[i:i+3] == '"""':
                in_triple = not in_triple
                i += 3
                continue
            if in_triple:
                i += 1
                continue

            # Handle single-quoted strings
            if c == '"' and not in_string:
                in_string = True
                i += 1
                continue
            if c == '"' and in_string:
                # Check for escaped quote
                backslashes = 0
                j = i - 1
                while j >= 0 and text[j] == '\\':
                    backslashes += 1
                    j -= 1
                if backslashes % 2 == 0:
                    in_string = False
                i += 1
                continue
            if in_string:
                i += 1
                continue

            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    def _parse_attrs(self, body: str) -> dict:
        """Extract all custom attributes from a prim body."""
        attrs = {}

        # Strip child prim definitions to avoid matching their attributes
        clean = self._strip_child_prims(body)

        # String arrays (must be before single strings to avoid partial matches)
        for m in self._STRING_ARRAY_ATTR.finditer(clean):
            key = m.group(1)
            raw = m.group(2)
            items = self._parse_string_array(raw)
            attrs[key] = items

        # Single strings (skip keys already captured as arrays)
        for m in self._STRING_ATTR.finditer(clean):
            key = m.group(1)
            if key in attrs:
                continue
            # group(2) is triple-quoted, group(3) is single-quoted
            value = m.group(2) if m.group(2) is not None else m.group(3)
            attrs[key] = self._unescape_string(value)

        # Integers
        for m in self._INT_ATTR.finditer(clean):
            key = m.group(1)
            attrs[key] = int(m.group(2))

        return attrs

    def _strip_child_prims(self, body: str) -> str:
        """Remove child prim blocks so we only parse this prim's own attributes."""
        result = []
        pos = 0
        for m in self._PRIM_RE.finditer(body):
            result.append(body[pos:m.start()])
            brace_start = m.end() - 1
            brace_end = self._find_matching_brace(body, brace_start)
            if brace_end != -1:
                pos = brace_end + 1
            else:
                pos = m.end()
        result.append(body[pos:])
        return ''.join(result)

    def _parse_string_array(self, raw: str) -> list:
        """Parse items from a USDA string array body (content between [ and ])."""
        items = []
        # Match each quoted string, handling escaped quotes
        i = 0
        while i < len(raw):
            # Find opening quote
            q = raw.find('"', i)
            if q == -1:
                break
            # Find closing quote (not escaped)
            j = q + 1
            while j < len(raw):
                if raw[j] == '"':
                    backslashes = 0
                    k = j - 1
                    while k > q and raw[k] == '\\':
                        backslashes += 1
                        k -= 1
                    if backslashes % 2 == 0:
                        break
                j += 1
            if j < len(raw):
                items.append(self._unescape_string(raw[q+1:j]))
                i = j + 1
            else:
                break
        return items

    @staticmethod
    def _unescape_string(s: str) -> str:
        """Reverse USDA string escaping."""
        s = s.replace('\\"', '"')
        s = s.replace('\\\\', '\\')
        return s


# ---------------------------------------------------------------------------
# Markdown Renderer
# ---------------------------------------------------------------------------

class MarkdownRenderer:
    """Renders a Prim tree to CLAUDE.md markdown."""

    HEADER_COMMENT = "<!-- AUTO-GENERATED from cognitive_substrate.usda -- do not hand-edit -->"

    def render(self, root: Prim) -> str:
        """Render the full markdown document from the root prim."""
        lines = [self.HEADER_COMMENT, ""]

        # Sort children by display_order
        children = sorted(root.children, key=lambda p: p.attrs.get('display_order', 0))

        for child in children:
            section_type = child.attrs.get('section_type', '')

            if section_type == 'metadata':
                lines.append(child.attrs.get('content', ''))
                lines.append("")
            elif child.children:
                # Group prim — renders as ## section with children
                lines.append("---")
                lines.append("")
                self._render_group(child, lines)
            else:
                # Leaf prim at top level
                self._render_leaf(child, lines, heading_level=2)

        # Remove trailing blank lines, ensure single newline at end
        text = '\n'.join(lines)
        text = text.rstrip('\n') + '\n'
        return text

    def _render_group(self, prim: Prim, lines: list):
        """Render a group prim as ## heading with children."""
        title = prim.attrs.get('title', prim.name)
        lines.append(f"## {title}")
        lines.append("")

        description = prim.attrs.get('description', '')
        if description:
            lines.append(description)
            lines.append("")

        children = sorted(prim.children, key=lambda p: p.attrs.get('display_order', 0))
        for child in children:
            self._render_leaf(child, lines, heading_level=3)

    def _render_leaf(self, prim: Prim, lines: list, heading_level: int = 3):
        """Render a leaf prim based on its section_type."""
        section_type = prim.attrs.get('section_type', 'protocol')

        if section_type == 'protocol':
            self._render_protocol(prim, lines, heading_level)
        elif section_type == 'table':
            self._render_table(prim, lines, heading_level)
        elif section_type == 'text':
            self._render_text(prim, lines, heading_level)

    def _render_protocol(self, prim: Prim, lines: list, heading_level: int):
        """Render a protocol prim (heading + description + list items + epilogue)."""
        title = prim.attrs.get('title', prim.name)
        prefix = '#' * heading_level
        lines.append(f"{prefix} {title}")
        lines.append("")

        description = prim.attrs.get('description', '')
        if description:
            lines.append(description)
            lines.append("")

        items = prim.attrs.get('items', [])
        list_type = prim.attrs.get('list_type', 'bullet')

        for i, item in enumerate(items):
            if list_type == 'ordered':
                lines.append(f"{i + 1}. {item}")
            else:
                lines.append(f"- {item}")

        if items:
            lines.append("")

        epilogue = prim.attrs.get('epilogue', '')
        if epilogue:
            lines.append(epilogue)
            lines.append("")

    def _render_table(self, prim: Prim, lines: list, heading_level: int):
        """Render a table prim (heading + markdown table + epilogue)."""
        title = prim.attrs.get('title', prim.name)
        prefix = '#' * heading_level
        lines.append(f"{prefix} {title}")
        lines.append("")

        headers = prim.attrs.get('column_headers', [])
        row_data = prim.attrs.get('row_data', [])
        num_cols = prim.attrs.get('num_columns', len(headers))

        if not headers or not num_cols:
            return

        # Reshape flat row_data into rows
        rows = []
        for i in range(0, len(row_data), num_cols):
            rows.append(row_data[i:i + num_cols])

        # Render header row (compact — no padding)
        lines.append("| " + " | ".join(headers) + " |")

        # Render separator (dashes match header text width + 2 for surrounding spaces)
        sep_cells = ["-" * (len(h) + 2) for h in headers]
        lines.append("|" + "|".join(sep_cells) + "|")

        # Render data rows (compact)
        for row in rows:
            cells = [row[j] if j < len(row) else "" for j in range(num_cols)]
            lines.append("| " + " | ".join(cells) + " |")

        lines.append("")

        epilogue = prim.attrs.get('epilogue', '')
        if epilogue:
            lines.append(epilogue)
            lines.append("")

    def _render_text(self, prim: Prim, lines: list, heading_level: int):
        """Render a text prim (heading + raw content)."""
        title = prim.attrs.get('title', '')
        if title:
            prefix = '#' * heading_level
            lines.append(f"{prefix} {title}")
            lines.append("")

        content = prim.attrs.get('content', '')
        if content:
            lines.append(content)
            lines.append("")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert cognitive_substrate.usda to CLAUDE.md"
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print generated markdown to stdout instead of writing'
    )
    parser.add_argument(
        '--verify', action='store_true',
        help='Compare generated output against current CLAUDE.md'
    )
    parser.add_argument(
        '--usda', type=Path,
        default=Path.home() / '.claude' / 'cognitive_substrate.usda',
        help='Path to USDA source file'
    )
    parser.add_argument(
        '--output', type=Path,
        default=Path.home() / '.claude' / 'CLAUDE.md',
        help='Path to output CLAUDE.md'
    )
    args = parser.parse_args()

    # Parse USDA
    usda_text = args.usda.read_text(encoding='utf-8')
    usda_parser = USDAParser()
    root = usda_parser.parse(usda_text)

    # Render markdown
    renderer = MarkdownRenderer()
    generated = renderer.render(root)

    if args.dry_run:
        sys.stdout.write(generated)
        return

    if args.verify:
        if not args.output.exists():
            print(f"ERROR: {args.output} does not exist", file=sys.stderr)
            sys.exit(1)

        current = args.output.read_text(encoding='utf-8')

        # Strip auto-generated header from both for comparison
        gen_lines = generated.splitlines()
        cur_lines = current.splitlines()

        # Remove header comment if present
        if gen_lines and gen_lines[0].startswith('<!-- AUTO-GENERATED'):
            gen_lines = gen_lines[1:]
            if gen_lines and gen_lines[0] == '':
                gen_lines = gen_lines[1:]

        gen_content = '\n'.join(gen_lines).strip()
        cur_content = '\n'.join(cur_lines).strip()

        if gen_content == cur_content:
            print("OK: Generated output matches current CLAUDE.md")
            return

        # Show diff
        import difflib
        diff = difflib.unified_diff(
            cur_content.splitlines(keepends=True),
            gen_content.splitlines(keepends=True),
            fromfile='current CLAUDE.md',
            tofile='generated',
            lineterm=''
        )
        diff_text = '\n'.join(diff)
        if diff_text:
            print("DIFF: Generated output differs from current CLAUDE.md:")
            print(diff_text)
            sys.exit(1)
        else:
            print("OK: Generated output matches current CLAUDE.md")
        return

    # Write output
    args.output.write_text(generated, encoding='utf-8')
    print(f"Generated {args.output}")


if __name__ == '__main__':
    main()
