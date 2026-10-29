#!/usr/bin/env python3
"""Regression check for the review-and-comment-pr skill — no agents, no network, no DOCS writes.

Each fixture is a saved run (context.json, discussion.json, PR body, issues, the agents' out/*.json,
texts.json, and for an Update the report as it was before). The script replays every scripted step on
a temp copy and compares the results with golden/<fixture>/:

  briefs.py find, briefs.py score (+ candidates.json), save.py on every out/*.json,
  assemble.py (compose.md), assemble.py --texts (findings.json), render.py --dry-run (report.md),
  prepare_comment.py's slice (comment.md), briefs.py factcheck

  run.py --skill <skill dir> --repo <aurora-dashboard checkout> [--sap <SAP root>] [--only <fixture>] [--update]

--skill  e.g. ~/projects/SAP/aurora-dashboard/.claude/skills/review-and-comment-pr (or a copy with
         agents/ and hooks/ two levels up, so the Markdown hook runs)
--repo   the aurora-dashboard git checkout; it must have the fixtures' commits (git cat-file)
--sap    what "{{SAP}}" in the fixtures stands for (default: the repo's parent)
--update write the current results as the new golden (after you've checked the diff)

Exit 0 = every output equals golden; 1 = differences (listed, with a unified diff per file).
Run it before and after every change to the skill; an unexpected difference is a regression.
"""
import datetime
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
GOLDEN = HERE / "golden"


