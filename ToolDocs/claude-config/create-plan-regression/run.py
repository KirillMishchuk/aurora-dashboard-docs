#!/usr/bin/env python3
"""Regression check for the create-plan skill's script (scripts/plan.py) — no agents, no network,
nothing written to the real DOCS or repo.

Each fixture in fixtures/<name>/ is a sequence of plan.py calls (steps.json) with the answers git,
GitHub and image downloads gave when it was recorded (calls.json, replayed through
CREATE_PLAN_REPLAY) and the planner's plans (*.md, fed to `save` on stdin). The script runs the
steps in a temp SAP folder — DOCS copied from docs-base/, an empty aurora-dashboard/ — and compares
with golden/<name>/:

  log.txt      every step: command, exit code, output
  docs.diff    what the steps changed in DOCS (unified diff against docs-base/)
  run/<file>   the run folder (task.md, context.json, github.md, plan.md, written.json)

  run.py --skill <create-plan skill dir> [--only <fixture>] [--update]

--update writes the current results as the new golden (after you've checked the diff).
Exit 0 = every output equals golden; 1 = differences (listed, with a unified diff per file).

steps.json: {"today": "YYYY-MM-DD", "steps": [{"args": [...], "stdin": "<file in the fixture>"}]}.
In args, {RUNS} stands for <repo>/.claude/runs/create-plan.
"""
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
FIXTURES, GOLDEN, DOCS_BASE = HERE / "fixtures", HERE / "golden", HERE / "docs-base"


def tree_diff(a, b):
    out = []
    files = sorted({str(p.relative_to(a)) for p in a.rglob("*") if p.is_file()} |
                   {str(p.relative_to(b)) for p in b.rglob("*") if p.is_file()})
    for f in files:
        x = (a / f).read_text(encoding="utf-8").splitlines() if (a / f).is_file() else []
        y = (b / f).read_text(encoding="utf-8").splitlines() if (b / f).is_file() else []
        if x != y:
            out += list(difflib.unified_diff(x, y, f"base/{f}", f"now/{f}", lineterm="", n=2))
    return "\n".join(out) + ("\n" if out else "")


def replay(script, fx, tmp):
    sap = tmp / "SAP"
    docs, repo = sap / "DOCS", sap / "aurora-dashboard"
    shutil.copytree(DOCS_BASE, docs)
    if (fx / "docs-extra").is_dir():
        shutil.copytree(fx / "docs-extra", docs, dirs_exist_ok=True)
    repo.mkdir(parents=True)
    spec = json.loads((fx / "steps.json").read_text(encoding="utf-8"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", CREATE_PLAN_REPLAY=str(fx),
               CREATE_PLAN_MAIN=str(repo), CREATE_PLAN_TODAY=spec["today"])
    env.pop("CREATE_PLAN_RECORD", None)
    runs = repo / ".claude" / "runs" / "create-plan"
    log = []
    for st in spec["steps"]:
        args = [x.replace("{RUNS}", str(runs)) for x in st["args"]]
        stdin = (fx / st["stdin"]).read_text(encoding="utf-8") if st.get("stdin") else ""
        p = subprocess.run([sys.executable, str(script)] + args, cwd=repo, input=stdin,
                           capture_output=True, text=True, env=env)
        shown = " ".join(st["args"]) + (f" < {st['stdin']}" if st.get("stdin") else "")
        log.append(f"$ plan.py {shown}\nexit {p.returncode}\n{(p.stdout + p.stderr).rstrip()}\n")
    res = {"log.txt": "\n".join(log), "docs.diff": tree_diff(DOCS_BASE_COPY(docs, fx, tmp), docs)}
    if runs.is_dir():
        for f in sorted(runs.rglob("*")):
            if f.is_file() and f.suffix in (".md", ".json"):
                res["run/" + str(f.relative_to(runs))] = f.read_text(encoding="utf-8")
    return res, {str(sap): "<SAP>", str(script): "<SCRIPT>", str(script.parent): "<SCRIPTS>"}


def DOCS_BASE_COPY(docs, fx, tmp):
    """docs-base plus the fixture's docs-extra: the DOCS the steps started from."""
    base = tmp / "base"
    if not base.exists():
        shutil.copytree(DOCS_BASE, base)
        if (fx / "docs-extra").is_dir():
            shutil.copytree(fx / "docs-extra", base, dirs_exist_ok=True)
    return base


def normalize(text, subst):
    for a, b in sorted(subst.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(a, b)
    return text


def main(argv):
    a = {"--skill": None, "--only": None}
    update = "--update" in argv
    it = iter([x for x in argv if x != "--update"])
    for x in it:
        if x not in a:
            print(__doc__)
            return 2
        a[x] = next(it, None)
    if not a["--skill"]:
        print(__doc__)
        return 2
    script = Path(a["--skill"]).expanduser().resolve() / "scripts" / "plan.py"
    if not script.is_file():
        print(f"{script} not found")
        return 2
    fixtures = [f for f in sorted(FIXTURES.iterdir()) if f.is_dir() and (not a["--only"] or f.name == a["--only"])]
    changed = 0
    for fx in fixtures:
        with tempfile.TemporaryDirectory(prefix="cpr-") as t:
            raw, subst = replay(script, fx, Path(t).resolve())
            res = {k: normalize(v, subst) for k, v in raw.items()}
        gdir = GOLDEN / fx.name
        if update:
            if gdir.exists():
                shutil.rmtree(gdir)
            for k, v in res.items():
                (gdir / k).parent.mkdir(parents=True, exist_ok=True)
                (gdir / k).write_text(v, encoding="utf-8")
            print(f"{fx.name}: golden written ({len(res)} files)")
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
