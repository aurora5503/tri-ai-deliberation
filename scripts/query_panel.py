#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Query local Codex, Claude Code, and Gemini CLIs in parallel."
    )
    parser.add_argument("--cwd", default=os.getcwd(), help="Working directory for all CLI calls.")
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=240,
        help="Per-model timeout in seconds. Default: 240.",
    )
    parser.add_argument(
        "--models",
        default="codex,claude,gemini",
        help="Comma-separated subset of models to query.",
    )
    parser.add_argument(
        "--codex-model",
        default="gpt-5.4",
        help="Codex model name. Default: gpt-5.4.",
    )
    parser.add_argument(
        "--codex-reasoning-effort",
        default="high",
        help="Codex reasoning effort. Default: high.",
    )
    parser.add_argument(
        "--claude-model",
        default="claude-sonnet-4-6",
        help="Claude model name. Default: claude-sonnet-4-6.",
    )
    parser.add_argument(
        "--claude-effort",
        default="high",
        help="Claude effort level. Default: high.",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-3.1-pro-preview",
        help="Gemini model name. Default: gemini-3.1-pro-preview.",
    )
    return parser.parse_args()


def read_prompt():
    prompt = sys.stdin.read()
    if not prompt.strip():
        raise SystemExit("Prompt required on stdin.")
    return prompt


def resolve_command(*candidates):
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def parse_first_json_blob(text):
    payload = text.lstrip()
    if not payload:
        raise ValueError("empty output")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(payload)
    return obj


def parse_codex_output(stdout_text):
    last_text = None
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict):
            if item.get("type") == "agent_message" and item.get("text"):
                last_text = item["text"]
    if not last_text:
        raise ValueError("unable to find agent message in codex output")
    return last_text


def build_commands(args):
    return {
        "codex": {
            "path": resolve_command("codex.cmd", "codex"),
            "argv": [
                "exec",
                "--model",
                args.codex_model,
                "-c",
                f'model_reasoning_effort="{args.codex_reasoning_effort}"',
                "-s",
                "read-only",
                "--skip-git-repo-check",
                "--ephemeral",
                "--json",
                "--color",
                "never",
                "-",
            ],
            "parser": lambda stdout: {"answer": parse_codex_output(stdout)},
        },
        "claude": {
            "path": resolve_command("claude.exe", "claude"),
            "argv": [
                "-p",
                "--model",
                args.claude_model,
                "--effort",
                args.claude_effort,
                "--tools",
                "",
                "--output-format",
                "json",
                "--permission-mode",
                "plan",
                "--no-session-persistence",
            ],
            "parser": lambda stdout: {"answer": parse_first_json_blob(stdout)["result"]},
        },
        "gemini": {
            "path": resolve_command("gemini.cmd", "gemini"),
            "argv": [
                "-p",
                "",
                "-m",
                args.gemini_model,
                "-o",
                "json",
            ],
            "parser": lambda stdout: {"answer": parse_first_json_blob(stdout)["response"]},
        },
    }


def shorten(text, limit=2000):
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def clean_stderr(text):
    ignored_fragments = (
        "shell snapshot not supported yet for PowerShell",
        "Loaded cached credentials.",
    )
    kept = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if any(fragment.lower() in lowered for fragment in ignored_fragments):
            continue
        kept.append(line)
    return "\n".join(kept)


def run_one(name, config, prompt, cwd, timeout_sec):
    started = time.perf_counter()
    if not config["path"]:
        return {
            "ok": False,
            "error": f"{name} command not found on PATH",
            "duration_sec": round(time.perf_counter() - started, 3),
        }

    try:
        proc = subprocess.run(
            [config["path"], *config["argv"]],
            input=prompt,
            text=True,
            capture_output=True,
            cwd=cwd,
            timeout=timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"{name} timed out after {timeout_sec} seconds",
            "duration_sec": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{name} failed to start: {exc}",
            "duration_sec": round(time.perf_counter() - started, 3),
        }

    duration = round(time.perf_counter() - started, 3)

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"{name} exited with code {proc.returncode}",
            "stdout": shorten(proc.stdout),
            "stderr": shorten(proc.stderr),
            "duration_sec": duration,
        }

    try:
        parsed = config["parser"](proc.stdout)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{name} output parse failed: {exc}",
            "stdout": shorten(proc.stdout),
            "stderr": shorten(proc.stderr),
            "duration_sec": duration,
        }

    result = {
        "ok": True,
        "answer": parsed["answer"].strip(),
        "duration_sec": duration,
    }
    stderr_text = clean_stderr(proc.stderr)
    if stderr_text:
        result["stderr"] = shorten(stderr_text, limit=800)
    return result


def main():
    args = parse_args()
    prompt = read_prompt()
    cwd = str(Path(args.cwd).resolve())
    requested = [item.strip() for item in args.models.split(",") if item.strip()]
    commands = build_commands(args)

    unknown = [name for name in requested if name not in commands]
    if unknown:
        raise SystemExit(f"Unknown model name(s): {', '.join(unknown)}")

    results = {}
    with ThreadPoolExecutor(max_workers=len(requested) or 1) as executor:
        future_map = {
            executor.submit(run_one, name, commands[name], prompt, cwd, args.timeout_sec): name
            for name in requested
        }
        for future in as_completed(future_map):
            name = future_map[future]
            results[name] = future.result()

    ordered_results = {name: results[name] for name in requested}
    payload = {
        "cwd": cwd,
        "models": ordered_results,
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
