"""USDA Exporter — serialize Cognitive Bridge epistemic state as USD files.

Generates 7 .usda files per project:
- stage.usda          Root stage file with sublayer ordering (LIVRPS)
- session_local.usda  LOCAL assertions (arc=10, strongest)
- domain_inherits.usda   INHERITS assertions (arc=20)
- hypothesis_variants.usda  VARIANT_SET assertions (arc=30)
- evidence_refs.usda  REFERENCES assertions (arc=40)
- deferred_payloads.usda   PAYLOADS assertions (arc=50)
- safety_specializes.usda  SPECIALIZES assertions (arc=60, weakest)

The sublayer ordering in stage.usda places stronger layers first.
USD composition resolves opinions in sublayer order — earlier sublayers
win over later ones. This mechanically matches LIVRPS: LOCAL (first)
overrides SPECIALIZES (last) at the same prim path.

No USD library (pxr) required — files are generated as text.
"""

from pathlib import Path
from typing import Optional

from cognitive_bridge.models.arcs import CompositionArc
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.stage import CompositionStage
from cognitive_bridge.models.variant_set import VariantSet


# Maps arc level to filename and documentation
ARC_FILE_MAP = {
    CompositionArc.LOCAL: ("session_local.usda", "LOCAL assertions (arc=10) — verified, high-confidence"),
    CompositionArc.INHERITS: ("domain_inherits.usda", "INHERITS assertions (arc=20) — domain patterns"),
    CompositionArc.VARIANT_SET: ("hypothesis_variants.usda", "VARIANT_SET assertions (arc=30) — competing hypotheses"),
    CompositionArc.REFERENCES: ("evidence_refs.usda", "REFERENCES assertions (arc=40) — external citations"),
    CompositionArc.PAYLOADS: ("deferred_payloads.usda", "PAYLOADS assertions (arc=50) — known unknowns"),
    CompositionArc.SPECIALIZES: ("safety_specializes.usda", "SPECIALIZES assertions (arc=60) — baseline knowledge"),
}

# LIVRPS sublayer ordering — strongest first
SUBLAYER_ORDER = [
    "session_local.usda",
    "domain_inherits.usda",
    "hypothesis_variants.usda",
    "evidence_refs.usda",
    "deferred_payloads.usda",
    "safety_specializes.usda",
]


def _escape_usda_string(s: str) -> str:
    """Escape a string for USDA attribute values.

    Handles backslashes, double-quotes, and newlines — the three characters
    that would break a USDA string literal if unescaped.
    """
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _build_prim_tree(assertions: list[Assertion]) -> dict:
    """Build a nested dict representing the USD prim hierarchy.

    Each topic_path like /architecture/database/engine becomes:
    {"architecture": {"database": {"engine": {"_assertions": [...]}}}}

    The special key "_assertions" stores the list of Assertion objects at
    that exact path node. Intermediate nodes without assertions have no
    "_assertions" key.
    """
    tree: dict = {}
    for ast in assertions:
        parts = ast.topic_path.strip("/").split("/")
        node = tree
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]
        node.setdefault("_assertions", []).append(ast)
    return tree


