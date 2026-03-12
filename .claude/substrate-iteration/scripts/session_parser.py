"""
session_parser.py — Parse session capture blocks into structured JSON.

Session captures come from Claude Desktop conversations. They're ASCII
text blocks with a known format (defined in the Substrate's Session Capture Block).

This parser extracts:
- Goal, progress, position
- Active reasoning trace
- Task tree state (AND/OR decomposition)
- Momentum/energy/burnout state
- Expert activations and outcomes
- Novel signal fingerprints
- Parked ideas
- Any freeform notes

It also detects patterns ACROSS multiple captures:
- Recurring crash triggers
- Expert success/failure rates
- Momentum patterns
- Emerging fast-path candidates
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class SessionCapture:
    """Structured representation of one session capture block."""
    date: str = ""
    goal: str = ""
    progress: list = field(default_factory=list)
    stopped_at: str = ""
    active_reasoning: str = ""
    task_tree: str = ""
    novel_signals: list = field(default_factory=list)
    next_steps: list = field(default_factory=list)
    momentum: str = ""
    energy: str = ""
    burnout: str = ""
    note_to_future: str = ""
    parked_ideas: list = field(default_factory=list)
    # Extracted behavioral signals (inferred from content)
    expert_activations: list = field(default_factory=list)
    crash_events: list = field(default_factory=list)
    stuck_events: list = field(default_factory=list)
    burst_events: list = field(default_factory=list)
    constitutional_notes: list = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "goal": self.goal,
            "progress": self.progress,
            "stopped_at": self.stopped_at,
            "active_reasoning": self.active_reasoning,
            "task_tree": self.task_tree,
            "novel_signals": self.novel_signals,
            "next_steps": self.next_steps,
            "state": {
                "momentum": self.momentum,
                "energy": self.energy,
                "burnout": self.burnout,
            },
            "note_to_future": self.note_to_future,
            "parked_ideas": self.parked_ideas,
            "behavioral_signals": {
                "expert_activations": self.expert_activations,
                "crash_events": self.crash_events,
                "stuck_events": self.stuck_events,
                "burst_events": self.burst_events,
                "constitutional_notes": self.constitutional_notes,
            },
        }


@dataclass
class SessionAnalysis:
    """Aggregated analysis across multiple sessions."""
    session_count: int = 0
    date_range: tuple = ("", "")
    # Frequency maps
    expert_frequency: dict = field(default_factory=dict)     # expert -> count
    crash_trigger_frequency: dict = field(default_factory=dict)  # trigger -> count
    stuck_type_frequency: dict = field(default_factory=dict)     # type -> count
    momentum_patterns: list = field(default_factory=list)
    novel_signals_accumulated: list = field(default_factory=list)
    recurring_goals: dict = field(default_factory=dict)      # goal_keyword -> count
    # Derived insights
    insights: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_count": self.session_count,
            "date_range": list(self.date_range),
            "expert_frequency": self.expert_frequency,
            "crash_trigger_frequency": self.crash_trigger_frequency,
            "stuck_type_frequency": self.stuck_type_frequency,
            "momentum_patterns": self.momentum_patterns,
            "novel_signals_accumulated": self.novel_signals_accumulated,
            "recurring_goals": self.recurring_goals,
            "insights": self.insights,
        }


# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_capture(text: str) -> SessionCapture:
    """Parse a single session capture block into structured data."""
    cap = SessionCapture(raw_text=text)
    
    # Extract date — handle box-format dashes, em-dashes, and plain dates
    date_match = re.search(r'SESSION CAPTURE\s*[-—–]+\s*(\d{4}-\d{2}-\d{2})', text)
    if date_match:
        cap.date = date_match.group(1)
    else:
        # Try ISO date anywhere in first 5 lines
        first_lines = "\n".join(text.split("\n")[:5])
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', first_lines)
        if date_match:
            cap.date = date_match.group(1)
    
    # Section extraction (handles both box-format and plain-format captures)
    cap.goal = _extract_section(text, r'Goal:', r'\n(?:\||[A-Z])') or ""
    cap.stopped_at = _extract_section(text, r'Stopped at:', r'\n(?:\||[A-Z])') or ""
    cap.active_reasoning = _extract_section(text, r'Active reasoning:', r'\n(?:\||[A-Z])') or ""
    cap.task_tree = _extract_section(text, r'Task tree state:', r'\n(?:\||[A-Z])') or ""
    cap.note_to_future = _extract_section(text, r'Note to future self:', r'\n(?:\||[A-Z]|\+)') or ""
    
    # Progress (bullet list)
    progress_block = _extract_section(text, r'Progress:', r'\n(?:\||Stopped|Active|Task tree)')
    if progress_block:
        cap.progress = [line.strip().lstrip('•-* ') for line in progress_block.split('\n') if line.strip() and line.strip() not in ('|', '')]
    
    # Next steps (bullet list)
    next_block = _extract_section(text, r'Next steps:', r'\n(?:\||State|Note)')
    if next_block:
        cap.next_steps = [line.strip().lstrip('•-* ') for line in next_block.split('\n') if line.strip() and line.strip() not in ('|', '')]
    
    # Parked ideas
    parked_block = _extract_section(text, r'(?:Parked ideas|Ideas parked):', r'\n(?:\+|$)')
    if parked_block:
        cap.parked_ideas = [line.strip().lstrip('•-* ') for line in parked_block.split('\n') if line.strip() and line.strip() not in ('|', '')]
    
    # State line: momentum | energy | burnout
    # Handle both "State: crashed | depleted | ORANGE" and box-format with leading/trailing pipes
    state_match = re.search(r'State:\s*(.+)', text)
    if state_match:
        raw = state_match.group(1).strip().rstrip('|').strip()
        parts = [p.strip() for p in raw.split('|') if p.strip()]
        if len(parts) >= 1:
            cap.momentum = parts[0].strip()
        if len(parts) >= 2:
            cap.energy = parts[1].strip()
        if len(parts) >= 3:
            cap.burnout = parts[2].strip()
    
    # Novel signal fingerprints
    novel_block = _extract_section(text, r'Novel signal fingerprints:', r'\n(?:\||Next|State)')
    if novel_block:
        cap.novel_signals = [line.strip().lstrip('•-* ') for line in novel_block.split('\n') if line.strip() and line.strip() not in ('|', '')]
    
    # ── Behavioral signal extraction (pattern matching on full text) ──
    cap.expert_activations = _detect_experts(text)
    cap.crash_events = _detect_crashes(text)
    cap.stuck_events = _detect_stuck(text)
    cap.burst_events = _detect_bursts(text)
    cap.constitutional_notes = _detect_constitutional(text)
    
    return cap


def _extract_section(text: str, start_pattern: str, end_pattern: str) -> Optional[str]:
    """Extract text between a section header and the next section."""
    match = re.search(start_pattern, text, re.IGNORECASE)
    if not match:
        return None
    
    start = match.end()
    remaining = text[start:]
    
    end_match = re.search(end_pattern, remaining)
    if end_match:
        content = remaining[:end_match.start()]
    else:
        content = remaining
    
    # Clean up box-drawing characters and extra whitespace
    content = re.sub(r'[│|]', '', content)
    content = content.strip()
    return content if content else None


# ── Behavioral Signal Detection ──────────────────────────────────────────────

EXPERT_KEYWORDS = {
    "Validator": ["frustrated", "empathy", "emotional", "acknowledged", "validated"],
    "Scaffolder": ["broke down", "decomposed", "scaffolded", "step by step", "simplified"],
    "Restorer": ["rest", "break", "permission", "depleted", "enough for today"],
    "Direct": ["burst", "flow", "terse", "rapid", "minimal"],
    "Socratic": ["explored", "what if", "tangent", "followed thread", "brainstorm"],
    "Grounding": ["physics", "simulation", "calculate", "verify", "oracle"],
}

def _detect_experts(text: str) -> list:
    """Detect which experts were likely activated based on keywords."""
    text_lower = text.lower()
    activated = []
    for expert, keywords in EXPERT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits >= 2:
            activated.append({"expert": expert, "confidence": "high", "keyword_hits": hits})
        elif hits == 1:
            activated.append({"expert": expert, "confidence": "low", "keyword_hits": hits})
    return activated


CRASH_KEYWORDS = [
    "crashed", "gave up", "stopped", "couldn't continue", "hit a wall",
    "frustrat", "overwhelm", "too much", "can't do this", "done for today",
    "RED", "spiral", "stuck"
]

def _detect_crashes(text: str) -> list:
    """Detect crash events."""
    text_lower = text.lower()
    events = []
    for kw in CRASH_KEYWORDS:
        if kw.lower() in text_lower:
            events.append({"keyword": kw, "context": _get_context(text, kw)})
    return events


STUCK_KEYWORDS = {
    "confused": ["don't understand", "unclear", "confused", "lost"],
    "overwhelmed": ["too much", "overwhelmed", "can't process"],
    "avoidance": ["avoiding", "later", "don't want to", "procrastinat"],
    "perfectionism": ["one more", "almost", "not quite", "polish"],
    "energy": ["tired", "depleted", "low energy", "can't focus"],
    "fear": ["what if it breaks", "afraid", "hesitat", "risky"],
}

def _detect_stuck(text: str) -> list:
    """Detect stuck events and classify type."""
    text_lower = text.lower()
    events = []
    for stuck_type, keywords in STUCK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                events.append({"type": stuck_type, "keyword": kw, "context": _get_context(text, kw)})
                break  # One hit per type
    return events


def _detect_bursts(text: str) -> list:
    """Detect burst/hyperfocus events."""
    text_lower = text.lower()
    events = []
    burst_kw = ["burst", "hyperfocus", "flow state", "rapid-fire", "rolling", "peak"]
    for kw in burst_kw:
        if kw in text_lower:
            events.append({"keyword": kw, "context": _get_context(text, kw)})
    return events


def _detect_constitutional(text: str) -> list:
    """Detect mentions of constitutional constraints (violations or successes)."""
    text_lower = text.lower()
    events = []
    const_kw = [
        "talked down", "already told", "sycophant", "single source",
        "pushed to keep going", "unsolicited advice", "over-explain",
        "performed helpfulness"
    ]
    for kw in const_kw:
        if kw in text_lower:
            events.append({"constraint": kw, "context": _get_context(text, kw)})
    return events


def _get_context(text: str, keyword: str, window: int = 80) -> str:
    """Get surrounding context for a keyword match."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    return text[start:end].replace('\n', ' ').strip()


