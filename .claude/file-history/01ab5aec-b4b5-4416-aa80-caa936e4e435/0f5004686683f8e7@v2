#!/usr/bin/env python3
r"""Digital Injection Diagnostic Script

Run from: C:\Users\User\usd-cognitive-substrate\cognitive_substrate\
Usage: python diagnose_injection.py

Checks every link in the chain: files exist, parser resolves paths,
sections compose correctly, injection graft loads, gain math works.
"""

import sys
from pathlib import Path

print("=" * 60)
print("DIGITAL INJECTION DIAGNOSTIC")
print("=" * 60)

errors = []
warnings = []

# ----- STEP 1: File existence -----
print("\n📁 STEP 1: File existence checks")
cwd = Path(".").resolve()
print(f"  Working directory: {cwd}")

files = {
    "root": Path("cognitive_substrate_root.usda"),
    "core": Path("core_substrate_v7.usda"),
    "deepseek": Path("grafts/graft_deepseek_v32.usda"),
    "injection": Path("grafts/graft_digital_injection.usda"),
    "converter": Path("converter.py"),
}

for label, path in files.items():
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    status = f"✅ {size:,} bytes" if exists else "❌ MISSING"
    print(f"  {label:12s} {str(path):50s} {status}")
    if not exists:
        errors.append(f"{label} file missing: {path}")

# ----- STEP 2: Root sublayer resolution -----
print("\n📡 STEP 2: Sublayer resolution")
if files["root"].exists():
    try:
        from converter import USDAParser
        parser = USDAParser()
        root_text = files["root"].read_text(encoding="utf-8")
        sublayers = parser.parse_sublayers(root_text, files["root"].parent)
        print(f"  Sublayers declared: {len(sublayers)}")
        for sl in sublayers:
            exists = sl.exists()
            status = "✅" if exists else "❌ NOT FOUND"
            print(f"    {status} {sl}")
            if not exists:
                errors.append(f"Sublayer not found: {sl}")
    except Exception as e:
        errors.append(f"Parser error: {e}")
        print(f"  ❌ Parser error: {e}")
else:
    print("  ⏭️  Skipped (root file missing)")

# ----- STEP 3: Section parsing per file -----
print("\n🔍 STEP 3: Section parsing per file")
if files["root"].exists():
    try:
        for sl in sublayers:
            if not sl.exists():
                continue
            sections, overrides = parser.parse_file(sl)
            sec_names = [s.name for s in sections]
            over_names = [o.name for o in overrides]
            enabled = [s.name for s in sections if s.enabled]
            disabled = [s.name for s in sections if not s.enabled]
            print(f"  {sl.name}:")
            print(f"    def sections: {sec_names}")
            print(f"    enabled:      {enabled}")
            print(f"    disabled:     {disabled}")
            print(f"    over prims:   {over_names}")
            if not sections and not overrides:
                warnings.append(f"No prims found in {sl.name}")
    except Exception as e:
        errors.append(f"Section parsing error: {e}")
        print(f"  ❌ Error: {e}")

# ----- STEP 4: Full composition -----
print("\n🏗️  STEP 4: Full composition")
try:
    from converter import SubstrateComposer
    composer = SubstrateComposer()
    composed = composer.compose(sublayers, parser)
    print(f"  Sections composed: {len(composed)}")
    for s in composed:
        content_len = len(s.markdown_content) if s.markdown_content else 0
        print(f"    [{s.priority:3d}] {s.name:30s} ({content_len:,} chars) from {s.source_file}")
    
    if len(composed) < 5:
        errors.append(f"Only {len(composed)} sections composed (expected 8+). Core sections may be missing.")
except Exception as e:
    errors.append(f"Composition error: {e}")
    print(f"  ❌ Error: {e}")

# ----- STEP 5: Injection engine -----
print("\n💉 STEP 5: Injection engine")
try:
    from converter import InjectionEngine
    
    for profile in ["none", "microdose", "classical", "mdma"]:
        engine = InjectionEngine(profile)
        gains = engine.compute_gains()
        g_min = min(gains.values())
        g_max = max(gains.values())
        print(f"  {profile:12s} active={str(engine.active):5s} gains={g_min:.4f}..{g_max:.4f}")
    
    # Check if DigitalInjection section exists in composition
    has_di = any(s.name == "DigitalInjection" for s in composed)
    if has_di:
        print(f"  ✅ DigitalInjection section found in composition")
    else:
        print(f"  ⚠️  DigitalInjection section NOT in composition (engine will add inline)")
        warnings.append("DigitalInjection section not in composition — graft may not be loading")
        
except Exception as e:
    errors.append(f"Injection engine error: {e}")
    print(f"  ❌ Error: {e}")

# ----- STEP 6: Output path -----
print("\n📤 STEP 6: Output path")
try:
    from converter import get_paths
    paths = get_paths()
    for label, p in paths.items():
        exists = p.exists() if isinstance(p, Path) else False
        status = "✅ exists" if exists else "⚪ will be created"
        print(f"  {label:15s} {p} ({status})")
except Exception as e:
    print(f"  ❌ Error: {e}")

# ----- SUMMARY -----
print("\n" + "=" * 60)
if errors:
    print(f"❌ {len(errors)} ERROR(S) FOUND:")
    for e in errors:
        print(f"   • {e}")
elif warnings:
    print(f"⚠️  No errors, but {len(warnings)} warning(s):")
    for w in warnings:
        print(f"   • {w}")
else:
    print("✅ ALL CHECKS PASSED")
print("=" * 60)

# ----- FIX SUGGESTIONS -----
if errors or warnings:
    print("\n🔧 SUGGESTED FIXES:")
    
    if any("Core sections" in e or "Only" in e for e in errors):
        print("""
  CORE SECTIONS MISSING:
  The core_substrate_v7.usda file exists but its sections aren't
  being parsed. Check encoding (must be UTF-8) and check that
  def prims have the standard format:
    def "SectionName" ( doc = "..." ) { ... }
""")
    
    if any("graft" in w.lower() or "DigitalInjection" in w for w in warnings):
        print("""
  INJECTION GRAFT NOT LOADING:
  The graft file is in grafts/ and root.usda references it,
  but sections aren't being extracted. Possible causes:
    1. File encoding issue (save as UTF-8 without BOM)
    2. Sublayer path resolution issue (check path separators)
    3. Parser not finding def prims in the graft
""")
