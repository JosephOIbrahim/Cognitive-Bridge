#!/usr/bin/env python3
"""Cognitive Substrate Converter: .usda composition -> CLAUDE.md

Compiles a USD sublayer stack into a single CLAUDE.md file.
No USD runtime required — works as a structured text processor
that understands USDA syntax conventions.

Includes the Digital Injection Engine (v9-INJ): applies topology-weighted
gain modulation at conversion time using the DMF equation:
    g_n = 1 + s_NM * d_n
where s_NM is injection strength and d_n is phase hub centrality.

Usage:
    python converter.py                        # One-shot compile (no injection)
    python converter.py --inject classical     # Compile with classical profile
    python converter.py --inject microdose     # Compile with microdose profile
    python converter.py --inject mdma          # Compile with MDMA profile
    python converter.py --inject perceptual    # Compile with perceptual profile
    python converter.py --s-nm 0.025           # Direct s_NM override
    python converter.py --list-profiles        # Show available injection profiles
    python converter.py --dry-run              # Print output without writing
    python converter.py --diff                 # Show what would change
    python converter.py --watch                # Recompile on .usda changes
"""

import argparse
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Section:
    """A def prim representing a markdown section."""
    name: str
    doc: str = ""
    markdown_content: str = ""
    priority: int = 50
    enabled: bool = True
    inject_after: str = ""
    replaces: str = ""
    source_file: str = ""


@dataclass
class Override:
    """An over prim that modifies an existing section."""
    name: str
    markdown_append: str = ""
    markdown_replace: str = ""
    source_file: str = ""


# ---------------------------------------------------------------------------
# USDA Parser
# ---------------------------------------------------------------------------