# ── Aggregation ──────────────────────────────────────────────────────────────

def analyze_sessions(captures: list) -> SessionAnalysis:
    """Aggregate patterns across multiple parsed session captures."""
    analysis = SessionAnalysis()
    analysis.session_count = len(captures)
    
    dates = [c.date for c in captures if c.date]
    if dates:
        analysis.date_range = (min(dates), max(dates))
    
    for cap in captures:
        # Expert frequency
        for ea in cap.expert_activations:
            expert = ea["expert"]
            analysis.expert_frequency[expert] = analysis.expert_frequency.get(expert, 0) + 1
        
        # Crash triggers
        for ce in cap.crash_events:
            kw = ce["keyword"]
            analysis.crash_trigger_frequency[kw] = analysis.crash_trigger_frequency.get(kw, 0) + 1
        
        # Stuck types
        for se in cap.stuck_events:
            st = se["type"]
            analysis.stuck_type_frequency[st] = analysis.stuck_type_frequency.get(st, 0) + 1
        
        # Momentum
        if cap.momentum:
            analysis.momentum_patterns.append({
                "date": cap.date,
                "final_state": cap.momentum,
                "had_crash": len(cap.crash_events) > 0,
                "had_burst": len(cap.burst_events) > 0,
            })
        
        # Novel signals
        analysis.novel_signals_accumulated.extend(cap.novel_signals)
        
        # Goal keywords
        if cap.goal:
            words = re.findall(r'\b\w{4,}\b', cap.goal.lower())
            for w in words:
                analysis.recurring_goals[w] = analysis.recurring_goals.get(w, 0) + 1
    
    # ── Derive insights ──
    
    # High-frequency crash triggers
    for trigger, count in sorted(analysis.crash_trigger_frequency.items(), key=lambda x: -x[1]):
        if count >= 2:
            analysis.insights.append({
                "type": "recurring_crash_trigger",
                "detail": f"'{trigger}' appeared in {count}/{len(captures)} sessions",
                "severity": "high" if count >= 3 else "medium",
            })
    
    # Expert imbalance
    if analysis.expert_frequency:
        max_expert = max(analysis.expert_frequency, key=analysis.expert_frequency.get)
        max_count = analysis.expert_frequency[max_expert]
        if max_count > len(captures) * 0.6:
            analysis.insights.append({
                "type": "expert_overuse",
                "detail": f"{max_expert} activated in {max_count}/{len(captures)} sessions — possible routing over-reliance",
                "severity": "low",
            })
    
    # Accumulated novel signals (candidates for new fast-paths)
    if len(analysis.novel_signals_accumulated) >= 3:
        analysis.insights.append({
            "type": "novel_signal_accumulation",
            "detail": f"{len(analysis.novel_signals_accumulated)} novel signals accumulated — review for fast-path promotion",
            "severity": "medium",
        })
    
    return analysis


