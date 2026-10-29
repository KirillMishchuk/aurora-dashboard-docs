#!/usr/bin/env python3
"""Run /review-and-comment-pr in Claude Code and collect everything needed to analyse the run.

    python3 run_review.py 1393                      # run, then collect when you quit Claude Code
    python3 run_review.py 1393 -- --model opus      # after --: flags for `claude`
    python3 run_review.py --save 1393-v1 [--last N] # collect a session you ran with plain `claude`
    python3 run_review.py --pack 1393-v1            # tar.gz of a collected run, to carry it back

Layout (the folder holding this repo's clone is <parent>):

    <parent>/aurora-dashboard   app repo, the skill installed in .claude/
    <parent>/DOCS               this repo
    <parent>/review-runs/       created here: one folder per run, OUTSIDE both repos

Collected into <parent>/review-runs/<label>/ (label = <pr>-v<N>, N = next free number):

    session.jsonl, session/     the orchestrator log and its subagent logs + tool results
                                (several sessions after /clear: session-a.jsonl, session-b.jsonl, ...)
    run/<pr>-<sha8>/            the skill's run folder(s) named in the log (context, briefs, out/, findings, report)
    docs-status.txt, docs.diff  what the run changed in DOCS (report, index, FOLLOW-UPS), vs DOCS HEAD
    docs-files/                 copies of the changed/new DOCS files
    meta.json                   label, command, session ids, time span, claude version, git heads

Session logs contain code and environment data: they stay in review-runs/, never in DOCS (public).
"""
import json, re, shutil, subprocess, sys, tarfile, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()


def sh(args, cwd=None, timeout=20, strip=True):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout.strip() if strip else r.stdout) if r.returncode == 0 else None
    except Exception:
        return None


DOCS = Path(sh(["git", "rev-parse", "--show-toplevel"], HERE.parent) or HERE.parents[3])
PARENT = DOCS.parent
REPO = PARENT / "aurora-dashboard"
OUT = PARENT / "review-runs"
SKILL = "review-and-comment-pr"
PROJECT_LOGS = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(REPO))
RUN_RE = re.compile(r"runs/review-and-comment-pr/(\d+-[0-9a-f]{8})")


def next_label(base):
    OUT.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in OUT.iterdir() if (m := re.fullmatch(rf"{re.escape(base)}-v(\d+)", p.name))]
    return f"{base}-v{max(nums, default=0) + 1}"


def time_span(log):
    first = last = None
    with open(log, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r'"timestamp"\s*:\s*"([^"]+)"', line)
            if m:
                first = first or m.group(1)
                last = m.group(1)
    return first, last


def run_folders(logs):
    """Run folders the orchestrator named in its log (collect.py prints the path)."""
    names = []
    for log in logs:
        for m in RUN_RE.finditer(Path(log).read_text(encoding="utf-8", errors="ignore")):
            if m.group(1) not in names:
                names.append(m.group(1))
    return names


def collect(logs, label, command):
    dest = OUT / label
    if dest.exists():
        sys.exit(f"refusing to overwrite {dest}")
    dest.mkdir(parents=True)
    sessions = []
    for i, log in enumerate(logs):
        tag = "session" if len(logs) == 1 else f"session-{chr(ord('a') + i)}"
        shutil.copy2(log, dest / f"{tag}.jsonl")
        folder = log.with_suffix("")
        subagents_folder = folder / "subagents"

        # Check for subagents folder and wait briefly if the session just ended
        if not subagents_folder.exists() and folder.is_dir():
            # Race condition: subagents might still be writing
            time.sleep(1)

        if folder.is_dir():
            if not subagents_folder.exists() or not any(subagents_folder.iterdir()):
                print(f"warning: {folder} exists but subagents/ is missing or empty — copy manually from {folder}")
            shutil.copytree(folder, dest / tag)
        else:
            print(f"warning: session folder {folder} not found — subagent logs will be missing")

        first, last = time_span(log)
        sessions.append({"file": f"{tag}.jsonl", "session_id": log.stem, "started": first, "ended": last,
                         "subagent_folder": folder.is_dir()})
    runs = []
    for name in run_folders(logs):
        src = REPO / ".claude" / "runs" / SKILL / name
        if src.is_dir():
            shutil.copytree(src, dest / "run" / name, ignore=shutil.ignore_patterns("__pycache__"))
            runs.append(name)
        else:
            runs.append(f"{name} (named in the log, missing on disk)")
    status = sh(["git", "-c", "core.quotePath=false", "status", "--porcelain", "--untracked-files=all"], DOCS,
                strip=False) or ""
    (dest / "docs-status.txt").write_text(status, encoding="utf-8")
    (dest / "docs.diff").write_text((sh(["git", "diff", "HEAD"], DOCS) or "") + "\n", encoding="utf-8")
    for line in status.splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        src = DOCS / path
        if src.is_file():
            (dest / "docs-files" / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / "docs-files" / path)
    meta = {
        "label": label, "command": command, "sessions": sessions, "run_folders": runs,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claude_version": sh(["claude", "--version"]),
        "repo": {"path": str(REPO), "branch": sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], REPO),
                 "head": sh(["git", "rev-parse", "--short", "HEAD"], REPO),
                 "origin_main": sh(["git", "rev-parse", "--short", "origin/main"], REPO),
                 "dirty": bool(sh(["git", "status", "--porcelain"], REPO))},
        "docs_head": sh(["git", "rev-parse", "--short", "HEAD"], DOCS),
        "skill_synced_with_docs": skill_in_sync(),
    }
    (dest / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"collected {len(logs)} session(s), run folder(s) {runs or 'none'} -> {dest}")
    if not runs:
        print("warning: no run folder named in the log — did the skill reach collect.py?")