def _render_prim_tree(tree: dict, indent: int = 0) -> str:
    """Recursively render a prim tree as USDA text.

    Each prim key becomes a USD Scope prim. If the node has "_assertions",
    the primary assertion's content becomes the prim's doc string and
    its fields are written as custom attributes. Additional assertions at
    the same path are written as child prims named opinion_1, opinion_2, etc.
    """
    lines = []
    pad = "    " * indent

    for key in sorted(tree.keys()):
        if key == "_assertions":
            continue

        subtree = tree[key]
        assertions = subtree.get("_assertions", [])

        if assertions:
            # Strongest assertion is the primary prim; the rest are shadowed
            # opinions. sorted() uses Assertion.__lt__ (arc -> confidence ->
            # recency), so sorted(...)[0] is the composition winner — this keeps
            # the USDA primary prim identical to CompositionStage.resolve(),
            # even when the winner was not inserted first.
            assertions = sorted(assertions)
            ast = assertions[0]  # Primary = composition winner at this path
            lines.append(f'{pad}def Scope "{key}" (')
            lines.append(f'{pad}    doc = "{_escape_usda_string(ast.content)}"')
            lines.append(f'{pad}) {{')

            # Write assertion attributes
            lines.append(f'{pad}    custom string cb:content = "{_escape_usda_string(ast.content)}"')
            lines.append(f'{pad}    custom string cb:assertion_id = "{ast.id}"')
            lines.append(f'{pad}    custom string cb:author = "{ast.author.value}"')
            lines.append(f'{pad}    custom float cb:confidence = {ast.confidence}')
            lines.append(f'{pad}    custom string cb:assumption_status = "{ast.assumption_status.value}"')

            if ast.falsifiable_if:
                lines.append(f'{pad}    custom string cb:falsifiable_if = "{_escape_usda_string(ast.falsifiable_if)}"')

            if ast.depends_on_paths:
                deps = ", ".join(f'"{d}"' for d in ast.depends_on_paths)
                lines.append(f'{pad}    custom string[] cb:depends_on_paths = [{deps}]')

            if ast.evidence:
                evs = ", ".join(f'"{_escape_usda_string(e)}"' for e in ast.evidence)
                lines.append(f'{pad}    custom string[] cb:evidence = [{evs}]')

            # If multiple assertions at same path in same arc, add them as children
            for i, extra_ast in enumerate(assertions[1:], 1):
                lines.append(f'{pad}    def Scope "opinion_{i}" (')
                lines.append(f'{pad}        doc = "{_escape_usda_string(extra_ast.content)}"')
                lines.append(f'{pad}    ) {{')
                lines.append(f'{pad}        custom string cb:content = "{_escape_usda_string(extra_ast.content)}"')
                lines.append(f'{pad}        custom string cb:assertion_id = "{extra_ast.id}"')
                lines.append(f'{pad}    }}')
        else:
            # Intermediate prim (no assertions at this exact path)
            lines.append(f'{pad}def Scope "{key}" {{')

        # Recurse into children
        child_content = _render_prim_tree(subtree, indent + 1)
        if child_content:
            lines.append(child_content)

        lines.append(f'{pad}}}')
        lines.append("")

    return "\n".join(lines)


def generate_arc_layer(
    assertions: list[Assertion],
    arc: CompositionArc,
    doc: str,
) -> str:
    """Generate a single .usda sublayer file for one arc level.

    Args:
        assertions: Active assertions at this arc level
        arc: The CompositionArc value
        doc: Documentation string for the file header

    Returns:
        Complete .usda file content as string
    """
    lines = [
        '#usda 1.0',
        '(',
        f'    doc = "{doc}"',
        ')',
        '',
    ]

    if not assertions:
        lines.append('# No assertions at this arc level.')
        return "\n".join(lines)

    tree = _build_prim_tree(assertions)
    rendered = _render_prim_tree(tree)
    lines.append(rendered)

    return "\n".join(lines)


