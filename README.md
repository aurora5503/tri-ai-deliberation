# tri-ai-deliberation

A Codex skill for stress-testing hard questions across three local CLIs in parallel:

- Codex: `gpt-5.4` with reasoning effort `high`
- Claude Code: `claude-sonnet-4-6` with effort `high`
- Gemini CLI: `gemini-3.1-pro-preview`

The skill runs one to three rounds of comparison, highlights the biggest disagreements, and then synthesizes a final answer.

## Included files

- `SKILL.md`: workflow and prompting guidance
- `scripts/query_panel.py`: parallel runner for Codex, Claude, and Gemini
- `agents/openai.yaml`: UI metadata for the skill

## Basic usage

From Codex, invoke the skill on a difficult question.

Direct script usage:

```powershell
$prompt = @'
Answer the question directly. State assumptions and uncertainty.
Question:
[your question here]
'@

$prompt | python scripts/query_panel.py --cwd "C:\path\to\workspace"
```

You can override the default models with:

- `--codex-model`
- `--codex-reasoning-effort`
- `--claude-model`
- `--claude-effort`
- `--gemini-model`
