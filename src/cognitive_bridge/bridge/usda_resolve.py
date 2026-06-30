"""USDA Resolver — resolve composed USD stage and verify consistency.

Two resolution strategies:
1. Pure-text resolver (always available) — parses USDA sublayer files
   in order, builds per-path winner map. Simple but correct.
2. OpenUSD resolver (requires pxr) — uses actual USD composition.
   More authoritative but depends on external library.

The consistency checker compares SQL-based resolution (CompositionStage.resolve())
against USDA-based resolution to verify the composition model is mechanically
correct.
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Check for OpenUSD availability
_USD_AVAILABLE = False
try:
    from pxr import Usd, Sdf  # type: ignore[import]
    _USD_AVAILABLE = True
except ImportError:
    pass


def resolve_via_text(stage_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Resolve a USDA stage by parsing sublayer files in order.

    This is a pure-text resolver that doesn't require OpenUSD.
    It reads sublayer files in LIVRPS order (as declared in stage.usda)
    and builds a per-prim-path winner map.

    The first sublayer to define an attribute on a prim path wins —
    this matches USD sublayer composition semantics.

    Args:
        stage_dir: Directory containing the 7 .usda files

    Returns:
        Dict mapping prim paths to their resolved attributes.
        Each value is a dict with keys like:
        {"content": str, "assertion_id": str, "author": str, ...}
    """
    stage_dir = Path(stage_dir)
    stage_file = stage_dir / "stage.usda"

    if not stage_file.exists():
        raise FileNotFoundError(f"stage.usda not found in {stage_dir}")

    # Parse sublayer order from stage.usda
    stage_text = stage_file.read_text(encoding="utf-8")
    sublayer_pattern = re.compile(r'@\./([^@]+)@')
    sublayers = sublayer_pattern.findall(stage_text)

    if not sublayers:
        return {}

    resolved: dict[str, dict[str, Any]] = {}

    # Process sublayers in order (first = strongest, matching LIVRPS)
    for sublayer_name in sublayers:
        sublayer_path = stage_dir / sublayer_name
        if not sublayer_path.exists():
            continue

        layer_text = sublayer_path.read_text(encoding="utf-8")
        prims = _parse_prims_from_usda(layer_text)

        for prim_path, attrs in prims.items():
            if prim_path not in resolved:
                resolved[prim_path] = attrs
            # If already resolved (by a stronger sublayer), skip.
            # This IS the LIVRPS resolution: first sublayer wins.

    return resolved


# Opinion child prims (named ``opinion_N``) preserve losing same-arc opinions
# non-destructively in the export. They are nested under an assertion prim and
# are NOT composition winners, so the resolver must not surface them as paths.
_OPINION_RE = re.compile(r"^opinion_\d+$")


def _parse_prims_from_usda(text: str) -> dict[str, dict[str, Any]]:
    """Parse prim paths and cb: attributes from USDA text.

    Extracts all prims with their custom cb: namespace attributes. Uses regex
    parsing — not a full USD parser, but sufficient for the structured USDA we
    generate.

    Each prim accumulates its own attributes via a stack parallel to the path
    stack, so a prim is recorded even when it contains child prims — both
    legitimate nested topic paths (``/db`` with a ``/db/engine`` child) and
    ``opinion_N`` children. Opinion children are dropped: they hold shadowed
    (losing) same-arc opinions, not winners, and surfacing them would create
    phantom paths that diverge from CompositionStage.resolve().

    Returns:
        Dict mapping prim path strings to attribute dicts.
    """
    prims: dict[str, dict[str, Any]] = {}

    # Parallel stacks: path segments and the attributes accumulated for each
    # open prim. The innermost open prim is at index -1.
    path_stack: list[str] = []
    attrs_stack: list[dict[str, Any]] = []

    for line in text.split("\n"):
        stripped = line.strip()

        # Match prim definitions: def Scope "name" or over "name"
        prim_match = re.match(r'(?:def|over)\s+\w+\s+"([^"]+)"', stripped)
        if prim_match:
            path_stack.append(prim_match.group(1))
            attrs_stack.append({})
            continue

        # Match cb: attributes — they apply to the innermost open prim.
        attr_match = re.match(
            r'custom\s+\w+(?:\[\])?\s+cb:(\w+)\s*=\s*(.+)', stripped
        )
        if attr_match and attrs_stack:
            attr_name = attr_match.group(1)
            attr_value: Any = attr_match.group(2).strip()

            # Parse string value
            if attr_value.startswith('"') and attr_value.endswith('"'):
                attr_value = attr_value[1:-1]
            # Parse string array
            elif attr_value.startswith('['):
                attr_value = re.findall(r'"([^"]*)"', attr_value)
            # Parse float
            elif '.' in attr_value:
                try:
                    attr_value = float(attr_value)
                except ValueError:
                    pass

            attrs_stack[-1][attr_name] = attr_value
            continue

        # Closing brace — record the innermost prim's own attributes, then pop.
        if stripped == "}" and path_stack:
            name = path_stack[-1]
            attrs = attrs_stack.pop()
            # Skip opinion_N children: they are shadowed opinions nested under
            # an assertion prim (the parent carries cb:content), not winners.
            is_opinion = bool(_OPINION_RE.match(name)) and (
                bool(attrs_stack) and "content" in attrs_stack[-1]
            )
            if attrs and not is_opinion:
                prim_path = "/" + "/".join(path_stack)
                if prim_path not in prims:
                    prims[prim_path] = attrs
            path_stack.pop()

    return prims