# ── File I/O ─────────────────────────────────────────────────────────────────

def parse_capture_file(filepath: str) -> SessionCapture:
    """Parse a single capture file."""
    text = Path(filepath).read_text(encoding="utf-8")
    return parse_capture(text)


def parse_capture_dir(dirpath: str) -> list:
    """Parse all .txt files in a directory."""
    captures = []
    for f in sorted(Path(dirpath).glob("*.txt")):
        try:
            captures.append(parse_capture_file(str(f)))
        except Exception as e:
            print(f"Warning: Could not parse {f.name}: {e}")
    return captures


def save_analysis(analysis: SessionAnalysis, filepath: str):
    """Save analysis to JSON."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    Path(filepath).write_text(json.dumps(analysis.to_dict(), indent=2), encoding="utf-8")


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: session_parser.py <captures_dir>")
        print("       session_parser.py <single_file.txt>")
        sys.exit(1)
    
    target = Path(sys.argv[1])
    
    if target.is_dir():
        captures = parse_capture_dir(str(target))
        print(f"Parsed {len(captures)} session captures.")
        
        if captures:
            analysis = analyze_sessions(captures)
            out_path = target / "_analysis.json"
            save_analysis(analysis, str(out_path))
            print(f"Analysis saved to {out_path}")
            print(f"\nInsights ({len(analysis.insights)}):")
            for ins in analysis.insights:
                print(f"  [{ins['severity']}] {ins['type']}: {ins['detail']}")
    
    elif target.is_file():
        cap = parse_capture_file(str(target))
        print(json.dumps(cap.to_dict(), indent=2))
    
    else:
        print(f"Not found: {target}")
        sys.exit(1)
