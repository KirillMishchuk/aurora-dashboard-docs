#!/usr/bin/env python3
"""Write the agent briefs for a review-and-comment-pr stage from fixed templates.

Usage:
  briefs.py --run <run-dir> find
  briefs.py --run <run-dir> score
  briefs.py --run <run-dir> factcheck

find: the describer and finders a-g (f only when context.json flags it)
into <run-dir>/briefs/, from references/briefs/*.md. Prints one line per
agent: name, subagent type, brief path. Launch exactly these agents, each
with the prompt "Read your brief: <path>". Each saves its result with
save.py into <run-dir>/out/<name>.json.

score: reads out/finder-*.json and out/describer.json (unmet acceptance
criteria and stale callers become candidates), numbers the candidates
C1… (finder a…g, then describer), groups those that point at the same
place (same file within 3 lines, or the same label), packs them into
batches of up to 8 without splitting a group, and writes
<run-dir>/candidates.json plus one scorer brief per batch. Each scorer
saves out/score-<n>.json.

factcheck: one brief for the fact-checker over <run-dir>/report.md (the
rendered draft; on an update, just the new Update block). It
saves out/factcheck.json: the wrong claims, each with the field it comes
from and an exact old/new replacement.

Exit codes: 0 = briefs written (or none needed: release PR / status modes,
said on stdout); 1 = a template or the context is broken; 2 = usage error.
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import quotes  # noqa: E402

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
TEMPLATES = SKILL_DIR / "references" / "briefs"
AGENTS_DIR = SKILL_DIR.parent.parent / "agents"
BATCH = 8
NEAR_LINES = 3
LABELS = {"PR body", "PR state", "PR files", "CI"}
FINDERS = [("finder-a", "pr-reviewer", "Finder a — conventions"),
           ("finder-b", "pr-reviewer", "Finder b — bug scan"),
           ("finder-c", "pr-reviewer", "Finder c — history and open PRs"),
           ("finder-d", "pr-reviewer", "Finder d — review discussion"),
           ("finder-e", "pr-reviewer", "Finder e — comment compliance"),
           ("finder-f", "external-api-checker", "Finder f — external API contract"),
           ("finder-g", "security-reviewer", "Finder g — security")]


def hard_rules():
    """The two read-only rules from SKILL.md, verbatim (security-reviewer doesn't carry them)."""
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"(?ms)^- \*\*Never check out the PR branch.*?(?=^  Agent types and briefs|^- \*\*Verify against real code)", text)
    if not m:
        raise ValueError("SKILL.md: can't find the 'Never check out' / 'Reading code at a commit' rules")
    return m.group(0).rstrip()


def fallback_note(agent):
    return "" if (AGENTS_DIR / f"{agent}.md").is_file() else \
        "   (agent missing — use a general Sonnet agent; add '" + agent + " fallback used' to provenance_extra)"


def bullets(items):
    return "\n".join(f"- {x}" for x in items) or "- (none)"


def overlaps(ctx):
    out = []
    for o in ctx.get("overlapping_prs") or []:
        s = f"#{o['number']} {o['title']} — head `{o['head_oid']}`, {len(o['shared_files'])} shared file(s), merge: {o['merge']}"
        if o.get("conflicts_only_generated"):
            s += " (generated/catalog files only — not a candidate)"
        elif o.get("conflict_files"):
            gen = re.compile(r"(^|/)(locales/[^/]+/messages\.(ts|js|po)|routeTree\.gen\.ts)$")
            real = [x for x in o["conflict_files"] if not gen.search(x)]
            s += " in " + ", ".join(f"`{x}`" for x in real)
            if len(real) < len(o["conflict_files"]):
                s += f" (+{len(o['conflict_files']) - len(real)} generated/catalog)"
        out.append(s)
    return bullets(out) if out else "- none"


