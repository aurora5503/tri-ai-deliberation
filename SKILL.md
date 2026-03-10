---
name: tri-cli-deliberation
description: Use when the user wants a difficult question stress-tested across the local Codex CLI, Claude Code CLI, and Gemini CLI, with one to three rounds of comparison focused on factual and logical disagreements before you synthesize the final answer.
---

# Tri CLI Deliberation

## When To Use

Use this skill when the user explicitly asks you to consult local `codex`, `claude`, and `gemini` CLIs, or when the question is hard enough that cross-checking competing answers would materially improve the result.

Prefer a normal answer for simple requests unless the user clearly wants multi-model deliberation.

## Workflow

1. Restate the question into a neutral panel prompt.
2. Ask all three local CLIs for an initial answer with the bundled script.
3. Compare the answers yourself. Focus on the largest disagreements in:
   - factual claims
   - hidden assumptions or definitions
   - logical steps that drive the conclusion
   - uncertainty, confidence, or missing caveats
4. Write a targeted follow-up prompt that presents the strongest disagreements and asks each model to:
   - defend or revise its position
   - identify which claim is most uncertain
   - say what evidence or reasoning would change its mind
5. Run a second round with the same script.
6. Run a third round only if a material disagreement remains on logic or facts.
7. Produce the final answer yourself. Do not dump raw model outputs without synthesis.

## Helper Script

Use the bundled script to query the three CLIs in parallel:

```powershell
$prompt = @'
[your panel prompt here]
'@
$prompt | python C:\Users\snes5\.codex\skills\tri-cli-deliberation\scripts\query_panel.py --cwd "C:\path\to\workspace"
```

Current script defaults:

- `codex`: `gpt-5.4` with reasoning effort `high`
- `claude`: `claude-sonnet-4-6` with effort `high`
- `gemini`: `gemini-3.1-pro-preview`

Override them when needed:

```powershell
$prompt | python C:\Users\snes5\.codex\skills\tri-cli-deliberation\scripts\query_panel.py `
  --cwd "C:\path\to\workspace" `
  --codex-model gpt-5.4 `
  --codex-reasoning-effort high `
  --claude-model claude-sonnet-4-6 `
  --claude-effort high `
  --gemini-model gemini-3.1-pro-preview
```

The script prints JSON with one entry per model. Each entry includes `ok`, `answer`, `duration_sec`, and failure details when applicable.

If one CLI fails, continue with the remaining results and note the missing source in the final answer.

## Prompting Pattern

For round 1, keep the prompt neutral and direct. Include:

- the user question
- any important constraints
- the desired output format
- a request to state assumptions and uncertainty

Use wording like this:

```text
Answer the question directly. Focus on factual accuracy and logical soundness.
State key assumptions, note uncertainty, and avoid using local files or tools unless the prompt explicitly requires them.
Question:
[user question]
```

For follow-up rounds, show only the highest-signal disagreements. Ask the models to respond to each disagreement explicitly instead of re-answering from scratch.

## Final Output Requirements

Your final response to the user should include:

1. A short outline of the deliberation flow by round
2. The biggest disagreements and whether they were resolved
3. A synthesized final answer in your own words
4. Remaining uncertainty or verification notes when unresolved

Keep the final answer readable. Summarize raw model outputs instead of pasting them in full unless the user asks for the full transcripts.