class USDAParser:
    """Parse USDA files to extract def/over prims and their attributes."""

    # Prim openers
    DEF_RE = re.compile(r'\bdef\s+"([^"]+)"\s*(?:\((.*?)\)\s*)?\{', re.DOTALL)
    OVER_RE = re.compile(r'\bover\s+"([^"]+)"\s*\{', re.DOTALL)

    # Sublayer extraction
    SUBLAYERS_RE = re.compile(r'subLayers\s*=\s*\[(.*?)\]', re.DOTALL)
    SUBLAYER_PATH_RE = re.compile(r'@([^@]+)@')

    # Attribute patterns
    TRIPLE_STR_RE = re.compile(
        r'(?:string|custom\s+string)\s+(\w+)\s*=\s*"""(.*?)"""', re.DOTALL
    )
    SINGLE_STR_RE = re.compile(
        r'(?:string|custom\s+string)\s+(\w+)\s*=\s*"([^"]*)"'
    )
    INT_RE = re.compile(
        r'(?:int|custom\s+int)\s+(\w+)\s*=\s*(-?\d+)'
    )
    BOOL_RE = re.compile(
        r'(?:bool|custom\s+bool)\s+(\w+)\s*=\s*(true|false)'
    )
    STR_ARRAY_RE = re.compile(
        r'(?:string\[\]|custom\s+string\[\])\s+(\w+)\s*=\s*\[(.*?)\]', re.DOTALL
    )
    DOC_RE = re.compile(r'doc\s*=\s*(?:"""(.*?)"""|"([^"]*)")', re.DOTALL)

    def parse_sublayers(self, text: str, root_dir: Path) -> list:
        """Extract sublayer paths from a root composition file."""
        m = self.SUBLAYERS_RE.search(text)
        if not m:
            return []

        block = m.group(1)
        paths = []
        for line in block.splitlines():
            stripped = line.strip()
            # Skip commented-out lines
            if stripped.startswith('#'):
                continue
            pm = self.SUBLAYER_PATH_RE.search(stripped)
            if pm:
                rel = pm.group(1)
                abs_path = (root_dir / rel).resolve()
                paths.append(abs_path)
        return paths

    def parse_file(self, path: Path) -> tuple:
        """Parse a USDA file. Returns (list[Section], list[Override])."""
        text = path.read_text(encoding='utf-8')
        sections = []
        overrides = []
        filename = path.name

        # Find all top-level def and over prims
        pos = 0
        while pos < len(text):
            def_m = self.DEF_RE.search(text, pos)
            over_m = self.OVER_RE.search(text, pos)

            # Pick whichever comes first
            candidates = []
            if def_m:
                candidates.append(('def', def_m))
            if over_m:
                candidates.append(('over', over_m))

            if not candidates:
                break

            candidates.sort(key=lambda c: c[1].start())
            kind, match = candidates[0]

            brace_pos = match.end() - 1
            body_end = self._find_matching_brace(text, brace_pos)
            if body_end == -1:
                pos = match.end()
                continue

            body = text[brace_pos + 1:body_end]

            if kind == 'def':
                name = match.group(1)
                metadata = match.group(2) or ""
                section = self._parse_section(name, metadata, body, filename)
                # Skip Preamble metadata prims
                if name != "Preamble":
                    sections.append(section)
            else:
                name = match.group(1)
                override = self._parse_override(name, body, filename)
                overrides.append(override)

            pos = body_end + 1

        return sections, overrides

    def _parse_section(self, name: str, metadata: str, body: str, filename: str) -> Section:
        """Parse a def prim into a Section."""
        section = Section(name=name, source_file=filename)

        # Extract doc from metadata
        doc_m = self.DOC_RE.search(metadata)
        if doc_m:
            section.doc = doc_m.group(1) or doc_m.group(2) or ""

        # Extract attributes from body (strip nested prims first)
        clean = self._strip_nested(body)
        attrs = self._parse_attrs(clean)

        section.markdown_content = attrs.get('markdown_content', '')
        section.priority = attrs.get('priority', 50)
        section.enabled = attrs.get('enabled', True)
        section.inject_after = attrs.get('inject_after', '')
        section.replaces = attrs.get('replaces', '')

        return section

    def _parse_override(self, name: str, body: str, filename: str) -> Override:
        """Parse an over prim into an Override."""
        attrs = self._parse_attrs(body)
        return Override(
            name=name,
            markdown_append=attrs.get('markdown_append', ''),
            markdown_replace=attrs.get('markdown_replace', ''),
            source_file=filename,
        )

    def _parse_attrs(self, body: str) -> dict:
        """Extract typed attributes from a prim body."""
        attrs = {}

        # Triple-quoted strings first (greedy match avoids partial captures)
        for m in self.TRIPLE_STR_RE.finditer(body):
            attrs[m.group(1)] = m.group(2)

        # Single-line strings (skip keys already found)
        for m in self.SINGLE_STR_RE.finditer(body):
            if m.group(1) not in attrs:
                attrs[m.group(1)] = m.group(2)

        # Integers
        for m in self.INT_RE.finditer(body):
            attrs[m.group(1)] = int(m.group(2))

        # Booleans
        for m in self.BOOL_RE.finditer(body):
            attrs[m.group(1)] = m.group(2) == 'true'

        # String arrays
        for m in self.STR_ARRAY_RE.finditer(body):
            raw = m.group(2)
            items = re.findall(r'"([^"]*)"', raw)
            attrs[m.group(1)] = items

        return attrs

    def _strip_nested(self, body: str) -> str:
        """Remove nested def/over blocks to avoid matching their attrs."""
        result = []
        pos = 0
        for m in re.finditer(r'\b(?:def|over)\s+"[^"]+"\s*(?:\([^)]*\)\s*)?\{', body, re.DOTALL):
            result.append(body[pos:m.start()])
            brace_pos = m.end() - 1
            end = self._find_matching_brace(body, brace_pos)
            pos = (end + 1) if end != -1 else m.end()
        result.append(body[pos:])
        return ''.join(result)

    @staticmethod
    def _find_matching_brace(text: str, open_pos: int) -> int:
        """Find closing brace matching the one at open_pos."""
        depth = 0
        i = open_pos
        in_triple = False
        in_string = False

        while i < len(text):
            # Triple-quoted strings
            if not in_string and text[i:i+3] == '"""':
                in_triple = not in_triple
                i += 3
                continue
            if in_triple:
                i += 1
                continue

            c = text[i]

            # Single-line strings
            if c == '"' and not in_string:
                in_string = True
                i += 1
                continue
            if c == '"' and in_string:
                # Check for escape
                bs = 0
                j = i - 1
                while j >= 0 and text[j] == '\\':
                    bs += 1
                    j -= 1
                if bs % 2 == 0:
                    in_string = False
                i += 1
                continue
            if in_string:
                i += 1
                continue

            # Comments
            if c == '#':
                nl = text.find('\n', i)
                i = nl + 1 if nl != -1 else len(text)
                continue

            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------