def sh(args, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    return (p.stdout + p.stderr), p.returncode


def prepare(fx, tmp, sap):
    run = tmp / fx.name
    shutil.copytree(fx, run)
    for f in run.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".md"):
            s = f.read_text(encoding="utf-8")
            if "{{SAP}}" in s:
                f.write_text(s.replace("{{SAP}}", str(sap)), encoding="utf-8")
    ctx = json.loads((run / "context.json").read_text(encoding="utf-8"))
    ctx["run_dir"] = str(run)
    if (run / "report-before.md").exists():  # an Update renders against the report as it was
        ctx["report"]["path"] = str(run / "report-before.md")
    (run / "context.json").write_text(json.dumps(ctx, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.copytree(run / "out", run / "_out")
    return run, ctx


def restore_out(run):
    for f in (run / "_out").glob("*.json"):
        shutil.copy(f, run / "out" / f.name)


def delta(S, ctx):
    """collect.py's delta.diff for an Update (git only, no gh) — base changes merged into the PR's files."""
    old, head = ctx["report"]["delta"].split("..")
    sys.path.insert(0, str(S))
    try:
        import collect
        note = {}
        try:
            d = collect.delta_diff(old, head, ctx["pr"]["files"], ctx["repo"]["root"],
                                   base=ctx["pr"]["base"]["oid"], note=note)
        except TypeError:  # an older collect.py without base/note
            d = collect.delta_diff(old, head, ctx["pr"]["files"], ctx["repo"]["root"])
        return d, json.dumps(note, indent=1) + "\n"
    finally:
        sys.path.remove(str(S))
        sys.modules.pop("collect", None)


def replay(skill, run, ctx):
    S = skill / "scripts"
    res = {}
    if ctx["mode"] == "update" and ".." in str(ctx["report"].get("delta")):
        res["delta.diff"], res["delta-note.json"] = delta(S, ctx)
    out, rc = sh([sys.executable, str(S / "briefs.py"), "--run", str(run), "find"])
    res["log/find.txt"] = f"exit {rc}\n{out}"
    for b in sorted((run / "briefs").glob("*.md")) if (run / "briefs").exists() else []:
        res[f"briefs-find/{b.name}"] = b.read_text(encoding="utf-8")
    restore_out(run)
    out, rc = sh([sys.executable, str(S / "briefs.py"), "--run", str(run), "score"])
    res["log/score.txt"] = f"exit {rc}\n{out}"
    for b in sorted((run / "briefs").glob("score-*.md")) if (run / "briefs").exists() else []:
        res[f"briefs-score/{b.name}"] = b.read_text(encoding="utf-8")
    if (run / "candidates.json").exists():
        res["candidates.json"] = (run / "candidates.json").read_text(encoding="utf-8")
    restore_out(run)
    lines = []
    for f in sorted((run / "_out").glob("*.json")):
        p = subprocess.run([sys.executable, str(S / "save.py"), "--run", str(run), "--as", f.stem],
                           input=f.read_text(encoding="utf-8"), capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        lines.append(f"## {f.stem}: exit {p.returncode}\n{(p.stdout + p.stderr).strip()}\n")
    res["log/save.txt"] = "\n".join(lines)
    restore_out(run)
    out, rc = sh([sys.executable, str(S / "assemble.py"), "--run", str(run)])
    res["log/assemble.txt"] = f"exit {rc}\n{out}"
    if (run / "compose.md").exists():
        res["compose.md"] = (run / "compose.md").read_text(encoding="utf-8")
    out, rc = sh([sys.executable, str(S / "assemble.py"), "--run", str(run), "--texts"])
    res["log/texts.txt"] = f"exit {rc}\n{out}"
    if rc == 0:
        res["findings.json"] = (run / "findings.json").read_text(encoding="utf-8")
        out, rc = sh([sys.executable, str(S / "render.py"), "--run", str(run), "--dry-run"])
        res["log/render.txt"] = f"exit {rc}\n{out}"
        if rc == 0 and (run / "report.md").exists():
            report = (run / "report.md").read_text(encoding="utf-8")
            res["report.md"] = report
            sys.path.insert(0, str(S))
            try:
                import prepare_comment
                text = report
                if ctx["mode"] == "update":  # the dry run writes only the block; slice it out of the report
                    text = Path(ctx["report"]["path"]).read_text(encoding="utf-8").rstrip() + "\n\n" + report
                body = prepare_comment.slice_comment(text, ctx["mode"] == "update")
                res["comment.md"] = prepare_comment.fit(body, ctx["report"]["path"])[0] \
                    if hasattr(prepare_comment, "fit") else body
            except Exception as e:  # noqa: BLE001 — recorded, compared like any output
                res["comment.md"] = f"ERROR: {e}\n"
            finally:
                sys.path.remove(str(S))
                sys.modules.pop("prepare_comment", None)
            out, rc = sh([sys.executable, str(S / "briefs.py"), "--run", str(run), "factcheck"])
            res["log/factcheck.txt"] = f"exit {rc}\n{out}"
            if (run / "briefs" / "factcheck.md").exists():
                res["briefs-factcheck.md"] = (run / "briefs" / "factcheck.md").read_text(encoding="utf-8")
    return res


def normalize(text, run, skill, repo, sap):
    for a, b in ((str(run), "<RUN>"), (str(skill), "<SKILL>"), (str(repo), "<REPO>"), (str(sap), "<SAP>")):
        text = text.replace(a, b)
    text = re.sub(r"/tmp[^\s'\"`)]*?/rpr-[^/\s]+", "<TMP>", text)
    text = text.replace(datetime.date.today().isoformat(), "<TODAY>")  # dates = the day the set runs
    text = re.sub(r"[ \t]+\(agent missing — [^\n]*", "", text)  # a skill copy without agents/ next to it
    return re.sub(r"(?m)^_Reviewed at head (.*) · (\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC)_$", r"_Reviewed at head \1 · <TIME>_", text)


def main(argv):
    a = {"--skill": None, "--repo": None, "--sap": None, "--only": None}
    update = "--update" in argv
    it = iter([x for x in argv if x != "--update"])
    for x in it:
        if x not in a:
            print(__doc__)
            return 2
        a[x] = next(it, None)
    if not a["--skill"] or not a["--repo"]:
        print(__doc__)
        return 2
    skill, repo = Path(a["--skill"]).expanduser().resolve(), Path(a["--repo"]).expanduser().resolve()
    sap = Path(a["--sap"]).expanduser().resolve() if a["--sap"] else repo.parent
    fixtures = [f for f in sorted(FIXTURES.iterdir()) if f.is_dir() and (not a["--only"] or f.name == a["--only"])]
    changed = 0
    for fx in fixtures:
        with tempfile.TemporaryDirectory(prefix="rpr-") as t:
            run, ctx = prepare(fx, Path(t), sap)
            ctx_repo = Path(ctx["repo"]["root"])
            res = {k: normalize(v, run, skill, ctx_repo, sap) for k, v in replay(skill, run, ctx).items()}
        gdir = GOLDEN / fx.name
        if update:
            for k, v in res.items():
                (gdir / k).parent.mkdir(parents=True, exist_ok=True)
                (gdir / k).write_text(v, encoding="utf-8")
            stale = [p for p in gdir.rglob("*") if p.is_file() and str(p.relative_to(gdir)) not in res]
            for p in stale:
                try:
                    p.unlink()
                except OSError:
                    print(f"  could not remove stale golden file {p} — delete it by hand")
            print(f"{fx.name}: golden written ({len(res)} files" + (f", {len(stale)} stale" if stale else "") + ")")
            continue
        gold = {str(p.relative_to(gdir)): p.read_text(encoding="utf-8") for p in gdir.rglob("*") if p.is_file()} \
            if gdir.exists() else {}
        diffs = []
        for k in sorted(set(gold) | set(res)):
            if gold.get(k) != res.get(k):
                diffs.append(k)
                d = difflib.unified_diff((gold.get(k) or "").splitlines(), (res.get(k) or "").splitlines(),
                                         f"golden/{k}", f"now/{k}", lineterm="", n=1)
                print(f"--- {fx.name}/{k}" + ("" if k in gold else " (new)") + ("" if k in res else " (gone)"))
                print("\n".join(list(d)[2:60]))
        print(f"{fx.name}: " + (f"{len(diffs)} file(s) differ" if diffs else f"OK ({len(res)} files)"))
        changed += bool(diffs)
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
