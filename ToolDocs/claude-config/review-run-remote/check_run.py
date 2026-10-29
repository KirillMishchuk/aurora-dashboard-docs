#!/usr/bin/env python3
"""Mechanical checks of one collected /review-and-comment-pr run (a folder made by run_review.py).

    python3 check_run.py <parent>/review-runs/1393-v1 > <parent>/review-runs/1393-v1/checks.md

Reads session.jsonl (+ session/subagents/) and run/<pr>-<sha8>/ and prints Markdown:
  1. Run facts       mode, delta, base changes removed, flags, discussion, provenance notes
  2. Orchestrator    the scripts it ran (exit codes), agents it launched vs the lists briefs.py printed,
                     files it read/wrote, commands the skill's hard rules forbid it
  3. Agents          per agent: role, tool calls, save.py refusals (text), rule breaks, network calls
  4. Results         out/*.json present per brief; findings, earlier statuses, dismissed, Process
  5. Report text     leaks of internal names/placeholders, cut sentences in "not taken up"
Every line marked [!] needs a look; the rest is context for the analysis. It judges nothing about whether a
finding is right — that is the analysing agent's job (README.md, step 4).
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cost-audit"))
from audit_session import rows, tools, load_agents, kind, describe  # noqa: E402

LIST_RE = re.compile(r"^(\S+)\s+([\w-]+)\s+(\S*/briefs/(\S+)\.md)", re.M)
FORBIDDEN_MAIN = [(r"^\s*gh\s", "gh (Step 1 did it)"), (r"\bgit\s+(fetch|show|grep|blame|log|diff)\b", "reads git itself"),
                  (r"\bgit\s+(checkout|switch|reset|commit|push|update-ref|branch|stash)\b", "touches git state")]
FORBIDDEN_AGENT = [(r"\bgit\s+(checkout|switch|reset|commit|push|update-ref|branch|stash)\b", "touches git state"),
                   (r"\bgit\s+fetch\s+\S+\s+\S+:\S+", "fetch creates a ref")]
CD_RE = re.compile(r"(^|&&|;|\n)\s*cd\s")
RUN_FILES_MAIN_OK = ("compose.md", "texts.json", "out/factcheck.json", "findings.json")  # findings.json: release PR only
LEAK_RE = re.compile(r"headRefOid|baseRefOid|context\.json|pr-body\.md|candidates\.json|compose\.md|\bfind-(standards|diff-bugs|"
                     r"history|discussion|code-comments|api-contract|security|cross-boundary)\b|\bscorer\b|\bdescriber\b|"
                     r"\bfact-check\b|\[\[(code|at|ref):|<TODAY>")


def out(s=""):
    print(s)


def bullet(s, warn=False):
    out(f"- {'[!] ' if warn else ''}{s}")


def first_line(t, n=220):
    t = (t or "").strip().replace("\n", " ⏎ ")
    return t[:n] + ("…" if len(t) > n else "")


def main(folder):
    folder = Path(folder)
    logs = sorted(folder.glob("session*.jsonl"))
    if not logs:
        sys.exit(f"no session*.jsonl in {folder}")
    runs = sorted((folder / "run").glob("*")) if (folder / "run").is_dir() else []
    out(f"# Checks — {folder.name}")
    out(f"\nSessions: {', '.join(p.name for p in logs)} · run folders: {', '.join(r.name for r in runs) or 'none'}")
    for r in runs:
        facts(r)
    for log in logs:
        sdir = log.with_suffix("")
        all_rows = list(rows(log))
        listed = orchestrator(all_rows, log.name)
        agents(sdir, listed)
    for r in runs:
        results(r)
        report(r)


def facts(r):
    out(f"\n## 1. Run facts — {r.name}")
    try:
        c = json.loads((r / "context.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        bullet(f"context.json unreadable: {e}", True)
        return
    rep, fl, pr = c.get("report") or {}, c.get("flags") or {}, c.get("pr") or {}
    bullet(f"PR #{pr.get('number')} · head {(pr.get('head') or {}).get('oid', '')[:8] or '?'} · mode **{c.get('mode')}** — {c.get('mode_reason')}")
    if c.get("mode") == "update":
        bullet(f"delta: {rep.get('delta')} · old head reachable: {rep.get('old_head_reachable')}",
               rep.get("old_head_reachable") is False)
        bullet(f"base changes removed from delta: {rep.get('delta_base_changes_removed') or 'none'}")
        d = r / "delta.diff"
        if d.exists():
            files = re.findall(r"^diff --git a/(\S+)", d.read_text(encoding="utf-8", errors="ignore"), re.M)
            bullet(f"delta.diff: {len(files)} file(s)", not files)
    api = fl.get("api_contract") or fl.get("finder_f") or {}
    bullet(f"release PR: {(fl.get('release') or {}).get('is_release')} · api contract needed: {api.get('needed')} "
           f"({len(api.get('files') or [])} server files)")
    disc = c.get("discussion") or {}
    bullet(f"discussion: own reports excluded {disc.get('own_reports_excluded')}")
    dj = r / "discussion.json"
    if dj.exists():
        n = len(re.findall(r"\[quoted \d+ line\(s\) omitted\]", dj.read_text(encoding="utf-8", errors="ignore")))
        bullet(f"discussion.json: {n} quote block(s) replaced by '[quoted N line(s) omitted]'")


def orchestrator(all_rows, name):
    out(f"\n## 2. Orchestrator — {name}")
    # Find skill completion marker: last AskUserQuestion with "FOLLOW-UPS" or "Would you like me to file"
    # Everything after that is diagnostic work, not part of the skill run
    skill_end_idx = None
    for i, row in enumerate(all_rows):
        if row.get("role") == "assistant":
            text = (row.get("content") or [{}])[0].get("text", "") if isinstance(row.get("content"), list) else ""
            if "FOLLOW-UPS" in text or "Would you like me to file" in text:
                skill_end_idx = i

    # Filter rows to only include skill run (up to skill_end_idx)
    skill_rows = all_rows[:skill_end_idx + 1] if skill_end_idx is not None else all_rows
    calls = tools(skill_rows)
    listed = {}  # brief name -> agent type, from briefs.py output
    launched = []
    for b, res, err, ts, _ in calls:
        n, i = b["name"], b.get("input") or {}
        k = kind(b)
        if n == "Bash":
            cmd = i.get("command", "")
            if k.endswith(".py") and k != "save.py":
                ex = re.search(r"Exit code (\d+)", res or "")
                bullet(f"{ts[11:19]} `{k}` {first_line(cmd.split(k, 1)[-1], 60)} → "
                       f"{'exit ' + ex.group(1) if ex else 'ok'}: {first_line(res, 160)}", bool(err))
                for m in LIST_RE.finditer(res or ""):
                    listed[m.group(4)] = m.group(2)
            elif "FOLLOW-UPS.md" in cmd:
                bullet(f"{ts[11:19]} Bash ({k}), Step 9 FOLLOW-UPS: {first_line(cmd, 120)}")
            else:
                bullet(f"{ts[11:19]} Bash ({k}): {first_line(cmd, 160)}", True)
            for pat, why in FORBIDDEN_MAIN:
                if re.search(pat, cmd) and not k.endswith(".py"):
                    bullet(f"hard rule: {why} — {first_line(cmd, 120)}", True)
        elif n in ("Agent", "Task"):
            m = re.search(r"/briefs/(\S+)\.md", i.get("prompt", ""))
            launched.append((m.group(1) if m else None, i.get("subagent_type"), i.get("run_in_background"), i.get("prompt", ""), ts))
        elif n in ("Read", "Write", "Edit"):
            p = i.get("file_path", "")
            ok = any(p.endswith(x) for x in RUN_FILES_MAIN_OK) or p.endswith("findings-format.md") or "/tmp/" in p \
                or re.search(r"/tmp/pr-\d+-comment\.md$", p)
            bullet(f"{ts[11:19]} {n} {p}" + (f" — error: {first_line(res, 100)}" if err else ""), not ok or err)
        elif n not in ("AskUserQuestion",):
            bullet(f"{ts[11:19]} {n}: {first_line(describe(b), 120)}", True)
        else:
            bullet(f"{ts[11:19]} AskUserQuestion")
    out("\nAgents launched vs listed by briefs.py:")
    if skill_end_idx is not None and skill_end_idx < len(all_rows) - 1:
        out(f"(Note: filtered to skill run only — {len(all_rows) - skill_end_idx - 1} turns after completion ignored)")
    names = [x[0] for x in launched]
    for brief, typ in listed.items():
        got = [x for x in launched if x[0] == brief]
        if not got:
            bullet(f"{brief}: listed, **not launched**", True)
        for g in got:
            bad = g[1] != typ or g[2] or not re.fullmatch(r"Read your brief: \S+\.md", g[3].strip())
            bullet(f"{brief}: type {g[1]} (listed {typ}) · background {bool(g[2])}"
                   + (f" · prompt: {first_line(g[3], 80)}" if bad else ""), bad)
        if len(got) > 1:
            bullet(f"{brief}: launched {len(got)} times (re-launch after a failed save?)", True)
    for g in launched:
        if g[0] not in listed:
            bullet(f"launched but not listed: {g[0] or first_line(g[3], 80)} ({g[1]})", True)
    if not launched:
        bullet("no agents launched", True)
    return listed


def agents(sdir, listed):
    out(f"\n## 3. Agents — {sdir.name}/subagents")
    for typ, desc, ar in load_agents(sdir):
        calls = tools(ar)
        kinds = {}
        for b, *_ in calls:
            kinds[kind(b)] = kinds.get(kind(b), 0) + 1
        reqs = len({d.get("requestId") for d in ar if d.get("type") == "assistant"})
        out(f"\n**{desc}** ({typ}) — {len(calls)} calls in {reqs} requests · {kinds}")
        cds = sum(1 for b, *_ in calls if b["name"] == "Bash" and CD_RE.search((b.get("input") or {}).get("command", "")))
        if cds:
            bullet(f"{cds} command(s) start with `cd` (SKILL.md: agents run from the repo root, never cd) — harmless "
                   "unless a git command then ran outside the repo")
        for b, res, err, ts, _ in calls:
            n, i = b["name"], b.get("input") or {}
            cmd = i.get("command", "") if n == "Bash" else ""
            if kind(b) == "save.py":
                if "INVALID" in (res or "") or err:
                    bullet(f"save.py call failed: {first_line(res, 400)}", True)
                else:
                    bullet(f"save.py: {first_line(res, 120)}")
            elif err:
                bullet(f"error ({kind(b)}): {first_line(describe(b), 100)} → {first_line(res, 160)}", True)
            if n == "Bash" and re.search(r"\bcurl\b", cmd) or n in ("WebFetch", "WebSearch"):
                bullet(f"network: {first_line(describe(b), 160)} → {first_line(res, 100)}",
                       n == "Bash" and "raw.githubusercontent.com/openstack/" not in cmd)
            if n in ("Write", "Edit", "NotebookEdit"):
                bullet(f"{n} {i.get('file_path')} (agents save only through save.py)", True)
            for pat, why in FORBIDDEN_AGENT:
                if cmd and re.search(pat, cmd):
                    bullet(f"hard rule: {why} — {first_line(cmd, 120)}", True)
        last = next((d for d in reversed(ar) if d.get("type") == "assistant"), {})
        txt = " ".join(x.get("text", "") for x in ((last.get("message") or {}).get("content") or [])
                       if isinstance(x, dict) and x.get("type") == "text")
        if txt and not txt.strip().startswith("saved"):
            bullet(f"last reply isn't a 'saved …' line: {first_line(txt, 160)}", True)


def results(r):
    out(f"\n## 4. Results — {r.name}")
    briefs = sorted(p.stem for p in (r / "briefs").glob("*.md")) if (r / "briefs").is_dir() else []
    have = {p.stem for p in (r / "out").glob("*.json")} if (r / "out").is_dir() else set()
    alias = {"earlier-findings": "earlier-findings", "factcheck": "factcheck"}
    missing = [b for b in briefs if alias.get(b, b) not in have and b not in have]
    bullet(f"briefs: {len(briefs)} · out/*.json: {len(have)}" + (f" · missing results: {missing}" if missing else ""), bool(missing))
    try:
        author = (json.loads((r / "context.json").read_text(encoding="utf-8")).get("pr") or {}).get("author")
    except (OSError, ValueError):
        author = "?"
    try:
        f = json.loads((r / "findings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        bullet(f"findings.json unreadable: {e}", True)
        return
    out("\nFindings (verify each against the code at head — README step 4):")
    for x in f.get("findings") or []:
        bullet(f"`{x.get('id')}` {x.get('score')} {x.get('severity')} {x.get('category')}"
               f"{' · precedent ' + first_line(json.dumps(x['precedent'], ensure_ascii=False), 80) if x.get('precedent') else ''} — {first_line(x.get('title') or x.get('issue'), 140)}"
               f" · at `{first_line(x.get('location'), 120)}`")
    if not f.get("findings"):
        bullet("none")
    for p in f.get("process") or []:
        bullet(f"Process `{p.get('id')}`: {first_line(p.get('text') or p.get('title') or json.dumps(p), 160)}")
    earlier = f.get("earlier") or {}
    if earlier:
        out("\nEarlier findings (statuses from earlier-findings):")
        for k, v in earlier.items():
            st = v.get("status")
            note = v.get("note") or ""
            warn = st == "dropped" and k.startswith("CR") and re.search(r"Kept as is", note)
            warn = warn or (re.search(r"maintainer", note, re.I) is not None and st in ("dropped", "fixed"))
            bullet(f"{k}: **{st}** — {first_line(note, 200)}"
                   + (" — 'Kept as is' closes only I/P" if st == "dropped" and k.startswith("CR") and "Kept as is" in note else "")
                   + (f" — says 'maintainer': is that person the PR author ({author})? A maintainer's reversal is "
                      "'dropped · Reversed by', not 'fixed'" if re.search(r"maintainer", note, re.I) else ""), bool(warn))
    dis = f.get("dismissed") or []
    if dis:
        out(f"\nDismissed: {len(dis)} (with a discussion link: {sum(1 for d in dis if d.get('discussion'))})")
        for d in dis:
            if d.get("discussion"):
                m = re.search(r"maintainer", d.get("reason") or "", re.I)
                bullet(f"{d.get('score')} · {first_line(d.get('claim'), 120)} · reason: {first_line(d.get('reason'), 140)}"
                       + (f" — says 'maintainer': is that person the PR author ({author})?" if m else ""), bool(m))
    for p in f.get("provenance_extra") or []:
        bullet(f"provenance note: {first_line(p, 200)}", True)


def report(r):
    rp = r / "report.md"
    out(f"\n## 5. Report text — {r.name}/report.md")
    if not rp.exists():
        bullet("no report.md", True)
        return
    t = rp.read_text(encoding="utf-8", errors="ignore")
    bullet(f"{len(t)} characters")
    for m in LEAK_RE.finditer(t):
        a = t.rfind("\n", 0, m.start()) + 1
        bullet(f"internal name/placeholder `{m.group(0)}` in: {first_line(t[a:t.find(chr(10), m.end())], 160)}", True)
    sec = re.search(r"not taken up(.*?)(\n#{2,4} |\Z)", t, re.S | re.I)
    if sec:
        for line in sec.group(1).splitlines():
            s = line.strip()
            if s.startswith(("- ", "* ", "|")) and not re.search(r"[.!?)`\]|]\s*\|?$", s):
                bullet(f"'not taken up' line may be cut: {first_line(s, 200)}", True)
    for m in re.finditer(r"(?<!\()https://github\.com/\S+#pullrequestreview-\d+", t):
        bullet(f"bare review URL (not a link): {m.group(0)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