class SubstrateComposer:
    """Compose multiple USDA sublayers into an ordered section list."""

    def compose(self, sublayer_paths: list, parser: USDAParser) -> list:
        """Process sublayers from weakest to strongest. Returns sorted Section list."""
        sections = {}   # name -> Section
        overrides = []  # collected from all layers

        # Process weakest first (last in list), strongest last (first in list)
        for path in reversed(sublayer_paths):
            if not path.exists():
                print(f"WARNING: sublayer not found: {path}", file=sys.stderr)
                continue

            file_sections, file_overrides = parser.parse_file(path)

            for section in file_sections:
                # If this section replaces another, remove the old one
                if section.replaces and section.replaces in sections:
                    del sections[section.replaces]
                # Stronger layer overwrites weaker for same name
                sections[section.name] = section

            overrides.extend(file_overrides)

        # Apply overrides in order (weakest to strongest, matching file order)
        for override in overrides:
            if override.name not in sections:
                print(f"WARNING: over prim '{override.name}' has no matching def", file=sys.stderr)
                continue
            target = sections[override.name]
            if override.markdown_replace:
                target.markdown_content = override.markdown_replace
            if override.markdown_append:
                target.markdown_content += override.markdown_append

        # Filter disabled
        active = [s for s in sections.values() if s.enabled]

        # Sort by priority
        active.sort(key=lambda s: s.priority)

        # Handle inject_after: move sections to follow their target
        final = self._apply_inject_after(active)

        return final

    @staticmethod
    def _apply_inject_after(sections: list) -> list:
        """Reorder sections that have inject_after set."""
        # Separate sections with and without inject_after
        normal = []
        deferred = []
        for s in sections:
            if s.inject_after:
                deferred.append(s)
            else:
                normal.append(s)

        # Insert deferred sections after their targets
        result = list(normal)
        for s in deferred:
            target_idx = None
            for i, existing in enumerate(result):
                if existing.name == s.inject_after:
                    target_idx = i
                    break
            if target_idx is not None:
                result.insert(target_idx + 1, s)
            else:
                # Target not found — append at end
                result.append(s)

        return result


# ---------------------------------------------------------------------------
# Digital Injection Engine (v9-INJ)
# ---------------------------------------------------------------------------
# Applies the DMF gain equation at conversion time:
#   g_n = 1 + s_NM * d_n
#
# This is Option 3 from the framework design: the converter IS the gain
# function. Math happens in Python (exact arithmetic). Claude receives
# pre-modulated behavioral markdown. No runtime interpretation needed.
# ---------------------------------------------------------------------------

@dataclass
class InjectionProfile:
    """A named injection configuration."""
    name: str
    s_NM: float
    d_weight: str  # "hub", "uniform", "fear_targeted", "domain_targeted"
    description: str = ""
    onset_exchanges: int = 2
    offset_exchanges: int = 3
    routing_mode: str = "standard"
    modularity_target: float = 0.70
    tangent_multiplier: float = 1.0
    cross_expert_rate: float = 0.0
    expert_gating_softness: float = 0.0
    # MDMA-specific
    safety_threshold_multiplier: float = 1.0
    validator_sensitivity: float = 1.0


