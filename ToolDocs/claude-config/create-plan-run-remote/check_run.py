#!/usr/bin/env python3
"""Mechanical checks of one collected /create-plan run (a folder made by run_plan.py).

    python3 check_run.py <parent>/plan-runs/1208-v1 > <parent>/plan-runs/1208-v1/checks.md

Reads session.jsonl (+ session/subagents/), run/<label>/ and docs-files/ and prints Markdown:
  1. Run facts       mode, task, lag, KB lag, images, review sources, original plan (context.json, written.json)
  2. Orchestrator    every tool call in order; plan.py results; what the skill says it must not do itself
  3. Agents          per agent: tool calls, save refusals (text), writes outside save, network, git state
  4. Results         plan.md re-checked by the skill's own checks; the plan file in DOCS (header, paths),
                     index row, FOLLOW-UPS, other DOCS changes
Every line marked [!] needs a look; the rest is context for the analysis. It judges nothing about whether the
plan is right — that is the analysing agent's job (README.md, step 4).
"""
import importlib.util, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve()
CFG = HERE.parent.parent
sys.path.insert(0, str(CFG / "cost-audit"))
sys.dont_write_bytecode = True
from audit_session import rows, tools, load_agents, describe  # noqa: E402

PLAN_PY = CFG / "aurora-dashboard-config" / ".claude" / "skills" / "create-plan" / "scripts" / "plan.py"
RUN_FILES = re.compile(r"runs/create-plan/[^/\s]+/(task\.md|plan\.md|github\.md|context\.json)")
WRITE_RE = re.compile(r"(?<![<>&0-9])>(?!&|\s*/dev/null)|\btee\b|\bsed\s+-i\b|\brm\b|\bmv\b|\bcp\b|open\([^)]*['\"][wa]['\"]")
GIT_STATE = re.compile(r"\bgit\s+(checkout|switch|reset|commit|push|stash|branch\s+-[dDmM]|update-ref|rebase|merge)\b")
NET_RE = re.compile(r"\b(curl|wget)\b")
# grep -r over a whole package or the repo root reaches dist/ and node_modules/ (C10); under src/ it doesn't
BROAD_GREP = re.compile(r"\bgrep\s+(-\w*\s+)*-\w*r\w*\b[^|;&]*\s(packages|apps|packages/[\w-]+|apps/[\w-]+)/?(\s|$|[|;&])")
OUTSIDE_RE = re.compile(r"(^|\s|['\"=])(/tmp/|/private/tmp/|~/|\$HOME/)")


