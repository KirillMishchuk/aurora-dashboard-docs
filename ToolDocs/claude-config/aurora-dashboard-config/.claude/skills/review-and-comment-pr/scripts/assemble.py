#!/usr/bin/env python3
"""Assemble findings.json from the agents' results (review-and-comment-pr Step 6).

Usage:
  assemble.py --run <run-dir>            write <run-dir>/compose.md
  assemble.py --run <run-dir> --texts    texts.json -> findings.json

Pass 1 reads candidates.json, out/score-*.json and out/describer.json, keeps
every candidate scored 50 or more that isn't a `same_as` duplicate (the
duplicate's evidence goes along; a duplicate of a dropped candidate is listed
with it under "Checked and dismissed", never lost), flags pairs of kept findings that look
alike, and writes compose.md: per finding the claim, evidence and scorer's
reason, plus a texts.json template. You write <run-dir>/texts.json — the
wording only (summary, confidence, index line, and issue/title/explanation/
fix per finding) — then pass 2 builds findings.json for render.py: scores,
severity, category, location and ids from the scorers, overview and QA plan
from the describer, your texts on top.

Exit codes: 0 = written; 1 = missing input or texts.json problems (listed);
2 = usage error.
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import quotes  # noqa: E402  (same folder)

ORDER = ["Critical", "Major", "Moderate", "Low", "Trivial"]
TEXT_KEYS = ("issue", "title", "explanation", "fix")
SIMILAR = 0.3
STOP = {"that", "this", "with", "from", "which", "when", "only", "into", "does", "than", "their", "there",
        "they", "have", "uses", "used", "instead", "should", "because", "both", "also", "each", "page", "list"}


DESC_TITLE = {"not in code": "The description claims what the code doesn't do",
              "not described": "A change the description doesn't mention"}
PROCESS_KEYS = ("title", "issue", "location", "explanation", "fix")


def description_items(run_dir):
    """The `pr-description` agent's mismatches as Process items desc-1, desc-2 … — they go into the report as written
    (save.py checked the quote and the location); texts.json may reword one through process_overrides.<id>."""
    f = run_dir / "out" / "pr-description.json"
    if not f.exists():
        return []
    return [{"id": f"desc-{i}", "title": DESC_TITLE[m["kind"]], "issue": m["issue"],
             "location": m.get("location") or "PR body" if m["kind"] == "not described" else "PR body",
             "explanation": m["explanation"], "fix": m["fix"], "_quote": m.get("quote")}
            for i, m in enumerate(json.loads(f.read_text(encoding="utf-8"))["mismatches"], 1)]


def load(run_dir):
    cands = {c["id"]: c for c in json.loads((run_dir / "candidates.json").read_text(encoding="utf-8"))["candidates"]}
    scores = {}
    for f in sorted(run_dir.glob("out/score-*.json")):
        for s in json.loads(f.read_text(encoding="utf-8"))["scores"]:
            scores[s["id"]] = s
    missing = [c for c in cands if c not in scores]
    if missing:
        raise ValueError(f"no score for {', '.join(missing)} — a scorer didn't save (re-launch it)")
    desc_f = run_dir / "out" / "describer.json"
    desc = json.loads(desc_f.read_text(encoding="utf-8")) if desc_f.exists() else None
    return cands, scores, desc


def root(cid, scores):
    """The candidate a `same_as` duplicate stands for: follow the chain to one with no same_as (save.py
    refuses chains, this is the fallback for older runs). A loop ends at the last id before it repeats."""
    seen = [cid]
    while scores[seen[-1]].get("same_as") in scores and scores[seen[-1]]["same_as"] not in seen:
        seen.append(scores[seen[-1]]["same_as"])
    return seen[-1]


def kept(cands, scores):
    keep = {}
    for cid, s in scores.items():
        if s["score"] >= 50 and not s.get("same_as"):
            keep[cid] = {"c": cands[cid], "s": s, "dups": []}
    for cid, s in scores.items():
        if s.get("same_as") and root(cid, scores) in keep:
            keep[root(cid, scores)]["dups"].append(cands[cid])
    return dict(sorted(keep.items(), key=lambda kv: (ORDER.index(kv[1]["s"]["severity"]), int(kv[0][1:]))))


def words(text):
    ids = set(re.findall(r"`([^`]+)`", text))
    return {w for w in re.findall(r"[a-z][a-z0-9_]{3,}", text.lower()) if w not in STOP} | {i.lower() for i in ids}


def code_terms(text):
    """Code identifiers in backticks (4+ chars, one token) — two findings naming the same one may be one problem."""
    return {m for m in re.findall(r"`([A-Za-z_$][\w$.]{3,})`", text)}


def similar_pairs(keep):
    items = list(keep.items())
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            if a["s"]["category"] != b["s"]["category"]:
                continue
            ta = a["c"]["claim"] + " " + " ".join(d["claim"] for d in a["dups"])
            tb = b["c"]["claim"] + " " + " ".join(d["claim"] for d in b["dups"])
            wa, wb = words(ta), words(tb)
            j_ = len(wa & wb) / max(1, len(wa | wb))
            shared = code_terms(ta) & code_terms(tb)
            if j_ >= SIMILAR or shared:
                out.append((items[i][0], items[j][0],
                            f"shares {', '.join(f'`{x}`' for x in sorted(shared))}" if shared else f"word overlap {j_:.2f}"))
    return out


def ref(cid):
    return cid.lower()


def is_update(run_dir):
    ctx = json.loads((run_dir / "context.json").read_text(encoding="utf-8"))
    return ctx["mode"] == "update", ctx


def compose(run_dir):
    cands, scores, desc = load(run_dir)
    update, ctx = is_update(run_dir)
    keep = kept(cands, scores)
    pairs = similar_pairs(keep)
    L = ["# Compose findings — review-and-comment-pr", "",
         "Write `texts.json` in the run folder (shape at the end), then run",
         "`python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder> --texts`",
         "and `render.py`. Scores, severity, category and location are the scorers' — don't change them.",
         "Text rules, code placeholders and `[[ref:<id>]]` are in `references/findings-format.md`.",
         "A finding's precedent (existing pattern / deferred) is the scorer's tag — render.py shows it; "
         "don't repeat it in the explanation.", ""]
    if pairs:
        L += ["## Look alike — same problem?", "",
              "If a pair below is one problem, put `\"merge\": {\"<drop id>\": \"<keep id>\"}` in texts.json "
              "and give the kept one the other's evidence; otherwise leave both.", ""]
        L += [f"- `{ref(a)}` and `{ref(b)}` — {why}" for a, b, why in pairs] + [""]
    L += ["## Findings", ""]
    for cid, k in keep.items():
        c, s = k["c"], k["s"]
        p = s.get("precedent")
        L += [f"### `{ref(cid)}` — {s['severity']} · {s['category']} · `{s['location']}` · score {s['score']}"
              + (f" · precedent: {p['kind']} ({p['ref']})" if p else ""),
              f"- **Claim** ({c['source']}): {c['claim']}",
              f"- **Scorer:** {s['reason']}"]
        if c.get("precedent"):
            L.append(f"- **Precedent:** {c['precedent']}")
        if c.get("discussion"):
            L.append(f"- **Review discussion:** {c['discussion']}")
        L.append(f"- **Evidence:**\n\n{c['evidence']}\n")
        for d in k["dups"]:
            L.append(f"- **Same problem, also from {d['source']}:** {d['claim']}\n\n{d['evidence']}\n")
        if s["category"] == "Bug":
            L.append("- Bug: add its scenario to `edge_cases` in texts.json.")
        L.append("")
    dropped = sorted((c for c in scores.values() if c["score"] < 50), key=lambda s: int(s["id"][1:]))
    if dropped:
        L += ["## Scored below 50 (not in the report)", ""]
        L += [f"- `{s['id']}` {s['score']}: {cands[s['id']]['claim'][:140]}" for s in dropped] + [""]
    if desc and desc.get("acceptance"):
        L += ["## Acceptance grading (for the summary)", ""]
        L += [f"- {a['status']}: {a['criterion']}" for a in desc["acceptance"]] + [""]
    if update:
        rows = quotes.earlier_rows(ctx["report"]["path"], ctx["pr"]["head"]["short"])
        agf = run_dir / "out" / "earlier-findings.json"
        ag = json.loads(agf.read_text(encoding="utf-8"))["earlier"] if agf.exists() else {}
        L += ["## Earlier findings (for `earlier`)", "",
              ("The `earlier-findings` agent checked each of them at the new head; its status, note and evidence are below "
               "and already in the template. Keep the statuses — change one only if another agent's result shows "
               "it wrong, and say why in the note — and reword a note only for the reader. Don't open the code "
               "yourself." if ag else
               "**The `earlier-findings` agent's result is missing (`out/earlier-findings.json`)** — re-launch it as in Step 4 "
               "before writing texts.json.")
              + " In a note, name earlier findings by number (`CR2`), this Update's own by `[[ref:<id>]]`. "
              "render.py refuses a list with one left out.", ""]
        for n, sev, issue, loc in rows:
            L.append(f"- {n} {sev} — {issue} — {loc}")
            if n in ag:
                L.append(f"  - **{ag[n]['status']}** — {ag[n]['note']} _(evidence: {ag[n]['evidence']})_")
        if not rows:
            L.append("- none")
        L += [""]
        tmpl = {"earlier": {n: ({"status": ag[n]["status"], "note": ag[n]["note"]} if n in ag
                                else {"status": "fixed | partly | open | dropped", "note": ""}) for n, *_ in rows},
                "confidence": "High | Medium | Low",
                "findings": {ref(cid): {k: "" for k in TEXT_KEYS} for cid in keep},
                "merge": {}, "provenance_extra": []}
    else:
        tmpl = {"summary": "2–4 sentences", "confidence": "High | Medium | Low",
                "index_affected": "touched surface, ≤ 40 words, no verdict",
                "findings": {ref(cid): {k: "" for k in TEXT_KEYS} for cid in keep},
                "edge_cases": ["scenario behind each Bug finding, citing [[ref:<id>]]"],
                "merge": {}, "provenance_extra": []}
    desc_items = description_items(run_dir)
    L += ["## PR description vs code (Process items)", "",
          ("These go into the report as Process items as written — you can't drop one. To reword one for the "
           "reader, put `\"process_overrides\": {\"<id>\": {\"issue\": \"…\", \"explanation\": \"…\", "
           "\"fix\": \"…\"}}` in texts.json; name one in a text as `[[ref:<id>]]`." if desc_items else
           ("None — the description matches the code." if (run_dir / "out" / "pr-description.json").exists()
            else "No result (`out/pr-description.json` is missing — the PR description is empty, or re-launch the "
                 "`pr-description` agent as in Step 4).")), ""]
    for d in desc_items:
        L += [f"- `{d['id']}` — {d['title']} · {d['location']}: {d['issue']}"
              + (f"\n  - Quote: \"{d['_quote']}\"" if d.get("_quote") else ""),
              f"  - {d['explanation']}", f"  - _Fix:_ {d['fix']}"]
    L += [""] if desc_items else []
    L += ["## texts.json shape", "",
          "Optional: `fixes` — exact replacements after the fact-check, copied from `out/factcheck.json`: "
          "`[{\"field\": \"overview.how\", \"old\": \"…\", \"new\": \"…\"}]` (fields as in findings.json: "
          "overview.what/how/affects, qa.core_path[i], qa.edge_cases[i], findings.<id>.issue/title/explanation/fix); "
          "`process` / `process_overrides` as in findings-format.md.", "",
          "```json", json.dumps(tmpl, indent=1, ensure_ascii=False), "```", ""]
    (run_dir / "compose.md").write_text("\n".join(L), encoding="utf-8")
    bugs = sum(1 for k in keep.values() if k["s"]["category"] == "Bug")
    print(f"{len(keep)} findings to write ({bugs} Bug), {len(scores) - len(keep)} candidates dropped "
          f"(below 50 or same_as), {len(pairs)} look-alike pair(s), "
          f"{len(desc_items)} Process item(s) from the PR description check.\n"
          f"Read {run_dir / 'compose.md'}, write {run_dir / 'texts.json'}, then run with --texts."
          + ("\nWARNING: out/earlier-findings.json is missing — re-launch the `earlier-findings` agent (Step 4) first."
             if update and not (run_dir / "out" / "earlier-findings.json").exists() else ""))
    return 0


FIELD = re.compile(r"^overview\.(what|how|affects)$|^qa\.(core_path|edge_cases)\[(\d+)\]$"
                   r"|^findings\.([a-z0-9-]+)\.(issue|title|explanation|fix|location)$")


def apply_fix(fx, w, ov, qa, by_id, errors):
    """One exact replacement in the assembled text: overview.how, qa.edge_cases[3], findings.c12.explanation."""
    m = FIELD.match(fx["field"])
    if not m:
        errors.append(f"{w}.field: {fx['field']!r} — overview.what|how|affects, qa.core_path[i], "
                      "qa.edge_cases[i] or findings.<id>.issue|title|explanation|fix|location")
        return
    if m.group(1):
        get, put = (lambda: ov.get(m.group(1), "")), (lambda v: ov.__setitem__(m.group(1), v))
    elif m.group(2):
        lst, idx = qa.get(m.group(2), []), int(m.group(3))
        if idx >= len(lst):
            errors.append(f"{w}.field: {fx['field']} — qa.{m.group(2)} has {len(lst)} entries")
            return
        get, put = (lambda: lst[idx]), (lambda v: lst.__setitem__(idx, v))
    else:
        f = by_id.get(m.group(4))
        if f is None:
            errors.append(f"{w}.field: no finding {m.group(4)!r} (merged or not kept?)")
            return
        get, put = (lambda: f[m.group(5)]), (lambda v: f.__setitem__(m.group(5), v))
    cur = get()
    if cur.count(fx["old"]) != 1:
        errors.append(f"{w}.old: found {cur.count(fx['old'])} times in {fx['field']} — must match exactly once")
        return
    put(cur.replace(fx["old"], fx["new"]))


def build(run_dir):
    cands, scores, desc = load(run_dir)
    update, ctx = is_update(run_dir)
    keep = kept(cands, scores)
    try:
        t = json.loads((run_dir / "texts.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: {run_dir / 'texts.json'} not found — write it from compose.md first")
        return 1
    except ValueError as e:
        print(f"INVALID texts.json — not valid JSON: {e}")
        return 1
    errors = []
    allowed = {"summary", "confidence", "index_affected", "earlier", "findings", "edge_cases", "merge",
               "provenance_extra",
               "overview", "qa", "process", "process_overrides", "fixes", "scope"}
    for k in t:
        if k not in allowed:
            errors.append(f"{k}: unknown key (allowed: {', '.join(sorted(allowed))})")
    ids = {ref(c): c for c in keep}
    merge = t.get("merge") or {}
    for a, b in merge.items():
        if a not in ids or b not in ids or a == b:
            errors.append(f"merge.{a}: both ids must be findings from compose.md and differ")
    texts = t.get("findings") or {}
    for rid in ids:
        if rid in merge:
            continue
        f = texts.get(rid)
        if not isinstance(f, dict):
            errors.append(f"findings.{rid}: missing")
            continue
        for k in TEXT_KEYS:
            if not isinstance(f.get(k), str) or not f[k].strip():
                errors.append(f"findings.{rid}.{k}: missing or empty")
    for rid in texts:
        if rid not in ids:
            errors.append(f"findings.{rid}: not a finding in compose.md")
    if update:  # a status per earlier finding; render.py checks it in full
        if not isinstance(t.get("earlier"), dict) or not t["earlier"]:
            errors.append("earlier: missing — the object from compose.md, one entry per earlier finding")
        if not isinstance(t.get("confidence"), str) or not t["confidence"].strip():
            errors.append("confidence: missing or empty — High, Medium or Low for the PR at this head")
    else:
        for k in ("summary", "confidence", "index_affected"):
            if not isinstance(t.get(k), str) or not t[k].strip():
                errors.append(f"{k}: missing or empty")
        if "earlier" in t:
            errors.append("earlier: exists only on an Update")
    desc_items = {d["id"]: d for d in description_items(run_dir)}
    overrides = dict(t.get("process_overrides") or {})
    for pid in [k for k in overrides if k in desc_items]:
        ov_ = overrides.pop(pid)
        bad = [k for k in (ov_ if isinstance(ov_, dict) else {"": 0}) if k not in PROCESS_KEYS]
        if bad:
            errors.append(f"process_overrides.{pid}: unknown key(s) {', '.join(map(repr, bad))} "
                          f"(allowed: {', '.join(PROCESS_KEYS)})")
        else:
            desc_items[pid].update({k: v for k, v in ov_.items() if isinstance(v, str) and v.strip()})
    if not desc and not t.get("overview"):
        errors.append("overview: no describer result — write overview and qa yourself")
    if errors:
        print(f"INVALID texts.json — {len(errors)} error(s), findings.json not written:\n  " + "\n  ".join(errors))
        return 1
    findings = []
    for rid, cid in ids.items():
        if rid in merge:
            continue
        s = keep[cid]["s"]
        findings.append(dict({"id": rid, "score": s["score"], "severity": s["severity"], "category": s["category"],
                              "location": s["location"], "precedent": s.get("precedent")},
                             **{k: texts[rid][k] for k in TEXT_KEYS}))
    ov = dict((desc or {}).get("overview") or {}, **(t.get("overview") or {}))
    qa = dict((desc or {}).get("qa") or {}, **(t.get("qa") or {}))
    qa = {k: list(v) for k, v in qa.items()}
    qa["edge_cases"] = list(qa.get("edge_cases") or []) + [x for x in t.get("edge_cases") or []
                                                            if not x.startswith("scenario behind each Bug")]
    by_id = {f["id"]: f for f in findings}
    for i, fx in enumerate(t.get("fixes") or []):  # exact replacements, e.g. from the fact-check
        w = f"fixes[{i}]"
        if not isinstance(fx, dict) or not all(isinstance(fx.get(k), str) for k in ("field", "old", "new")):
            errors.append(f"{w}: needs field, old, new (strings)")
            continue
        apply_fix(fx, w, ov, qa, by_id, errors)
    if errors:
        print(f"INVALID texts.json — {len(errors)} error(s), findings.json not written:\n  " + "\n  ".join(errors))
        return 1
    fd = {"schema_version": 1, "summary": t.get("summary", ""), "confidence": t.get("confidence", ""),
          "findings": findings,
          "process": [{k: v for k, v in d.items() if not k.startswith("_")} for d in desc_items.values()]
          + (t.get("process") or []),
          "process_overrides": overrides,
          "overview": ov, "qa": qa, "provenance_extra": t.get("provenance_extra") or [],
          "index_affected": t.get("index_affected", ""),
          "scope": t["scope"] if "scope" in t else (desc or {}).get("scope")}
    if update:
        fd["earlier"] = t["earlier"]
    # what the scorers checked and dropped: the full table only in the KB report (never posted); the ones a
    # reviewer raised (`discussion`) are also answered in the comment — render.py, "Review comments not taken up"
    # a duplicate whose candidate was dropped goes with it: that candidate's score and reason, its own claim
    # and discussion (a reviewer's comment it cites still gets its answer)
    keep_ids = set(kept(cands, scores))
    drop = {cid: scores[root(cid, scores)] for cid in scores if root(cid, scores) not in keep_ids}
    fd["dismissed"] = [{"score": s["score"], "claim": cands[cid]["claim"], "location": cands[cid]["location"],
                        "reason": s["reason"], "discussion": cands[cid].get("discussion") or ""}
                       for cid, s in sorted(drop.items(), key=lambda kv: (-kv[1]["score"], int(kv[0][1:])))]
    (run_dir / "findings.json").write_text(json.dumps(fd, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"findings.json written: {len(findings)} findings ({len(merge)} merged). Now run render.py.")
    return 0


def main(argv):
    if len(argv) not in (2, 3) or argv[0] != "--run" or (len(argv) == 3 and argv[2] != "--texts"):
        print(__doc__)
        return 2
    run_dir = Path(argv[1])
    try:
        return build(run_dir) if len(argv) == 3 else compose(run_dir)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