def variables(ctx, run):
    p, f, rep = ctx["pr"], ctx["flags"], ctx["report"]
    issue = ctx.get("issue") or {}
    issues = [i for i in issue.get("linked", [])] + ([issue["supplied"]] if issue.get("supplied") else [])
    issue_files = "".join(f", `{i['file']}` (issue #{i['number']} — acceptance criteria)" for i in issues)
    scope = ""
    if ctx["mode"] == "update":
        scope = ("- **Scope: this is an Update.** Analyze only the new commits — "
                 + ("`delta.diff`, the range `" + rep["delta"] + "`." if rep.get("delta") not in (None, "whole-pr")
                    else "the old head is unreachable (force-push), so the whole PR diff.") + "\n")
    acceptance = (f"Grade the PR against the acceptance criteria in "
                  + ", ".join(f"`{i['file']}`" for i in issues)
                  + ": for each criterion, met / partly met / unmet, with `file:line` evidence. "
                  "Use \"out of scope\" only when `pr-body.md` explicitly limits the PR to part of the issue "
                  "(e.g. \"phase 1\", \"read-only part of #N\") and the criterion falls outside that part — "
                  "quote the limiting line from `pr-body.md` in `evidence`. An out-of-scope criterion is not "
                  "a candidate; a partly met criterion inside the PR's own scope still is."
                  if issues else "There is no issue to grade against — return `\"acceptance\": []`.")
    return {
        "number": str(p["number"]), "run": run, "head": p["head"]["oid"], "base": p["base"]["oid"],
        "issue_files": issue_files, "scope": scope, "acceptance": acceptance,
        "claude_md": (ctx.get("standards") or {}).get("claude_md", "CLAUDE.md"),
        "overlaps": overlaps(ctx),
        "finder_f_files": bullets(f"`{x}`" for x in f["finder_f"]["files"]),
    }


def fill(text, vals):
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: vals[m.group(1)] if m.group(1) in vals else m.group(0), text)
    left = re.findall(r"\{\{\w+\}\}", out)
    if left:
        raise ValueError(f"unknown template variables: {', '.join(sorted(set(left)))}")
    return out


def find(ctx, run_dir):
    if ctx["mode"] not in ("full", "rerun", "update"):
        print(f"Mode {ctx['mode']}: no agents.")
        return 0
    if ctx["flags"]["release"]["is_release"]:
        print("Release PR: no agents — do the light review yourself (Step 2).")
        return 0
    run = str(run_dir)
    vals = variables(ctx, run)
    part = {n: (TEMPLATES / f"_{n}.md").read_text(encoding="utf-8") for n in ("header", "output", "candidates")}
    agents = [("describer", "pr-reviewer", "Describer")] + [
        a for a in FINDERS if a[0] != "finder-f" or ctx["flags"]["finder_f"]["needed"]]
    (run_dir / "briefs").mkdir(exist_ok=True)
    (run_dir / "out").mkdir(exist_ok=True)
    lines = []
    for name, agent, role in agents:
        v = dict(vals, name=name, role=role)
        v["header"] = fill(part["header"], v)
        v["output"] = fill(part["output"], v)
        v["candidates"] = part["candidates"]
        if name == "finder-g":
            v["hard_rules"] = hard_rules()
        brief = fill((TEMPLATES / f"{name}.md").read_text(encoding="utf-8"), v)
        brief = re.sub(r"\n{3,}", "\n\n", brief)
        path = run_dir / "briefs" / f"{name}.md"
        path.write_text(brief, encoding="utf-8")
        stale = run_dir / "out" / f"{name}.json"
        if stale.exists():
            stale.unlink()
        lines.append(f"{name:<10} {agent:<21} {path}{fallback_note(agent)}")
    print(f"Launch these {len(lines)} agents in ONE message, in the foreground, each with the prompt "
          "\"Read your brief: <path>\" and the subagent type shown:\n" + "\n".join(lines))
    return 0