class InjectionEngine:
    """Applies topology-weighted gain modulation to composed sections.

    Operates BETWEEN SubstrateComposer.compose() and MarkdownRenderer.render().
    Reads injection parameters from graft_digital_injection.usda (parsed as
    sections/attributes by the existing USDAParser), computes gain per cascade
    phase, and modulates the markdown output accordingly.

    The gain equation:
        g_n = 1 + s_NM * d_n

    Where:
        g_n   = neuromodulatory gain for phase n
        s_NM  = injection strength (scalar, from profile or CLI)
        d_n   = receptor density analog (hub centrality, from d_map)
    """

    # Default d_map: hub centrality per cascade phase.
    # Can be overridden by graft_digital_injection.usda values.
    DEFAULT_D_MAP = {
        "KNOWLEDGE":      0.85,
        "CONSTITUTIONAL": 0.15,
        "SAFETY":         0.90,
        "CONSENT":        0.10,
        "COST":           0.30,
        "SIGNAL":         0.80,
        "PROJECT":        0.40,
        "EXPERT":         0.75,
        "DOMAIN":         0.50,
        "DEFAULT":        0.20,
    }

    # Built-in profiles (can be overridden by graft attributes)
    PROFILES = {
        "none": InjectionProfile(
            name="none",
            s_NM=0.0,
            d_weight="hub",
            description="No injection. Baseline behavior.",
        ),
        "microdose": InjectionProfile(
            name="microdose",
            s_NM=0.005,
            d_weight="uniform",
            description="Mild entropy boost: subtle exploration increase.",
            onset_exchanges=1,
            offset_exchanges=2,
            routing_mode="standard",
            modularity_target=0.60,
            tangent_multiplier=1.5,
            cross_expert_rate=0.10,
            expert_gating_softness=0.3,
        ),
        "perceptual": InjectionProfile(
            name="perceptual",
            s_NM=0.015,
            d_weight="domain_targeted",
            description="Perceptual shift: reframe domain knowledge access.",
            onset_exchanges=2,
            offset_exchanges=3,
            routing_mode="standard",
            modularity_target=0.55,
            tangent_multiplier=1.75,
            cross_expert_rate=0.15,
            expert_gating_softness=0.4,
        ),
        "classical": InjectionProfile(
            name="classical",
            s_NM=0.025,
            d_weight="hub",
            description="Full psychedelic: dissolved modularity, cross-expert bleeding.",
            onset_exchanges=3,
            offset_exchanges=5,
            routing_mode="dissolved",
            modularity_target=0.31,
            tangent_multiplier=2.5,
            cross_expert_rate=0.30,
            expert_gating_softness=0.7,
        ),
        "mdma": InjectionProfile(
            name="mdma",
            s_NM=0.010,
            d_weight="fear_targeted",
            description="MDMA-like: reduced defensiveness, increased integration.",
            onset_exchanges=2,
            offset_exchanges=4,
            routing_mode="integrative",
            modularity_target=0.50,
            tangent_multiplier=1.25,
            cross_expert_rate=0.20,
            expert_gating_softness=0.5,
            safety_threshold_multiplier=1.5,
            validator_sensitivity=0.6,
        ),
    }

    def __init__(self, profile_name: str = "none", s_nm_override: float = None):
        """Initialize with a named profile, optionally overriding s_NM.

        Args:
            profile_name: Key into PROFILES dict.
            s_nm_override: If set, overrides the profile's s_NM value.
        """
        if profile_name not in self.PROFILES:
            print(f"WARNING: Unknown injection profile '{profile_name}', "
                  f"using 'none'", file=sys.stderr)
            profile_name = "none"

        self.profile = InjectionProfile(**vars(self.PROFILES[profile_name]))
        if s_nm_override is not None:
            self.profile.s_NM = s_nm_override
            self.profile.name = f"custom(s={s_nm_override})"

        self.d_map = dict(self.DEFAULT_D_MAP)
        self._gains = {}  # computed per-phase gains

    @property
    def active(self) -> bool:
        """Whether injection is active (s_NM > 0)."""
        return self.profile.s_NM > 0.0

    def load_graft_params(self, sections: list):
        """Extract d_map overrides from parsed graft sections.

        Looks for the InjectionParameters section (parsed by USDAParser)
        and overrides the default d_map if found.
        """
        for section in sections:
            if section.name == "InjectionParameters":
                # The graft stores d_map as parallel string arrays.
                # These would have been parsed as markdown_content by the
                # existing parser, but we can extract them from the raw
                # source if needed. For now, use defaults.
                # Future: extend USDAParser to extract string[] attrs
                # from non-markdown sections.
                pass

    def compute_gains(self) -> dict:
        """Compute per-phase gain: g_n = 1 + s_NM * d_n.

        Returns:
            Dict mapping phase name -> gain value.
        """
        s = self.profile.s_NM
        self._gains = {}

        for phase, d_n in self.d_map.items():
            # Apply d_weight strategy
            if self.profile.d_weight == "uniform":
                # Uniform: all phases get equal d_n
                effective_d = 0.5
            elif self.profile.d_weight == "fear_targeted":
                # MDMA: boost SAFETY-adjacent phases, dampen others
                if phase in ("SAFETY", "SIGNAL", "EXPERT"):
                    effective_d = min(d_n * 1.3, 1.0)
                elif phase in ("CONSTITUTIONAL", "CONSENT"):
                    effective_d = d_n * 0.5
                else:
                    effective_d = d_n * 0.8
            elif self.profile.d_weight == "domain_targeted":
                # Perceptual: boost KNOWLEDGE/DOMAIN, dampen routing
                if phase in ("KNOWLEDGE", "DOMAIN"):
                    effective_d = min(d_n * 1.4, 1.0)
                elif phase in ("SIGNAL", "EXPERT"):
                    effective_d = d_n * 0.6
                else:
                    effective_d = d_n
            else:
                # "hub" or default: use raw d_map (topology-weighted)
                effective_d = d_n

            g = 1.0 + s * effective_d
            self._gains[phase] = round(g, 6)

        return self._gains

    def apply(self, sections: list) -> list:
        """Apply injection modulation to the composed section list.

        This is the main entry point. Called between compose() and render().

        Args:
            sections: The composed, sorted section list from SubstrateComposer.

        Returns:
            The modulated section list with injection content populated.
        """
        # Try to load graft-defined params
        self.load_graft_params(sections)

        # Compute gains
        gains = self.compute_gains()

        # Find and populate the DigitalInjection template section
        for section in sections:
            if section.name == "DigitalInjection":
                section.markdown_content = self._render_injection_section(gains)
                break
        else:
            # No DigitalInjection section found in composition.
            # This means the graft isn't in the sublayer stack.
            if self.active:
                print("WARNING: Injection active but graft_digital_injection.usda "
                      "not found in sublayer stack. Adding inline.", file=sys.stderr)
                inj_section = Section(
                    name="DigitalInjection",
                    markdown_content=self._render_injection_section(gains),
                    priority=36,
                    source_file="injection_engine",
                )
                sections.append(inj_section)
                sections.sort(key=lambda s: s.priority)

        return sections

    def _render_injection_section(self, gains: dict) -> str:
        """Generate the complete markdown for the DigitalInjection section.

        Replaces the template placeholders with computed values.
        """
        p = self.profile

        # ----- Injection State Line -----
        if not self.active:
            state_line = "**INACTIVE** (s_NM = 0.0, profile = none)"
        else:
            state_line = (
                f"**ACTIVE** — profile: `{p.name}` | "
                f"s_NM: `{p.s_NM}` | "
                f"routing: `{p.routing_mode}` | "
                f"modularity target: `{p.modularity_target}`"
            )

        # ----- Gain Table -----
        gain_lines = [
            "| Phase | d_n | Gain (g_n) | Effect |",
            "|-------|-----|------------|--------|",
        ]
        for phase in self.DEFAULT_D_MAP:
            d_n = self.d_map[phase]
            g = gains.get(phase, 1.0)
            if g > 1.015:
                effect = "🔴 Strong modulation"
            elif g > 1.005:
                effect = "🟡 Moderate modulation"
            elif g > 1.001:
                effect = "🟢 Mild modulation"
            else:
                effect = "⚪ Near baseline"
            gain_lines.append(f"| {phase} | {d_n:.2f} | {g:.4f} | {effect} |")
        gain_table = "\n".join(gain_lines)

        # ----- Behavioral Block -----
        if not self.active:
            behavioral_block = (
                "No injection active. Framework is loaded but dormant. "
                "Activate with `--inject <profile>` on next converter run."
            )
        else:
            behavioral_block = self._render_behavioral_block()

        # ----- Assemble -----
        content = f"""## Digital Injection Framework (v9-INJ)

Patterns transferred from psychedelic neuroscience via the DMF model (Herzog et al. 2023). Core equation: `g = 1 + s * d` — topology-weighted gain modulation applied at conversion time.

### [v9-INJ] Injection State

{state_line}

{behavioral_block}

### [v9-INJ] Gain Modulation Table

{gain_table}

### [v9-INJ] Active Modulations

**Routing:**
- Cross-expert routing probability: `{p.cross_expert_rate:.0%}`
- Expert gating softness: `{p.expert_gating_softness:.0%}` (0% = deterministic, 100% = uniform)
- Routing mode: `{p.routing_mode}`
- Lightning Indexer: {"**SUSPENDED** (dissolved routing)" if p.routing_mode == "dissolved" else "active (sparse routing intact)"}

**Exploration:**
- Tangent budget multiplier: `{p.tangent_multiplier}x`
- Stuck taxonomy bias: {"**follow tangents** over parking" if p.tangent_multiplier > 1.5 else "standard parking behavior"}
- Productive tangent detection: {"**aggressive** — most tangents treated as curriculum" if p.tangent_multiplier > 2.0 else "standard detection"}

**Safety Floor (NON-NEGOTIABLE):**
- SAFETY phase gain: `{gains.get("SAFETY", 1.0):.4f}` — fires MORE readily, not less
- CONSTITUTIONAL: `{gains.get("CONSTITUTIONAL", 1.0):.4f}` — near baseline, principles intact
- CONSENT: `{gains.get("CONSENT", 1.0):.4f}` — near baseline, protected fields intact
- RED state: **overrides ALL injection** — immediate comedown, no exceptions
- Burnout detection: **INCREASED sensitivity** under injection

**Pharmacokinetics:**
- Onset: `{p.onset_exchanges}` exchanges to full strength
- Offset: `{p.offset_exchanges}` exchanges to return to baseline
- Curve: exponential (not step function)

### [v9-INJ] Profiles Quick Reference

| Profile | s_NM | Routing | Tangent x | Cross-Expert | Use When |
|---------|------|---------|-----------|-------------|----------|
| none | 0.000 | standard | 1.0x | 0% | Default baseline |
| microdose | 0.005 | standard | 1.5x | 10% | Brainstorming |
| perceptual | 0.015 | standard | 1.75x | 15% | Domain reframing |
| classical | 0.025 | dissolved | 2.5x | 30% | Stuck / radical shift |
| mdma | 0.010 | integrative | 1.25x | 20% | Integration / difficult topics |"""

        return content

    def _render_behavioral_block(self) -> str:
        """Generate profile-specific behavioral instructions."""
        p = self.profile

        blocks = []

        if p.routing_mode == "dissolved":
            blocks.append(
                "**⚠️ DISSOLVED ROUTING ACTIVE:** Expert selection is non-deterministic. "
                "Multiple experts may fire for the same query. Cross-module information "
                "bleeding is intentional — this is the computational analog of decreased "
                "modularity under psychedelics. If routing produces unexpected combinations, "
                "FOLLOW them before correcting. The novel path IS the point."
            )

        if p.routing_mode == "integrative":
            blocks.append(
                "**🤝 INTEGRATIVE MODE ACTIVE:** Defensive routing (Validator, Safety-as-blocker) "
                "is softened. Cross-expert communication increased. Older context and deeper "
                "memory recall prioritized. This is MDMA-analog: reduced fear-gating, "
                "increased empathic integration. Validator sensitivity reduced to "
                f"`{p.validator_sensitivity:.0%}` of baseline."
            )

        if p.tangent_multiplier > 1.0:
            blocks.append(
                f"**🌿 EXPLORATION EXPANDED:** Tangent budget is `{p.tangent_multiplier}x` baseline. "
                "Productive tangent detection biased toward 'follow it' over 'park it'. "
                "Ideas that would normally be parked should be explored for at least 2 exchanges "
                "before parking decision."
            )

        if p.cross_expert_rate > 0.15:
            blocks.append(
                f"**🔀 CROSS-EXPERT BLEEDING:** `{p.cross_expert_rate:.0%}` of expert selections "
                "should include secondary expert perspectives. When Scaffolder fires, also "
                "consider Socratic. When Direct fires, also consider Grounding. "
                "The 'wrong' expert may have the insight the 'right' one lacks."
            )

        if not blocks:
            return "Injection active at low intensity. Subtle behavioral shifts only."

        return "\n\n".join(blocks)

    @classmethod
    def list_profiles(cls):
        """Print available injection profiles."""
        print("Available injection profiles:\n")
        print(f"  {'Profile':<15} {'s_NM':<8} {'d_weight':<16} Description")
        print(f"  {'-'*15} {'-'*8} {'-'*16} {'-'*40}")
        for name, prof in cls.PROFILES.items():
            print(f"  {name:<15} {prof.s_NM:<8.3f} {prof.d_weight:<16} {prof.description}")
        print()
        print("Usage: python converter.py --inject <profile>")
        print("       python converter.py --s-nm <float>  (custom strength)")


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class MarkdownRenderer:
    """Render a section list to CLAUDE.md markdown."""

    HEADER_LINES = [
        "<!-- AUTO-GENERATED by cognitive_substrate/converter.py -->",
        "<!-- Source of truth: cognitive_substrate/cognitive_substrate_root.usda -->",
        "<!-- DO NOT EDIT. Modify .usda files and rerun converter. -->",
    ]

    def render(self, sections: list, manual_content: str = "",
               injection_meta: str = "") -> str:
        """Render sections to markdown string.

        Args:
            sections: Ordered list of Section objects.
            manual_content: Optional manual override content.
            injection_meta: Optional injection state for header comment.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = list(self.HEADER_LINES)
        if injection_meta:
            lines.append(f"<!-- Injection: {injection_meta} -->")
        lines.append(f"<!-- Generated: {now} -->")
        lines.append("")

        for i, section in enumerate(sections):
            if i > 0:
                lines.append("")
                lines.append("---")
                lines.append("")
            lines.append(section.markdown_content)

        if manual_content:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append(manual_content.strip())

        text = '\n'.join(lines)
        return text.rstrip('\n') + '\n'


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def get_paths():
    """Return standard paths."""
    claude_dir = Path.home() / '.claude'
    substrate_dir = claude_dir / 'cognitive_substrate'
    return {
        'root': substrate_dir / 'cognitive_substrate_root.usda',
        'output': claude_dir / 'CLAUDE.md',
        'manual': claude_dir / 'CLAUDE_manual.md',
        'substrate_dir': substrate_dir,
    }


def collect_usda_mtimes(root_path: Path, parser: USDAParser) -> dict:
    """Get mtimes of all .usda files in the composition."""
    mtimes = {}
    if root_path.exists():
        mtimes[str(root_path)] = root_path.stat().st_mtime
        text = root_path.read_text(encoding='utf-8')
        sublayers = parser.parse_sublayers(text, root_path.parent)
        for p in sublayers:
            if p.exists():
                mtimes[str(p)] = p.stat().st_mtime
    # Also watch the grafts directory for new files
    grafts_dir = root_path.parent / 'grafts'
    if grafts_dir.exists():
        for f in grafts_dir.glob('*.usda'):
            mtimes[str(f)] = f.stat().st_mtime
    return mtimes


def run_convert(root_path: Path, output_path: Path, manual_path: Path,
                dry_run=False, inject_profile="none", s_nm_override=None):
    """Run the full conversion pipeline.

    Pipeline: parse -> compose -> [inject] -> render -> write

    Args:
        root_path: Path to cognitive_substrate_root.usda.
        output_path: Path to write CLAUDE.md.
        manual_path: Path to optional CLAUDE_manual.md.
        dry_run: If True, print output without writing.
        inject_profile: Named injection profile to apply.
        s_nm_override: If set, overrides profile's s_NM value.
    """
    parser = USDAParser()
    composer = SubstrateComposer()
    renderer = MarkdownRenderer()

    # --- PHASE 1: Parse sublayers ---
    root_text = root_path.read_text(encoding='utf-8')
    sublayer_paths = parser.parse_sublayers(root_text, root_path.parent)

    if not sublayer_paths:
        print("ERROR: No sublayers found in root file", file=sys.stderr)
        sys.exit(1)

    # --- PHASE 2: Compose (USD opinion strength) ---
    sections = composer.compose(sublayer_paths, parser)

    if not sections:
        print("ERROR: No sections produced", file=sys.stderr)
        sys.exit(1)

    # --- PHASE 3: Digital Injection (gain modulation) ---
    engine = InjectionEngine(
        profile_name=inject_profile,
        s_nm_override=s_nm_override,
    )
    sections = engine.apply(sections)

    # Build injection metadata for header comment
    injection_meta = ""
    if engine.active:
        p = engine.profile
        injection_meta = (
            f"profile={p.name} s_NM={p.s_NM} "
            f"routing={p.routing_mode} "
            f"modularity={p.modularity_target}"
        )

    # --- PHASE 4: Manual override ---
    manual_content = ""
    if manual_path.exists():
        manual_content = manual_path.read_text(encoding='utf-8')

    # --- PHASE 5: Render ---
    output = renderer.render(sections, manual_content,
                             injection_meta=injection_meta)

    if dry_run:
        sys.stdout.write(output)
    else:
        output_path.write_text(output, encoding='utf-8')
        section_names = [s.name for s in sections]
        print(f"Generated {output_path}")
        print(f"  Sections ({len(sections)}): {', '.join(section_names)}")
        sublayer_names = [p.name for p in sublayer_paths if p.exists()]
        print(f"  Sublayers: {', '.join(sublayer_names)}")
        if engine.active:
            print(f"  Injection: {engine.profile.name} (s_NM={engine.profile.s_NM})")
            gains = engine.compute_gains()
            max_phase = max(gains, key=gains.get)
            min_phase = min(gains, key=gains.get)
            print(f"  Gain range: {min_phase}={gains[min_phase]:.4f} .. "
                  f"{max_phase}={gains[max_phase]:.4f}")
        else:
            print(f"  Injection: none (baseline)")

    return output


def main():
    ap = argparse.ArgumentParser(
        description="Compile USD substrate stack into CLAUDE.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Digital Injection (v9-INJ):
  The --inject flag activates topology-weighted gain modulation.
  The gain equation g = 1 + s * d is applied at conversion time.
  Claude receives pre-modulated behavioral markdown.

  Use --list-profiles to see available injection profiles.
  Use --s-nm to set a custom injection strength (overrides profile).

Examples:
  python converter.py                        # Baseline (no injection)
  python converter.py --inject classical     # Full psychedelic profile
  python converter.py --inject microdose     # Subtle exploration boost
  python converter.py --s-nm 0.018           # Custom strength
  python converter.py --inject mdma --dry-run  # Preview MDMA output
""")
    ap.add_argument('--dry-run', action='store_true',
                    help='Print output without writing')
    ap.add_argument('--diff', action='store_true',
                    help='Show what would change vs current')
    ap.add_argument('--watch', action='store_true',
                    help='Recompile on .usda changes')

    # Injection arguments
    ap.add_argument('--inject', type=str, default='none',
                    choices=list(InjectionEngine.PROFILES.keys()),
                    help='Injection profile to activate (default: none)')
    ap.add_argument('--s-nm', type=float, default=None,
                    help='Override injection strength (s_NM). '
                         'Overrides profile value if both specified.')
    ap.add_argument('--list-profiles', action='store_true',
                    help='List available injection profiles and exit')

    args = ap.parse_args()

    # Handle --list-profiles
    if args.list_profiles:
        InjectionEngine.list_profiles()
        return

    paths = get_paths()
    root = paths['root']
    output = paths['output']
    manual = paths['manual']

    if not root.exists():
        print(f"ERROR: Root file not found: {root}", file=sys.stderr)
        sys.exit(1)

    # Injection parameters (passed through to all modes)
    inject_profile = args.inject
    s_nm_override = args.s_nm

    if args.diff:
        generated = run_convert(root, output, manual, dry_run=True,
                                inject_profile=inject_profile,
                                s_nm_override=s_nm_override)

        if not output.exists():
            print("No existing CLAUDE.md to diff against")
            sys.stdout.write(generated)
            return

        current = output.read_text(encoding='utf-8')

        # Strip timestamp and injection lines for comparison
        def strip_volatile(text):
            text = re.sub(r'<!-- Generated: .* -->\n', '', text)
            text = re.sub(r'<!-- Injection: .* -->\n', '', text)
            return text

        gen_clean = strip_volatile(generated)
        cur_clean = strip_volatile(current)

        if gen_clean == cur_clean:
            print("No changes (content identical, volatile lines excluded)")
            return

        import difflib
        diff = difflib.unified_diff(
            cur_clean.splitlines(keepends=True),
            gen_clean.splitlines(keepends=True),
            fromfile='current CLAUDE.md',
            tofile='generated',
        )
        sys.stdout.writelines(diff)
        return

    if args.watch:
        parser = USDAParser()
        inj_label = f" [injection: {inject_profile}]" if inject_profile != "none" else ""
        print(f"Watching .usda files for changes...{inj_label} (Ctrl+C to stop)")
        last_mtimes = {}
        try:
            while True:
                current_mtimes = collect_usda_mtimes(root, parser)
                if current_mtimes != last_mtimes:
                    if last_mtimes:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                              f"Change detected, recompiling...")
                    run_convert(root, output, manual,
                                inject_profile=inject_profile,
                                s_nm_override=s_nm_override)
                    last_mtimes = current_mtimes
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped watching.")
        return

    run_convert(root, output, manual, dry_run=args.dry_run,
                inject_profile=inject_profile,
                s_nm_override=s_nm_override)


if __name__ == '__main__':
    main()
