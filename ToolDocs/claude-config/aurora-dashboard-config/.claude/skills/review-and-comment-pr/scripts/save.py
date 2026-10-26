#!/usr/bin/env python3
"""Check an agent's result and save it into the run folder.

Usage (by the agent, as its brief says):
  python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <run-dir> --as <name> <<'JSON'
  { … }
  JSON

<name>: describer | finder-a … finder-g | score-<n> | factcheck. Checks the JSON shape, every
location (the file and line exist at the PR head) and, for the describer,
every [[code:…]] / [[at:…]] placeholder and `path:line` citation. On success
writes <run-dir>/out/<name>.json and prints one line; on errors writes
nothing and lists them — fix and run again.

Exit codes: 0 = saved; 1 = invalid (errors listed); 2 = usage error.
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import quotes  # noqa: E402

LABELS = {"PR body", "PR state", "PR files", "CI"}
SCORES = {0, 25, 50, 75, 100}
SEVERITIES = ["Critical", "Major", "Moderate", "Low", "Trivial"]
CATEGORIES = ["Bug", "Security", "Accessibility", "UI/UX", "Code Quality", "Performance", "Docs",
              "Test coverage"]
STATUSES = {"met", "partly met", "unmet", "out of scope"}
CHECK = {"violated", "not violated"}


ABBREV = re.compile(r"(?<![\w/])(\.\.\.|…)/")


def text(errors, obj, key, where, required=True):
    v = obj.get(key)
    if isinstance(v, str) and ABBREV.search(v):
        errors.append(f"{where}.{key}: abbreviated path (…/ or .../) — write the full repo-relative path")
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            errors.append(f"{where}.{key}: missing or empty")
        return None
    if not isinstance(v, str):
        errors.append(f"{where}.{key}: must be a string")
        return None
    return v


def keys(errors, obj, allowed, where):
    if not isinstance(obj, dict):
        errors.append(f"{where}: must be an object")
        return False
    for k in obj:
        if k not in allowed:
            errors.append(f"{where}.{k}: unknown key (allowed: {', '.join(sorted(allowed))})")
    return True


def location(repo, loc, where, errors):
    loc = loc.strip()
    if loc in LABELS:
        return
    if " | " in loc:
        quotes.resolve_location(repo, loc, where, errors)
        return
    m = re.match(r"^([^:`\s]+?)(?::(\d+)(?:-(\d+))?)?$", loc)
    if not m:
        errors.append(f"{where}: {loc!r} — use path:line, path | text, or one of {sorted(LABELS)}")
        return
    path = repo.resolve_name(m.group(1)) or m.group(1)
    ls = repo.lines(path)
    if ls is None:
        errors.append(f"{where}: {path} does not exist at head {repo.head[:8]}")
    elif m.group(2) and not (1 <= int(m.group(2)) <= int(m.group(3) or m.group(2)) <= len(ls)):
        errors.append(f"{where}: {loc} is out of range ({len(ls)} lines at head)")


def check_finder(name, data, repo):
    errors = []
    allowed = {"candidates", "checklist"} if name == "finder-a" else {"candidates"}
    if not keys(errors, data, allowed, name):
        return errors, 0
    cands = data.get("candidates")
    if not isinstance(cands, list):
        errors.append("candidates: must be a list (empty if none)")
        cands = []
    for i, c in enumerate(cands):
        w = f"candidates[{i}]"
        if not keys(errors, c, {"claim", "location", "evidence", "precedent", "discussion"}, w):
            continue
        text(errors, c, "claim", w)
        text(errors, c, "evidence", w)
        text(errors, c, "precedent", w, required=False)
        text(errors, c, "discussion", w, required=False)
        loc = text(errors, c, "location", w)
        if loc:
            location(repo, loc, f"{w}.location", errors)
    if name == "finder-a":
        cl = data.get("checklist")
        if not isinstance(cl, list) or not cl:
            errors.append("checklist: one entry per checklist item / Reject line is required")
        else:
            for i, it in enumerate(cl):
                w = f"checklist[{i}]"
                if keys(errors, it, {"item", "result", "where"}, w):
                    text(errors, it, "item", w)
                    if it.get("result") not in CHECK:
                        errors.append(f"{w}.result: {it.get('result')!r} not one of {sorted(CHECK)}")
    return errors, len(cands)


def check_scores(name, data, repo, run_dir):
    errors = []
    try:
        cands = json.loads((run_dir / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    except (OSError, ValueError, KeyError):
        return ["candidates.json missing — run briefs.py score first"], 0
    n = int(name.split("-")[1])
    mine = {c["id"]: c for c in cands if c.get("batch") == n}
    if not mine:
        return [f"no batch {n} in candidates.json"], 0
    if not keys(errors, data, {"scores"}, name) or not isinstance(data.get("scores"), list):
        return errors or ["scores: must be a list"], 0
    seen = set()
    for i, s in enumerate(data["scores"]):
        w = f"scores[{i}]"
        if not keys(errors, s, {"id", "score", "severity", "category", "location", "reason", "same_as", "precedent"}, w):
            continue
        cid = s.get("id")
        if cid not in mine:
            errors.append(f"{w}.id: {cid!r} is not in batch {n} ({', '.join(mine)})")
            continue
        if cid in seen:
            errors.append(f"{w}.id: {cid} scored twice")
        seen.add(cid)
        w = f"{cid}"
        if s.get("same_as"):  # a duplicate is dropped: its score and reason don't matter, fill them in
            if s.get("score") is None:
                s["score"] = 0
            if not (isinstance(s.get("reason"), str) and s["reason"].strip()):
                s["reason"] = f"Same problem as {s['same_as']}."
        text(errors, s, "reason", w)
        if s.get("score") not in SCORES:
            errors.append(f"{w}.score: {s.get('score')!r} — use 0, 25, 50, 75 or 100")
        group = mine[cid].get("group")
        if group:
            if "same_as" not in s:
                others = [g for g in group if g != cid]
                errors.append(f"{w}.same_as: {cid} shares a place with {', '.join(others)} — set same_as to one of "
                              "them if it's the same problem, or null if it's a different one")
            elif s["same_as"] is not None and (s["same_as"] not in group or s["same_as"] == cid):
                errors.append(f"{w}.same_as: {s['same_as']!r} — must be another id of its group ({', '.join(group)}) or null")
        elif s.get("same_as") is not None:
            errors.append(f"{w}.same_as: {cid} is in no group — leave same_as out")
        if isinstance(s.get("score"), int) and s["score"] >= 50 and not s.get("same_as"):
            if s.get("severity") not in SEVERITIES:
                errors.append(f"{w}.severity: {s.get('severity')!r} not one of {SEVERITIES}")
            if s.get("category") not in CATEGORIES:
                errors.append(f"{w}.category: {s.get('category')!r} not one of {CATEGORIES}")
            loc = text(errors, s, "location", w)
            if loc:
                location(repo, loc, f"{w}.location", errors)
            if "precedent" not in s:
                errors.append(f"{w}.precedent: required for a score of 50 or more — null, or "
                              "{\"kind\": \"existing\" | \"deferred\", \"ref\": …}")
            else:
                quotes.check_precedent(repo, s["precedent"], f"{w}.precedent", errors)
    missing = [c for c in mine if c not in seen]
    if missing:
        errors.append(f"not scored: {', '.join(missing)} — every candidate of the batch exactly once")
    return errors, len(seen)


def check_factcheck(data, ctx, run_dir):
    errors = []
    if not keys(errors, data, {"wrong"}, "factcheck") or not isinstance(data.get("wrong"), list):
        return errors or ["wrong: must be a list (empty if everything holds)"], 0
    try:
        fd = json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))
    except OSError:
        return ["findings.json missing — the fact-check runs after assemble.py --texts"], 0
    for i, w_ in enumerate(data["wrong"]):
        w = f"wrong[{i}]"
        if not keys(errors, w_, {"claim", "field", "old", "new", "evidence"}, w):
            continue
        for k in ("claim", "field", "old", "new", "evidence"):
            text(errors, w_, k, w)
        f, old = w_.get("field"), w_.get("old")
        if not isinstance(f, str) or not isinstance(old, str) or not old:
            continue
        m = re.match(r"^overview\.(what|how|affects)$|^qa\.(core_path|edge_cases)\[(\d+)\]$"
                     r"|^findings\.([a-z0-9-]+)\.(issue|title|explanation|fix)$", f)
        if not m:
            errors.append(f"{w}.field: {f!r} — overview.what|how|affects, qa.core_path[i], qa.edge_cases[i], "
                          "or findings.<id>.issue|title|explanation|fix")
            continue
        if m.group(1):
            cur = (fd.get("overview") or {}).get(m.group(1), "")
        elif m.group(2):
            lst = (fd.get("qa") or {}).get(m.group(2), [])
            cur = lst[int(m.group(3))] if int(m.group(3)) < len(lst) else None
            if cur is None:
                errors.append(f"{w}.field: qa.{m.group(2)} has {len(lst)} entries (0-based)")
                continue
        else:
            hit = [x for x in fd.get("findings", []) if x.get("id") == m.group(4)]
            if not hit:
                errors.append(f"{w}.field: no finding {m.group(4)!r} in findings.json")
                continue
            cur = hit[0].get(m.group(5), "")
        if cur.count(old) != 1:
            errors.append(f"{w}.old: found {cur.count(old)} times in {f} — copy an exact piece of the source text "
                          "that occurs once")
    return errors, len(data["wrong"])


def check_earlier(data, ctx):
    """The `earlier` agent: a status, a note and evidence for every finding of the existing report — no gaps."""
    errors = []
    if not keys(errors, data, {"earlier"}, "earlier") or not isinstance(data.get("earlier"), dict):
        return errors or ["earlier: must be an object keyed by the earlier findings' numbers"], 0
    numbers = [r[0] for r in quotes.earlier_rows(ctx["report"]["path"], ctx["pr"]["head"]["short"])]
    e = data["earlier"]
    missing = [n for n in numbers if n not in e]
    if missing:
        errors.append(f"earlier: missing {', '.join(missing)} — every finding in your brief's list exactly once")
    for k, v in e.items():
        w = f"earlier.{k}"
        if k not in numbers:
            errors.append(f"{w}: not in your brief's list ({', '.join(numbers) or 'none'})")
            continue
        if not keys(errors, v, {"status", "note", "evidence"}, w):
            continue
        if v.get("status") not in ("fixed", "partly", "open"):
            errors.append(f"{w}.status: {v.get('status')!r} — fixed, partly or open")
        note = text(errors, v, "note", w)
        if note and "\n" in note.strip():
            errors.append(f"{w}.note: one line")
        text(errors, v, "evidence", w)
    return errors, len(e)


def check_describer(data, repo):
    errors = []
    if not keys(errors, data, {"overview", "qa", "acceptance", "stale_callers", "scope"}, "describer"):
        return errors
    ov = data.get("overview")
    if keys(errors, ov or {}, {"what", "how", "affects"}, "overview"):
        for k in ("what", "how", "affects"):
            t = text(errors, ov or {}, k, "overview")
            if t:
                quotes.resolve_text(repo, t, f"overview.{k}", errors)
    qa = data.get("qa")
    if keys(errors, qa or {}, {"core_path", "edge_cases"}, "qa"):
        for k in ("core_path", "edge_cases"):
            v = (qa or {}).get(k)
            if not isinstance(v, list) or not v or not all(isinstance(x, str) and x.strip() for x in v):
                errors.append(f"qa.{k}: must be a non-empty list of strings")
                continue
            for i, x in enumerate(v):
                quotes.resolve_text(repo, x, f"qa.{k}[{i}]", errors, code_ok=False)
    acc = data.get("acceptance", [])
    if not isinstance(acc, list):
        errors.append("acceptance: must be a list (empty if there is no issue)")
    else:
        for i, a in enumerate(acc):
            w = f"acceptance[{i}]"
            if keys(errors, a, {"criterion", "status", "evidence"}, w):
                text(errors, a, "criterion", w)
                text(errors, a, "evidence", w)
                if a.get("status") not in STATUSES:
                    errors.append(f"{w}.status: {a.get('status')!r} not one of {sorted(STATUSES)}")
    if data.get("scope") is not None:
        sc_ = text(errors, data, "scope", "describer")
        if sc_ and ("\n" in sc_.strip() or len(sc_) > 100):
            errors.append("describer.scope: one short line (about 100 characters at most), or null")
    sc = data.get("stale_callers", [])
    if not isinstance(sc, list):
        errors.append("stale_callers: must be a list")
    else:
        for i, s in enumerate(sc):
            w = f"stale_callers[{i}]"
            if keys(errors, s, {"symbol", "location", "note"}, w):
                text(errors, s, "symbol", w)
                text(errors, s, "note", w)
                loc = text(errors, s, "location", w)
                if loc:
                    location(repo, loc, f"{w}.location", errors)
    return errors


def main(argv):
    if len(argv) != 4 or argv[0] != "--run" or argv[2] != "--as":
        print(__doc__)
        return 2
    run_dir, name = Path(argv[1]), argv[3]
    if name not in ("describer", "factcheck", "earlier") and not re.match(r"^(finder-[a-g]|score-\d+)$", name):
        print(f"ERROR: unknown result name {name!r} (describer, finder-a … finder-g, earlier, score-<n>, factcheck)")
        return 2
    try:
        ctx = json.loads((run_dir / "context.json").read_text(encoding="utf-8"))
    except OSError as e:
        print(f"ERROR: {e}")
        return 2
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except ValueError as e:
        print(f"INVALID — not valid JSON: {e}. Nothing saved; fix it and run again.")
        return 1
    repo = quotes.Repo(ctx)
    if name == "describer":
        errors, what = check_describer(data, repo), "describer result"
    elif name == "factcheck":
        errors, n = check_factcheck(data, ctx, run_dir)
        what = f"{n} wrong claim(s)"
    elif name == "earlier":
        if ctx["mode"] != "update":
            print("ERROR: `earlier` runs only on an Update")
            return 2
        errors, n = check_earlier(data, ctx)
        what = f"{n} earlier finding status(es)"
    elif name.startswith("score-"):
        errors, n = check_scores(name, data, repo, run_dir)
        what = f"{n} score(s)"
    else:
        errors, n = check_finder(name, data, repo)
        what = f"{n} candidate(s)"
    if errors:
        print(f"INVALID — {len(errors)} error(s), nothing saved; fix them and run again:\n  " + "\n  ".join(errors))
        return 1
    out = run_dir / "out" / f"{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {out.relative_to(run_dir)}: {what}"
          + (f" — warnings: {'; '.join(repo.warnings)}" if repo.warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