def collect_candidates(run_dir, repo):
    cands = []
    for name, _, _ in FINDERS:
        f = run_dir / "out" / f"{name}.json"
        if f.exists():
            for c in json.loads(f.read_text(encoding="utf-8"))["candidates"]:
                cands.append(dict(c, source=name))
    gen = re.compile(r"(^|/)(locales/[^/]+/messages\.(ts|js|po)|routeTree\.gen\.ts)$")
    ctx = json.loads((run_dir / "context.json").read_text(encoding="utf-8"))
    for o in ctx.get("overlapping_prs") or []:  # a conflict collect.py proved — not left to finder c's recall
        if o.get("merge") != "conflicts" or o.get("conflicts_only_generated"):
            continue
        real = [x for x in o.get("conflict_files") or [] if not gen.search(x)]
        cands.append({"claim": f"Merge conflict with open PR #{o['number']} ({o['title']}) in "
                               + ", ".join(f"`{x}`" for x in real) + ".",
                      "location": "PR files",
                      "evidence": f"`git merge-tree --write-tree --name-only {ctx['pr']['head']['oid']} {o['head_oid']}` "
                                  "reports conflicts in: " + ", ".join(f"`{x}`" for x in o.get("conflict_files") or []),
                      "source": "collect.py (merge-tree)"})
    f = run_dir / "out" / "describer.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        for a in d.get("acceptance", []):
            if a["status"] in ("unmet", "partly met"):
                m = quotes.CITE.search(a["evidence"])
                cands.append({"claim": f"Acceptance criterion {a['status']}: {a['criterion']}",
                              "location": f"{m.group(1)}:{m.group(2)}" if m else "PR files",
                              "evidence": a["evidence"], "source": "describer (acceptance)"})
        for s in d.get("stale_callers", []):
            cands.append({"claim": f"Stale caller of `{s['symbol']}`: {s['note']}", "location": s["location"],
                          "evidence": s["note"], "source": "describer (stale caller)"})
    for i, c in enumerate(cands, 1):
        c["id"] = f"C{i}"
        loc = c["location"].strip()
        if " | " in loc:  # already checked by save.py; resolve to path:line for grouping and scorers
            loc = quotes.resolve_location(repo, loc, c["id"], [])
        m = re.match(r"^([^:\s]+)(:\d+(?:-\d+)?)?$", loc)
        if m and loc not in LABELS:  # a short name of a changed file -> its full path
            loc = (repo.resolve_name(m.group(1)) or m.group(1)) + (m.group(2) or "")
        c["location"] = loc
    return cands


def place(loc, repo):
    if loc in LABELS:
        return ("label", loc, None)
    m = re.match(r"^(.+?)(?::(\d+)(?:-\d+)?)?$", loc)
    path = repo.resolve_name(m.group(1)) or m.group(1)
    return ("path", path, int(m.group(2)) if m.group(2) else None)


