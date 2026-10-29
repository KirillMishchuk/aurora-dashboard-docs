#!/usr/bin/env python3
"""Run a project skill in Claude Code and save the session logs afterwards.

    python3 .claude/scripts/skill_run.py create-plan 1388
    python3 .claude/scripts/skill_run.py review-and-comment-pr 1393 -- --model opus

Starts `claude "/<skill> <args>"` in the repo root as a normal interactive
session. When you quit Claude Code, every session log of this project that
was written during the run (more than one after /clear) is copied to
SAP/Claude outputs/<skill>/runs/ — after the process has exited, so the logs
are complete. Label: <first arg>-v<N>, N = next free number for that skill
(1388-v1, 1388-v2, ...); several sessions in one run -> 1388-v1a, 1388-v1b.
Per session: <label>-session.jsonl, <label>-session/ (subagent logs, tool
results, if present), <label>-meta.json (session id, time span, git state).

Save a past session (ran plain `claude`):
    python3 .claude/scripts/skill_run.py --save <skill> <label> [--last N]

Logs contain code and environment data: they stay in Claude outputs, never DOCS.
"""
import json, re, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()


def git(args, cwd):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def main_root():
    common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], HERE.parent)
    return Path(common).parent if common else HERE.parents[2]


ROOT = main_root()
SAP = ROOT.parent
PROJECT_LOGS = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(ROOT))


def runs_dir(skill):
    d = SAP / "Claude outputs" / skill / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def next_label(runs, base):
    nums = [int(m.group(1)) for p in runs.iterdir()
            if (m := re.match(rf"{re.escape(base)}-v(\d+)", p.name))]
    return f"{base}-v{max(nums, default=0) + 1}"


def time_span(path):
    first = last = None
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r'"timestamp"\s*:\s*"([^"]+)"', line)
            if m:
                first = first or m.group(1)
                last = m.group(1)
    return first, last


def save_one(log, runs, label, skill, command):
    for suffix in ("-session.jsonl", "-session", "-meta.json"):
        if (runs / f"{label}{suffix}").exists():
            sys.exit(f"refusing to overwrite {runs / (label + suffix)}")
    shutil.copy2(log, runs / f"{label}-session.jsonl")
    folder = log.with_suffix("")
    if folder.is_dir():
        shutil.copytree(folder, runs / f"{label}-session")
    first, last = time_span(log)
    meta = {
        "label": label, "skill": skill, "command": command,
        "session_id": log.stem, "started": first, "ended": last,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subagent_folder": folder.is_dir(),
        "repo": {"branch": git(["rev-parse", "--abbrev-ref", "HEAD"], ROOT),
                 "head": git(["rev-parse", "--short", "HEAD"], ROOT),
                 "origin_main": git(["rev-parse", "--short", "origin/main"], ROOT),
                 "dirty": bool(git(["status", "--porcelain"], ROOT))},
        "docs_head": git(["rev-parse", "--short", "HEAD"], SAP / "DOCS"),
    }
    (runs / f"{label}-meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {log.name} -> {runs / label}-session.jsonl")


def save_all(logs, skill, label, command):
    runs = runs_dir(skill)
    for i, log in enumerate(logs):
        save_one(log, runs, label if len(logs) == 1 else f"{label}{chr(ord('a') + i)}", skill, command)


def logs_since(t0):
    return sorted((p for p in PROJECT_LOGS.glob("*.jsonl") if p.stat().st_mtime >= t0),
                  key=lambda p: p.stat().st_mtime)


def run(argv):
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    argv = argv[:argv.index("--")] if "--" in argv else argv
    if not argv:
        sys.exit(__doc__)
    skill, args = argv[0], argv[1:]
    if not (ROOT / ".claude" / "skills" / skill / "SKILL.md").is_file():
        sys.exit(f"no project skill '{skill}' in {ROOT / '.claude/skills'}")
    label = next_label(runs_dir(skill), args[0] if args else "run")
    command = f"/{skill} {' '.join(args)}".strip()
    print(f"run {label}: claude \"{command}\"  (logs are saved when you quit)", flush=True)
    t0 = time.time() - 1
    subprocess.run(["claude", *extra, command], cwd=ROOT)
    logs = logs_since(t0)
    if not logs:
        sys.exit(f"no session log written in {PROJECT_LOGS} — nothing saved")
    save_all(logs, skill, label, command)


def save_past(argv):
    last = 1
    if "--last" in argv:
        i = argv.index("--last"); last = int(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    if len(argv) != 2:
        sys.exit("usage: skill_run.py --save <skill> <label> [--last N]")
    logs = sorted(PROJECT_LOGS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)[-last:]
    if not logs:
        sys.exit(f"no session logs in {PROJECT_LOGS}")
    save_all(logs, argv[0], argv[1], None)


if __name__ == "__main__":
    a = sys.argv[1:]
    save_past(a[1:]) if a[:1] == ["--save"] else run(a)