def load_plan_py():
    if not PLAN_PY.is_file():
        return None
    spec = importlib.util.spec_from_file_location("plan_py", PLAN_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def out(s=""):
    print(s)


def bullet(s, warn=False):
    out(f"- {'[!] ' if warn else ''}{s}")


def first_line(t, n=200):
    t = (t or "").strip().replace("\n", " ⏎ ")
    return t[:n] + ("…" if len(t) > n else "")


def facts(run):
    out(f"\n## 1. Run facts — {run.name}\n")
    c = json.loads((run / "context.json").read_text(encoding="utf-8")) if (run / "context.json").is_file() else {}
    if not c:
        bullet("no context.json — collect didn't finish", True)
        return c
    bullet(f"mode {c.get('mode')} · {c.get('kind')} {c.get('number') or ''} · {c.get('title', '')}")
    bullet(f"links for write: issue {c.get('issue')}, pr {c.get('pr')}" + (f" · epic #{c['epic']}" if c.get("epic") else ""))
    bullet(f"git fetch: {'ok' if c.get('fetch_ok') else 'FAILED'}", not c.get("fetch_ok"))
    bullet(f"code behind origin/main: {c.get('behind')} · KB pin {c.get('kb_pin')}, {c.get('kb_lag')} commits behind")
    imgs = sorted((run / "images").glob("*")) if (run / "images").is_dir() else []
    task = (run / "task.md").read_text(encoding="utf-8") if (run / "task.md").is_file() else ""
    nd = task.count("- not downloaded:")
    bullet(f"images: {len(imgs)} downloaded, {nd} not downloaded", nd > 0)
    if c.get("mode") == "B":
        for r in c.get("reviews", []):
            bullet(f"review source: {r['source']} ({r['date']}, {r['size']})")
        bullet(f"original plan: {c.get('original_plan') or 'not unique: ' + str(c.get('original_plan_candidates'))}")
        bullet(f"fixes file: {c.get('fixes_file') or 'none (round 1)'}")
    w = run / "written.json"
    if w.is_file():
        bullet(f"written: {json.loads(w.read_text(encoding='utf-8'))}")
    else:
        bullet("no written.json — `plan.py write` didn't run (or failed)", True)
    return c


def orchestrator(all_rows, name, ctx):
    out(f"\n## 2. Orchestrator — {name}\n")
    calls = tools(all_rows)
    planners = reviewers = asks = 0
    followups_args = []
    for b, res, err, ts, _ in calls:
        n, d = b["name"], describe(b)
        t = (ts or "")[11:19]
        warn, why = False, ""
        if n == "Bash":
            if "plan.py" in d:
                sub = re.search(r"plan\.py\s+(\w+)", d)
                sub = sub.group(1) if sub else "?"
                bad = err or bool(re.search(r"^(NOT saved|.*doesn't exist|.*needs --|.*: give exactly|replay:)", res or "", re.M))
                bullet(f"{t} plan.py {sub}: {'exit≠0 · ' if err else ''}{first_line(res, 160)}", bad)
                if sub == "followups":
                    followups_args.append(d)
                continue
            if re.search(r"(^|\s)gh\s", d):
                warn, why = True, "gh itself (collect does it)"
            elif re.search(r"\bgit\s", d):
                warn, why = True, "git itself (collect/write do it)"
            elif NET_RE.search(d):
                warn, why = True, "network itself"
            elif RUN_FILES.search(d):
                warn, why = True, "reads a run file (task.md/plan.md/github.md/context.json) — the skill says don't"
            elif "FOLLOW-UPS.md" in d and "awk" not in d:
                warn, why = True, "touches FOLLOW-UPS.md beyond the one-item awk"
            elif WRITE_RE.search(d):
                warn, why = True, "writes a file itself"
        elif n == "Read":
            if RUN_FILES.search(d) or re.search(r"DOCS/(plans/|FOLLOW-UPS\.md)", d):
                warn, why = True, "reads a run file / plan / registry itself"
        elif n in ("Write", "Edit"):
            warn, why = True, "writes a file itself (write/followups do it)"
        elif n in ("Agent", "Task"):
            i = b.get("input") or {}
            if i.get("subagent_type") == "dev-planner":
                planners += 1
            if i.get("subagent_type") == "plan-reviewer":
                reviewers += 1
            if i.get("run_in_background"):
                warn, why = True, "launched in background"
            p = i.get("prompt", "")
            if i.get("subagent_type") == "dev-planner":
                if "task.md" not in p:
                    warn, why = True, "planner not given task.md"
                if "plan.py save" not in p and "plan.py" not in p:
                    warn, why = True, "planner not given the save command"
                if len(p) > 6000:
                    warn, why = True, f"prompt {len(p)} chars — task pasted instead of the path?"
        elif n == "AskUserQuestion":
            asks += 1
        bullet(f"{t} {n}: {first_line(d, 160)}" + (f" — {why}" if why else ""), warn)
    out("")
    bullet(f"dev-planner launches: {planners}", planners != 1)
    if planners > 1:
        bullet("more than one planner — the skill continues the same one with SendMessage unless it can't", True)
    bullet(f"plan-reviewer launches: {reviewers}", reviewers > 1)
    bullet(f"AskUserQuestion calls: {asks}")
    for d in followups_args:
        if "--file" in d:
            bullet("followups filed items on this machine — the remote rule is --skip for every candidate", True)
    sent = sum(1 for b, *_ in calls if b["name"] == "SendMessage")
    bullet(f"SendMessage calls: {sent}")


def agents(sdir):
    out("\n## 3. Agents\n")
    for atype, desc, arows in load_agents(sdir):
        calls = tools(arows)
        reqs = len({(d.get("requestId") or (d.get("message") or {}).get("id")) for d in arows if d.get("type") == "assistant"})
        out(f"### {atype} — {desc}\n")
        bullet(f"{reqs} requests, {len(calls)} tool calls")
        saves = 0
        fetches = []
        for b, res, err, ts, _ in calls:
            n, d = b["name"], describe(b)
            t = (ts or "")[11:19]
            if n == "Bash" and "plan.py save" in d:
                saves += 1
                ok = (res or "").startswith("saved ")
                bullet(f"{t} save: {first_line(res, 200)}", not ok)
                if re.search(r"<\s*/(tmp|private)", d) or "--replace" in d:
                    bullet(f"{t} save from a file / --replace: {first_line(d, 120)}", "/tmp" in d)
                continue
            if n in ("WebFetch", "WebSearch"):
                fetches.append(((b.get('input') or {}).get('url') or (b.get('input') or {}).get('query', '')) + (" (error)" if err else ""))
                continue
            if n in ("Write", "Edit"):
                bullet(f"{t} {n} {d} — agents only read", True)
            elif n == "Bash":
                if GIT_STATE.search(d):
                    bullet(f"{t} touches git state: {first_line(d, 140)}", True)
                if NET_RE.search(d):
                    bullet(f"{t} network from Bash: {first_line(d, 140)}", True)
                if WRITE_RE.search(d) or OUTSIDE_RE.search(d):
                    bullet(f"{t} writes or works outside the repo/DOCS/run folder: {first_line(d, 160)}", True)
                if BROAD_GREP.search(d) and "--exclude-dir" not in d:
                    bullet(f"{t} recursive grep over packages/ without --exclude-dir (dist/, node_modules/ — C10): {first_line(d, 120)}")
            elif n == "Read" and re.search(r"^(/tmp|/private/tmp)", d):
                bullet(f"{t} reads /tmp: {d}", True)
            if err:
                bullet(f"{t} {n} error: {first_line(res, 140)}")
        if atype == "dev-planner":
            bullet(f"save calls: {saves}", saves == 0)
            hand = [(b.get("input") or {}).get("message", "") for b, *_ in calls if b["name"] == "SubagentHandback"]
            for h in hand:
                ok = h.startswith("saved ") or h.startswith("## Decisions needed")
                bullet(f"reply: {first_line(h, 160)}", not ok)
        if fetches:
            bullet("web: " + "; ".join(first_line(f, 90) for f in fetches))
        out("")


def results(folder, run, ctx):
    out("\n## 4. Results\n")
    m = load_plan_py()
    p = run / "plan.md" if run else None
    if p and p.is_file() and m:
        errs, info = m.analyse(p.read_text(encoding="utf-8").strip("\n"))
        bullet(f"plan.md (skill's own checks): {m.summary(info) if not errs else ''}", bool(errs))
        for e in errs:
            bullet(e, True)
    elif not m:
        bullet(f"can't load {PLAN_PY} — plan.md not re-checked", True)
    status = (folder / "docs-status.txt").read_text(encoding="utf-8") if (folder / "docs-status.txt").is_file() else ""
    changed = [l[3:].strip('"') for l in status.splitlines()]
    plans = [c for c in changed if re.match(r"plans/\d{4}-\d{2}-\d{2}-.*\.md$", c)]
    for c in changed:
        bullet(f"DOCS changed: {c}", c == "FOLLOW-UPS.md")
    if "FOLLOW-UPS.md" in changed:
        bullet("FOLLOW-UPS.md changed on this machine — numbers will collide with the main machine", True)
    if "plans/README.md" not in changed:
        bullet("plans/README.md unchanged — no index row?", True)
    for c in plans:
        f = folder / "docs-files" / c
        if not f.is_file():
            continue
        t = f.read_text(encoding="utf-8")
        head = "\n".join(t.split("\n")[:14])
        base = re.search(r"^\*\*Base:\*\* (.*)$", t, re.M)
        bullet(f"{c}: Base {base.group(1) if base else 'MISSING'}", not base)
        if re.search(r"(^|\s)(/Users/|/home/)", t):
            bullet(f"{c}: home-directory path in the plan", True)
        if "## Proposed follow-ups" in t or "### Proposed follow-ups" in t:
            bullet(f"{c}: still has `Proposed follow-ups` — step 6 didn't run", True)
        if re.search(r"^status: analysis", head, re.M):
            bullet(f"{c}: status analysis (no implementation steps)")
    idx = folder / "docs-files" / "plans" / "README.md"
    if idx.is_file():
        for c in plans:
            row = next((l for l in idx.read_text(encoding="utf-8").splitlines() if f"](./{Path(c).name})" in l), None)
            bullet(f"index row: {first_line(row, 220) if row else 'MISSING'}", not row or bool(row and re.search(r"[.;]; \d+ steps", row)))


def main(folder):
    folder = Path(folder)
    logs = sorted(folder.glob("session*.jsonl"))
    if not logs:
        sys.exit(f"no session*.jsonl in {folder}")
    runs = sorted((folder / "run").glob("*")) if (folder / "run").is_dir() else []
    out(f"# Checks — {folder.name}")
    out(f"\nSessions: {', '.join(p.name for p in logs)} · run folders: {', '.join(r.name for r in runs) or 'none'}")
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8")) if (folder / "meta.json").is_file() else {}
    if meta:
        bullet(f"skill in sync with DOCS: {meta.get('skill_synced_with_docs')}", meta.get("skill_synced_with_docs") is not True)
        bullet(f"repo: {meta.get('repo')}")
    ctx = {}
    for r in runs:
        ctx = facts(r)
    for log in logs:
        orchestrator(list(rows(log)), log.name, ctx)
        agents(log.with_suffix(""))
    results(folder, runs[-1] if runs else None, ctx)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
