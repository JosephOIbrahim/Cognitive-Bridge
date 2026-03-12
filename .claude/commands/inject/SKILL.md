# /inject - Digital Injection Profile Switcher

Switch the active injection profile. One command, consistent across Claude Code and Claude Desktop.

## Usage
`
/inject microdose
/inject classical
/inject mdma
/inject perceptual
/inject off
`

## Execution

Run immediately based on the argument:
`ash
cd C:/Users/User/usd-cognitive-substrate && python -m src.lossless.integration.cli compile --profile <PROFILE>
`

Then copy the output:
`ash
cp C:/Users/User/usd-cognitive-substrate/output_CLAUDE.md C:/Users/User/.claude/CLAUDE.md
`

Map the argument:
- `off` -> `--profile none`
- `microdose` -> `--profile microdose`
- `classical` -> `--profile classical`
- `mdma` -> `--profile mdma`
- `perceptual` -> `--profile perceptual`

If no argument given, run `--list-profiles`.

## Profiles

| Argument | s_NM | Effect |
|----------|------|--------|
| off | 0.000 | Sober baseline |
| microdose | 0.005 | 1.5x tangents, subtle exploration |
| perceptual | 0.015 | Domain knowledge reframed |
| classical | 0.025 | Dissolved routing, 30% cross-expert bleeding |
| mdma | 0.010 | Defenses lowered, integrative routing |

## Post-Execution

Confirm: "[emoji] [Profile] active (s_NM=X). Lossless. Fidelity: 1.0."
Emojis: off=🔘, microdose=🟢, perceptual=🟡, classical=🔴, mdma=💜