def group(cands, repo):
    parent = list(range(len(cands)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    places = [place(c["location"], repo) for c in cands]
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            a, b = places[i], places[j]
            if a[0] == b[0] and a[1] == b[1] and (
                    a[0] == "label" or (a[2] is None and b[2] is None)
                    or (a[2] is not None and b[2] is not None and abs(a[2] - b[2]) <= NEAR_LINES)):
                parent[root(j)] = root(i)
    groups = {}
    for i in range(len(cands)):
        groups.setdefault(root(i), []).append(i)
    return [g for g in sorted(groups.values(), key=lambda g: g[0])]


def candidate_md(c):
    out = [f"### {c['id']} — from {c['source']}", f"- **Claim:** {c['claim']}", f"- **Location:** `{c['location']}`"
           if c["location"] not in LABELS else f"- **Location:** {c['location']}", f"- **Evidence:**\n\n{c['evidence']}"]
    if c.get("precedent"):
        out.append(f"- **Precedent:** {c['precedent']}")
    if c.get("discussion"):
        out.append(f"- **Review discussion:** {c['discussion']}")
    return "\n".join(out) + "\n"


def score(ctx, run_dir):
    if ctx["mode"] not in ("full", "rerun", "update") or ctx["flags"]["release"]["is_release"]:
        print("No scoring for this mode / release PR.")
        return 0
    repo = quotes.Repo(ctx)
    cands = collect_candidates(run_dir, repo)
    out_dir = run_dir / "out"
    for stale in out_dir.glob("score-*.json"):
        stale.unlink()
    for stale in (run_dir / "briefs").glob("score-*.md"):
        stale.unlink()
    if not cands:
        (run_dir / "candidates.json").write_text(json.dumps({"candidates": [], "batches": 0}, indent=1) + "\n",
                                                 encoding="utf-8")
        print("No candidates — nothing to score. The review is clean apart from Process items.")
        return 0
    groups = group(cands, repo)
    batches, cur = [], []
    for g in groups:
        if cur and len(cur) + len(g) > BATCH:
            batches.append(cur)
            cur = []
        cur += g
    if cur:
        batches.append(cur)
    for g in groups:
        for i in g:
            cands[i]["group"] = [cands[k]["id"] for k in g] if len(g) > 1 else None
    for n, b in enumerate(batches, 1):
        for i in b:
            cands[i]["batch"] = n
    (run_dir / "candidates.json").write_text(json.dumps({"candidates": cands, "batches": len(batches)},
                                                        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    vals = variables(ctx, str(run_dir))
    part = {n: (TEMPLATES / f"_{n}.md").read_text(encoding="utf-8") for n in ("header", "output")}
    lines = []
    for n, b in enumerate(batches, 1):
        name = f"score-{n}"
        v = dict(vals, name=name, role=f"Scorer {n}", batch=str(n), batches=str(len(batches)))
        v["header"] = fill(part["header"], v)
        v["output"] = fill(part["output"], v)
        gs = []
        seen = set()
        for i in b:
            g = cands[i].get("group")
            if g and tuple(g) not in seen:
                seen.add(tuple(g))
                gs.append(g)
        v["groups"] = ("## Same place\n\nThese candidates point at the same place. For each, set `same_as` (see the "
                       "result shape): the same problem, or a different one.\n\n"
                       + "\n".join("- " + ", ".join(g) for g in gs) + "\n") if gs else ""
        v["candidates_md"] = "\n".join(candidate_md(cands[i]) for i in b)
        brief = re.sub(r"\n{3,}", "\n\n", fill((TEMPLATES / "scorer.md").read_text(encoding="utf-8"), v))
        path = run_dir / "briefs" / f"{name}.md"
        path.write_text(brief, encoding="utf-8")
        lines.append(f"{name:<10} {'pr-reviewer':<21} {path}   ({', '.join(cands[i]['id'] for i in b)})"
                     + fallback_note("pr-reviewer"))
    print(f"{len(cands)} candidates in {len(groups)} places. Launch these {len(lines)} scorers in ONE message, in the "
          "foreground, each with the prompt \"Read your brief: <path>\" and the subagent type shown:\n" + "\n".join(lines))
    return 0


def factcheck(ctx, run_dir):
    if not (run_dir / "report.md").exists() or not (run_dir / "findings.json").exists():
        print("ERROR: report.md / findings.json missing — run assemble.py --texts and render.py first")
        return 1
    target = str(run_dir / "report.md")
    field_ex = "overview.how | qa.edge_cases[3] | findings.<id>.explanation"
    src_note = (f" — `{run_dir / 'findings.json'}`: `overview.what|how|affects`, `qa.core_path[i]`, "
                "`qa.edge_cases[i]` (0-based, in the order shown), or `findings.<id>.issue|title|explanation|fix`")
    upd = (" — this is an Update block, so its \"What changed\" section (rendered from `overview`)"
           if ctx["mode"] == "update" else "")
    vals = variables(ctx, str(run_dir))
    v = dict(vals, name="factcheck", role="Fact-check", target=target, update_note=upd, source_note=src_note,
             field_example=field_ex)
    part = {n: (TEMPLATES / f"_{n}.md").read_text(encoding="utf-8") for n in ("header", "output")}
    v["header"] = fill(part["header"], v)
    v["output"] = fill(part["output"], v)
    brief = re.sub(r"\n{3,}", "\n\n", fill((TEMPLATES / "factcheck.md").read_text(encoding="utf-8"), v))
    (run_dir / "briefs").mkdir(exist_ok=True)
    path = run_dir / "briefs" / "factcheck.md"
    path.write_text(brief, encoding="utf-8")
    stale = run_dir / "out" / "factcheck.json"
    if stale.exists():
        stale.unlink()
    print("Launch this agent in the foreground with the prompt \"Read your brief: <path>\" and the subagent type shown:\n"
          f"{'factcheck':<10} {'pr-reviewer':<21} {path}" + fallback_note("pr-reviewer"))
    return 0


def main(argv):
    if len(argv) != 3 or argv[0] != "--run" or argv[2] not in ("find", "score", "factcheck"):
        print(__doc__)
        return 2
    run_dir = Path(argv[1]).resolve()
    try:
        ctx = json.loads((run_dir / "context.json").read_text(encoding="utf-8"))
        return {"find": find, "score": score, "factcheck": factcheck}[argv[2]](ctx, run_dir)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
