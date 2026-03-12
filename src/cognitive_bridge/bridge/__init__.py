"""Bridge module — USD interoperability layer.

Exports the USDA stage as text files and optionally resolves
via OpenUSD (pxr) for mechanical composition verification.
"""

from cognitive_bridge.bridge.usda_export import (
    export_stage_to_usda,
    generate_arc_layer,
    generate_stage_root,
    generate_variant_layer,
    ARC_FILE_MAP,
    SUBLAYER_ORDER,
)
from cognitive_bridge.bridge.usda_resolve import (
    check_consistency,
    resolve_via_text,
    resolve_via_usd,
)

__all__ = [
    "ARC_FILE_MAP",
    "SUBLAYER_ORDER",
    "check_consistency",
    "export_stage_to_usda",
    "generate_arc_layer",
    "generate_stage_root",
    "generate_variant_layer",
    "resolve_via_text",
    "resolve_via_usd",
]