def resolve_via_usd(stage_dir: str | Path) -> Optional[dict[str, dict[str, Any]]]:
    """Resolve a USDA stage using OpenUSD (pxr).

    Returns None if pxr is not available.

    Args:
        stage_dir: Directory containing the 7 .usda files

    Returns:
        Dict mapping prim paths to resolved attributes, or None if
        pxr is not installed.
    """
    if not _USD_AVAILABLE:
        logger.info(
            "OpenUSD (pxr) not available. "
            "Install via pip install usd-core for USD-native resolution."
        )
        return None

    stage_dir = Path(stage_dir)
    stage_file = stage_dir / "stage.usda"

    if not stage_file.exists():
        raise FileNotFoundError(f"stage.usda not found in {stage_dir}")

    stage = Usd.Stage.Open(str(stage_file))  # type: ignore[name-defined]
    if not stage:
        raise RuntimeError(f"Failed to open USD stage: {stage_file}")

    resolved: dict[str, dict[str, Any]] = {}

    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if path == "/":
            continue

        attrs: dict[str, Any] = {}
        for attr in prim.GetAttributes():
            name = attr.GetName()
            if name.startswith("cb:"):
                key = name[3:]  # Strip cb: prefix
                value = attr.Get()
                if hasattr(value, '__iter__') and not isinstance(value, str):
                    value = list(value)
                attrs[key] = value

        if attrs:
            resolved[path] = attrs

    return resolved


def check_consistency(
    sql_resolved: dict[str, dict[str, Any]],
    usda_resolved: dict[str, dict[str, Any]],
) -> list[str]:
    """Compare SQL-based and USDA-based resolution results.

    Checks that the winning content at each topic path matches
    between the two resolution strategies.

    Args:
        sql_resolved: Output of CompositionStage.resolve()
        usda_resolved: Output of resolve_via_text() or resolve_via_usd()

    Returns:
        List of discrepancy descriptions. Empty list = consistent.
    """
    discrepancies: list[str] = []

    # Extract winning content from SQL resolution
    sql_winners: dict[str, str] = {}
    for path, entry in sql_resolved.items():
        winning = entry.get("winning")
        if winning:
            sql_winners[path] = winning.content

    # Extract winning content from USDA resolution
    usda_winners: dict[str, str] = {}
    for path, attrs in usda_resolved.items():
        content = attrs.get("content")
        if content:
            usda_winners[path] = content

    # Check all SQL paths exist in USDA
    for path, content in sql_winners.items():
        if path not in usda_winners:
            discrepancies.append(
                f"Path {path} exists in SQL resolution but not in USDA"
            )
        elif usda_winners[path] != content:
            discrepancies.append(
                f"Path {path}: SQL winner = '{content}', "
                f"USDA winner = '{usda_winners[path]}'"
            )

    # Check for USDA paths not in SQL
    for path in usda_winners:
        if path not in sql_winners:
            discrepancies.append(
                f"Path {path} exists in USDA resolution but not in SQL"
            )

    return discrepancies