def skill_in_sync():
    """True if the installed skill, its three agents and the hook equal the copy in DOCS (the version the
    run should have used; settings are checked by sync_install.py)."""
    base = DOCS / "ToolDocs/claude-config/aurora-dashboard-config/.claude"
    src, dst = base / "skills" / SKILL, REPO / ".claude/skills" / SKILL
    if not (src.is_dir() and dst.is_dir()):
        return None
    files = lambda d: {p.relative_to(d): p.read_bytes() for p in d.rglob("*")  # noqa: E731
                       if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"}
    extra = [f"agents/{a}.md" for a in ("pr-reviewer", "external-api-checker", "security-reviewer")] \
        + ["hooks/check_report_md.py"]
    same = lambda a, b: a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()  # noqa: E731
    return files(src) == files(dst) and all(same(base / r, REPO / ".claude" / r) for r in extra)


def logs_since(t0):
    return sorted((p for p in PROJECT_LOGS.glob("*.jsonl") if p.stat().st_mtime >= t0), key=lambda p: p.stat().st_mtime)


def run(argv):
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    argv = argv[:argv.index("--")] if "--" in argv else argv
    if len(argv) != 1 or not argv[0].isdigit():
        sys.exit(__doc__)
    if not (REPO / ".claude/skills" / SKILL / "SKILL.md").is_file():
        sys.exit(f"skill not installed in {REPO}/.claude/skills/{SKILL} — see ../review-and-comment-pr-remote-setup.md")
    label = next_label(argv[0])
    command = f"/{SKILL} {argv[0]}"
    print(f"run {label}: claude \"{command}\" in {REPO} (collected when you quit Claude Code)", flush=True)
    t0 = time.time() - 1
    try:
        subprocess.run(["claude", "--add-dir", str(DOCS), *extra, command], cwd=REPO)
    except FileNotFoundError:
        sys.exit("`claude` not found on PATH")
    logs = logs_since(t0)
    if not logs:
        sys.exit(f"no session log written in {PROJECT_LOGS} — nothing collected")
    collect(logs, label, command)


def save_past(argv):
    last = 1
    if "--last" in argv:
        i = argv.index("--last")
        last = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1:
        sys.exit("usage: run_review.py --save <label> [--last N]")
    logs = sorted(PROJECT_LOGS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)[-last:]
    if not logs:
        sys.exit(f"no session logs in {PROJECT_LOGS}")
    collect(logs, argv[0], None)


def pack(argv):
    if len(argv) != 1 or not (OUT / argv[0]).is_dir():
        sys.exit(f"usage: run_review.py --pack <label>  (a folder in {OUT})")
    tgz = OUT / f"{argv[0]}.tar.gz"
    with tarfile.open(tgz, "w:gz") as t:
        t.add(OUT / argv[0], arcname=argv[0])
    print(f"packed -> {tgz} ({tgz.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    a = sys.argv[1:]
    {"--save": save_past, "--pack": pack}.get(a[0] if a else "", run)(a[1:] if a[:1] in (["--save"], ["--pack"]) else a)