def generate_variant_layer(
    variant_sets: list[VariantSet],
    assertions: list[Assertion],
) -> str:
    """Generate hypothesis_variants.usda with actual USD VariantSets.

    VARIANT_SET assertions are rendered alongside actual VariantSets
    from the stage's variant_sets collection. Resolved variant sets are
    excluded — only active hypothesis branches appear in the output.
    """
    lines = [
        '#usda 1.0',
        '(',
        '    doc = "VARIANT_SET assertions (arc=30) — competing hypotheses"',
        ')',
        '',
    ]

    if not variant_sets and not assertions:
        lines.append('# No variant sets or variant-arc assertions.')
        return "\n".join(lines)

    # Render VARIANT_SET assertions as prims
    if assertions:
        tree = _build_prim_tree(assertions)
        lines.append(_render_prim_tree(tree))

    # Render actual VariantSets as USD VariantSets
    for vs in variant_sets:
        if vs.resolved:
            continue  # Only export unresolved variant sets

        parts = vs.topic_path.strip("/").split("/")
        # Build nested prim path to the variant set location
        indent = 0
        for part in parts:
            pad = "    " * indent
            lines.append(f'{pad}over Scope "{part}" (')
            if part == parts[-1]:
                # Add variantSets declaration on the leaf prim
                vs_name = vs.name.replace(" ", "_").lower()
                lines.append(f'{pad}    prepend variantSets = ["{vs_name}"]')
            lines.append(f'{pad}) {{')
            indent += 1

        # Write the variantSet block
        pad = "    " * indent
        vs_name = vs.name.replace(" ", "_").lower()
        lines.append(f'{pad}variantSet "{vs_name}" = {{')
        for variant in vs.variants:
            v_name = variant.name.replace(" ", "_").lower()
            lines.append(f'{pad}    "{v_name}" {{')
            lines.append(f'{pad}        custom string cb:content = "{_escape_usda_string(variant.content)}"')
            if variant.evidence_for:
                evs = ", ".join(f'"{_escape_usda_string(e)}"' for e in variant.evidence_for)
                lines.append(f'{pad}        custom string[] cb:evidence_for = [{evs}]')
            lines.append(f'{pad}    }}')
        lines.append(f'{pad}}}')

        # Close nested prims
        for _ in range(indent):
            indent -= 1
            pad = "    " * indent
            lines.append(f'{pad}}}')
        lines.append("")

    return "\n".join(lines)


def generate_stage_root(
    project_id: str,
    project_name: str,
) -> str:
    """Generate the root stage.usda that sublayers all 6 arc files.

    Sublayer ordering matches LIVRPS: strongest (LOCAL) first,
    weakest (SPECIALIZES) last. USD resolves opinions in sublayer
    order, so this mechanically produces LIVRPS resolution.
    """
    sublayer_refs = "\n".join(
        f'        @./{f}@,' for f in SUBLAYER_ORDER
    )

    return (
        '#usda 1.0\n'
        '(\n'
        f'    doc = "Cognitive Bridge Composition Stage — {_escape_usda_string(project_name)} ({project_id})"\n'
        f'    subLayers = [\n'
        f'{sublayer_refs}\n'
        f'    ]\n'
        ')\n'
        '\n'
        '# USD composition resolves opinions in sublayer order.\n'
        '# session_local.usda (LOCAL, arc=10) is listed first and\n'
        '# therefore strongest — matching LIVRPS semantics exactly.\n'
        '#\n'
        '# When two sublayers define the same attribute on the same\n'
        '# prim path, the earlier sublayer wins. This is mechanically\n'
        '# identical to the IntEnum sorting in CompositionStage.resolve().\n'
    )


def export_stage_to_usda(
    stage: CompositionStage,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Export a CompositionStage as 7 .usda files.

    Generates one sublayer per arc level plus a root stage.usda that
    composes them in LIVRPS order. The exported files constitute a
    valid USD stage whose composition produces the same resolution as
    the SQL-based CompositionStage.resolve().

    Args:
        stage: The composition stage to export
        output_dir: Directory to write .usda files into (created if needed)

    Returns:
        Dict mapping filename to absolute Path for each generated file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group active assertions by arc
    by_arc: dict[CompositionArc, list[Assertion]] = {
        arc: [] for arc in CompositionArc
    }
    for ast in stage.assertions.values():
        if ast.active:
            by_arc[ast.arc].append(ast)

    written: dict[str, Path] = {}

    # Generate each arc sublayer
    for arc, (filename, doc) in ARC_FILE_MAP.items():
        if arc == CompositionArc.VARIANT_SET:
            # Special handling for variant layer
            active_vs = [
                vs for vs in stage.variant_sets.values()
                if not vs.resolved
            ]
            content = generate_variant_layer(active_vs, by_arc[arc])
        else:
            content = generate_arc_layer(by_arc[arc], arc, doc)

        filepath = output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        written[filename] = filepath

    # Generate root stage
    root_content = generate_stage_root(stage.project_id, stage.project_name)
    root_path = output_dir / "stage.usda"
    root_path.write_text(root_content, encoding="utf-8")
    written["stage.usda"] = root_path

    return written
