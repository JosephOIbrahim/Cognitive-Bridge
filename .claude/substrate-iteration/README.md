# Substrate Iteration System

Autonomous evaluation and iteration for Cognitive Substrate v7.2.0.

## Setup

1. Unzip into your Claude Code project root (next to `.claude/`)
2. Verify paths in `scripts/substrate_deployer.py` → `DEFAULT_CONFIG`
3. That's it. Zero dependencies — pure Python 3.8+.

## Usage

### The One Command

**End a Claude Desktop session → copy the session capture block → run:**

```bash
# Paste capture from clipboard (Windows):
powershell Get-Clipboard | python auto.py

# Paste capture from clipboard (Mac):
pbpaste | python auto.py

# From a file:
python auto.py --capture path/to/session.txt

# Just re-evaluate existing captures:
python auto.py --skip-ingest
```

**Or double-click the launcher:**
- Windows: `substrate-iterate.bat`
- Mac/Linux: `./substrate-iterate.sh` (run `chmod +x` first)

The launcher auto-detects clipboard content. If it looks like a session capture, it ingests it. Otherwise it runs on existing captures.

### What Happens

1. **Ingest** — Saves your session capture with date stamp
2. **Evaluate** — Parses all captures, detects behavioral patterns, scores against current substrate
3. **Propose** — Generates one proposal per finding (severity-ranked)
4. **Review** — Presents each proposal interactively: `[y]es / [n]o / [s]kip / [q]uit`
5. **Apply** — Approved proposals deploy to USD source, backup created automatically

### Claude Code Integration

Tell Claude Code: "iterate on my substrate" — it reads `CLAUDE.md` in this folder and runs the pipeline, presenting proposals conversationally.

### Granular Commands

```bash
python iterate.py status              # What's in the system
python iterate.py evaluate            # Analyze only (no proposals)
python iterate.py propose             # Generate proposals
python iterate.py apply <id>          # Apply a proposal
python iterate.py rollback <backup>   # Undo a change
python review.py --list               # List pending proposals
python review.py --approve <id>       # Approve one (add --auto-apply)
python review.py --reject <id>        # Reject one
```

## Safety

- Every apply auto-backs up to `history/`
- Proposals require explicit approval — no auto-apply
- `python iterate.py rollback <backup_file>` to undo any change
- USD is source of truth; markdown is regenerated
