#!/usr/bin/env python3
"""Bring this machine's review-and-comment-pr install up to the version in DOCS: skill, agents, hook, settings.

    python3 sync_install.py            # dry run: what differs and what would change
    python3 sync_install.py --apply    # back up, copy, merge settings; then check again

Source of truth (all in DOCS, pulled from the main machine):
  skill, agents, hook   ../aurora-dashboard-config/.claude/{skills/review-and-comment-pr, agents/<3>, hooks/check_report_md.py}
  settings              the JSON block in ../review-and-comment-pr-remote-setup.md (Install step 4), <parent> filled in

Target: <parent>/aurora-dashboard/.claude/. Settings are merged, never replaced: missing allow/deny entries
are appended, the listed flags, env and hooks are set; entries this machine has on top are kept and listed.
Everything replaced is first copied to <parent>/review-runs/_install-backups/<time>/.
Exit: 0 = in sync (after --apply: now in sync), 1 = differs (dry run) or a check failed.
"""
import filecmp, json, platform, re, shutil, sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
CFG = HERE.parent.parent                       # DOCS/ToolDocs/claude-config
DOCS = CFG.parent.parent
PARENT = DOCS.parent
REPO = PARENT / "aurora-dashboard"
SRC = CFG / "aurora-dashboard-config" / ".claude"
DST = REPO / ".claude"
SETUP = CFG / "review-and-comment-pr-remote-setup.md"
SKILL = "skills/review-and-comment-pr"
AGENTS = [f"agents/{a}.md" for a in ("pr-reviewer", "external-api-checker", "security-reviewer")]
HOOK = "hooks/check_report_md.py"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def files(d):
    return {p.relative_to(d) for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"}


def tree_diff(src, dst):
    """(new, changed, extra) relative paths."""
    a, b = files(src), files(dst) if dst.is_dir() else set()
    return (sorted(a - b), sorted(p for p in a & b if not filecmp.cmp(src / p, dst / p, shallow=False)), sorted(b - a))


def template():
    m = re.search(r"```json\n(.*?)```", SETUP.read_text(encoding="utf-8"), re.S)
    if not m:
        sys.exit(f"no JSON block in {SETUP}")
    t = json.loads(m.group(1).replace("/<parent>", str(PARENT)).replace("<parent>", str(PARENT)))
    if platform.system() == "Darwin":  # /tmp is /private/tmp there
        t["permissions"]["allow"].append("Edit(//private/tmp/pr-*-comment.md)")
    t["permissions"]["allow"] = [re.sub(r"^Read\(/(?!/)", "Read(//", x) for x in t["permissions"]["allow"]]
    return t


def merge(cur, t):
    """(merged settings, list of changes)"""
    new, ch = json.loads(json.dumps(cur)), []
    perms = new.setdefault("permissions", {})
    for key in ("allow", "deny"):
        have = perms.setdefault(key, [])
        for x in t["permissions"].get(key, []):
            if x not in have:
                have.append(x)
                ch.append(f"permissions.{key} += {x}")
    for k, v in t.items():
        if k in ("permissions", "hooks", "env"):
            continue
        if new.get(k) != v:
            ch.append(f"{k}: {new.get(k)!r} -> {v!r}")
            new[k] = v
    for k, v in (t.get("env") or {}).items():
        if (new.get("env") or {}).get(k) != v:
            ch.append(f"env.{k}: {(new.get('env') or {}).get(k)!r} -> {v!r}")
            new.setdefault("env", {})[k] = v
    for event, entries in (t.get("hooks") or {}).items():
        have = new.setdefault("hooks", {}).setdefault(event, [])
        for e in entries:
            cmds = {h.get("command") for x in have if x.get("matcher") == e["matcher"] for h in x.get("hooks", [])}
            if not all(h["command"] in cmds for h in e["hooks"]):
                have.append(e)
                ch.append(f"hooks.{event} += {e['matcher']} → {e['hooks'][0]['command']}")
    return new, ch


def main(apply):
    if not (REPO / ".git").exists():
        sys.exit(f"no aurora-dashboard clone at {REPO} (layout: <parent>/aurora-dashboard next to <parent>/DOCS)")
    backup = PARENT / "review-runs" / "_install-backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    differs = False
    print(f"DOCS {DOCS}\nrepo {REPO}\n")

    # 1. skill folder (mirror), agents, hook
    new, changed, extra = tree_diff(SRC / SKILL, DST / SKILL)
    for name, lst in (("new", new), ("changed", changed), ("only here (removed by --apply)", extra)):
        if lst:
            differs = True
            print(f"skill {name}: " + ", ".join(map(str, lst)))
    for rel in AGENTS + [HOOK]:
        s, d = SRC / rel, DST / rel
        if not d.exists() or not filecmp.cmp(s, d, shallow=False):
            differs = True
            print(f"{rel}: {'missing' if not d.exists() else 'differs'}")
    if apply and differs:
        if (DST / SKILL).exists():
            shutil.copytree(DST / SKILL, backup / SKILL, ignore=IGNORE)
            shutil.rmtree(DST / SKILL)
        shutil.copytree(SRC / SKILL, DST / SKILL, ignore=IGNORE)
        for rel in AGENTS + [HOOK]:
            if (DST / rel).exists():
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(DST / rel, backup / rel)
            (DST / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC / rel, DST / rel)
        print("copied skill, agents, hook")

    # 2. settings.local.json
    sp = DST / "settings.local.json"
    cur = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    t = template()
    merged, ch = merge(cur, t)
    if ch:
        differs = True
        print("\nsettings.local.json would change:" if not apply else "\nsettings.local.json:")
        for c in ch:
            print("  " + c)
    stale = [x for x in cur.get("permissions", {}).get("allow", [])
             if "review-and-comment-pr" in x and x not in t["permissions"]["allow"]]
    if stale:
        print("  kept, but not in the template (old paths?): " + ", ".join(stale))
    if apply and ch:
        if sp.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, backup / "settings.local.json")
        sp.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("settings.local.json written")
    if apply and backup.exists():
        print(f"\nbackup: {backup}")

    # 3. check
    if apply:
        ok = not any(tree_diff(SRC / SKILL, DST / SKILL)) and all(
            filecmp.cmp(SRC / r, DST / r, shallow=False) for r in AGENTS + [HOOK]) and not merge(
            json.loads(sp.read_text(encoding="utf-8")), t)[1]
        print("\nin sync" if ok else "\nSTILL DIFFERS — check by hand")
        print("Restart Claude Code (settings, agents and hooks are read at start); check /agents and /hooks.")
        return 0 if ok else 1
    print("\nin sync" if not differs else "\ndiffers — run with --apply (after the user agrees)")
    return 1 if differs else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a not in ([], ["--apply"]):
        sys.exit(__doc__)
    sys.exit(main(a == ["--apply"]))
