#!/usr/bin/env python3
"""create-plan: the parts of the skill that need no judgment.

  plan.py collect <issue|PR|follow-up N|URL> [--mine|--not-mine]   orchestrator, steps 1-2
  plan.py collect --text --label <slug> <<'TASK'                      … a task given in words
  plan.py save --run <dir> <<'PLAN'      dev-planner: check its plan and save it as <dir>/plan.md
  plan.py write --run <dir> ...          orchestrator, steps 4-5: plan file in DOCS, index row, Related
  plan.py followups --run <dir> ...      orchestrator, step 6: file the approved follow-ups

Run from the repo (any checkout or worktree): paths come from the common git dir.
Exit codes: 0 = done; 1 = problems listed (fix them and run again); 2 = usage;
3 = collect needs an answer from the user (the question is printed).

Regression tests (DOCS/ToolDocs/claude-config/create-plan-regression) set
CREATE_PLAN_REPLAY=<dir> (git, GitHub and downloads answered from <dir>/calls.json),
CREATE_PLAN_MAIN=<repo path> (replaces {{MAIN}} in those answers) and CREATE_PLAN_TODAY.
CREATE_PLAN_RECORD=<dir> records real answers into <dir>/calls.json to make a fixture.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True

SECTIONS = ["Overview", "Decisions", "Architecture Analysis", "Potential Problems & Mitigations",
            "Prerequisites", "Implementation Steps", "Testing Plan", "Acceptance Criteria",
            "Open Questions", "Proposed follow-ups"]
REQUIRED = ["Overview", "Architecture Analysis", "Potential Problems & Mitigations",
            "Implementation Steps", "Testing Plan", "Acceptance Criteria", "Open Questions"]
FU_FIELDS = ["Where", "What", "How to fix", "Why not in this plan"]
FU_REGISTRY_LABEL = {"Where": "Where", "What": "What", "How to fix": "How to fix",
                     "Why not in this plan": "Why not done right away"}
SEVERITIES = ["High", "Medium", "Low"]
ABS_PATH = re.compile(r"(?<![\w.~])/(?:Users|home|private|tmp|var|opt|Volumes|sessions)/[^\s`)\]]*")
RELATED_MARKER = "<!-- related:auto"
INDEX_HEADER = ("---\ntype: index\n---\n# Plans\n\n"
                "| Date | Task | Risks | Status | File |\n| --- | --- | --- | --- | --- |\n")
TASK_MAX = 200
REPO = "cobaltcore-dev/aurora-dashboard"
IMG_HOSTS = ("github.com/user-attachments/", "githubusercontent.com/")


class Problems(Exception):
    pass


# ---------- outside world: git, GitHub, downloads ----------

class Ext:
    """Every call outside the script goes through here, so the regression tests can replay it."""

    def __init__(self):
        self.replay = os.environ.get("CREATE_PLAN_REPLAY")
        self.record = os.environ.get("CREATE_PLAN_RECORD")
        self.main = os.environ.get("CREATE_PLAN_MAIN", "")
        self.calls = {}
        if self.replay:
            self.calls = json.loads((Path(self.replay) / "calls.json").read_text(encoding="utf-8"))

    def _call(self, key, fn):
        if self.replay:
            if key not in self.calls:
                raise Problems(f"replay: no recorded answer for `{key}`")
            return json.loads(json.dumps(self.calls[key]).replace("{{MAIN}}", self.main))
        v = fn()
        if self.record:
            p = Path(self.record) / "calls.json"
            have = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
            main = str(Path(git_common_dir_real()).parent)
            have[key] = json.loads(json.dumps(v).replace(main, "{{MAIN}}"))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(have, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return v

    def git(self, *args):
        def fn():
            r = subprocess.run(["git", *args], capture_output=True, text=True)
            return {"rc": r.returncode, "out": r.stdout.strip(), "err": r.stderr.strip()[-500:]}
        return self._call("git " + " ".join(args), fn)

    def api(self, path):
        """GET api.github.com/<path> through `gh api`, or unauthenticated curl without gh."""
        def fn():
            if shutil.which("gh"):
                r = subprocess.run(["gh", "api", "--method", "GET", path], capture_output=True, text=True)
                if r.returncode == 0:
                    return {"status": 200, "json": json.loads(r.stdout or "null")}
                m = re.search(r"HTTP (\d{3})", r.stderr)
                return {"status": int(m.group(1)) if m else 0, "json": None, "err": r.stderr.strip()[-300:]}
            r = subprocess.run(["curl", "-sS", "-H", "Accept: application/vnd.github+json", "-w", "\n%{http_code}",
                                f"https://api.github.com/{path}"], capture_output=True, text=True)
            body, _, code = r.stdout.rpartition("\n")
            st = int(code) if code.strip().isdigit() else 0
            try:
                js = json.loads(body) if st == 200 else None
            except ValueError:
                js, st = None, 0
            return {"status": st, "json": js, "err": (r.stderr.strip() or body[:200]) if st != 200 else ""}
        return self._call("api " + path, fn)

    def pages(self, path):
        out, page = [], 1
        while True:
            sep = "&" if "?" in path else "?"
            r = self.api(f"{path}{sep}per_page=100&page={page}")
            if r["status"] != 200:
                raise Problems(f"GitHub {path}: HTTP {r['status']} {r.get('err', '')}")
            out += r["json"]
            if len(r["json"]) < 100:
                return out
            page += 1

    def user(self):
        def fn():
            if not shutil.which("gh"):
                return {"login": None}
            r = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True)
            return {"login": r.stdout.strip() or None}
        return self._call("user", fn)["login"]

    def closing(self, n):
        def fn():
            if not shutil.which("gh"):
                return {"numbers": None}
            r = subprocess.run(["gh", "pr", "view", str(n), "--repo", REPO, "--json", "closingIssuesReferences",
                                "--jq", "[.closingIssuesReferences[].number]"], capture_output=True, text=True)
            return {"numbers": json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None}
        return self._call(f"closing {n}", fn)["numbers"]

    def download(self, url, dest):
        def fn():
            r = subprocess.run(["curl", "-sL", "--max-time", "60", "-o", str(dest), "-w", "%{http_code} %{content_type}",
                                url], capture_output=True, text=True)
            code, _, ctype = r.stdout.strip().partition(" ")
            return {"status": int(code) if code.isdigit() else 0, "type": ctype}
        v = self._call("download " + url, fn)
        ok = v["status"] == 200 and v["type"].startswith("image/")
        if self.replay and ok:
            dest.write_bytes(b"image placeholder (replay)\n")
        if not ok and dest.exists():
            dest.unlink()
        return ok, v


def git_common_dir_real():
    r = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True)
    return r.stdout.strip()


EXT = None


def ext():
    global EXT
    if EXT is None:
        EXT = Ext()
    return EXT


def git(*args, check=True):
    r = ext().git(*args)
    if check and r["rc"]:
        raise Problems(f"git {' '.join(args)} failed: {r['err']}")
    return r["out"]


def roots(docs_override=None, need_docs=True):
    main_root = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    sap = main_root.parent
    docs = Path(docs_override) if docs_override else sap / "DOCS"
    if need_docs and not (docs / "CLAUDE.md").is_file() and not docs_override:
        raise Problems(f"DOCS not found at {docs} — stop and tell the user; don't write anywhere else")
    return main_root, sap, docs


def today():
    return os.environ.get("CREATE_PLAN_TODAY") or datetime.date.today().isoformat()


# ---------- Markdown structure ----------

def headings(lines):
    """(index, level, title) for every ATX heading outside fenced code blocks."""
    out, fence = [], None
    for i, line in enumerate(lines):
        if fence:
            if re.fullmatch(r"\s*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
            continue
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            fence = m.group(1)
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
    return out


def in_code_mask(lines):
    mask, fence = [], None
    for line in lines:
        if fence:
            mask.append(True)
            if re.fullmatch(r"\s*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
            continue
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            fence = m.group(1)
            mask.append(True)
            continue
        mask.append(False)
    return mask


def section_span(lines, hs, start_idx, level, stop_at_marker=True):
    """End line (exclusive) of the section whose heading is at start_idx."""
    end = len(lines)
    for i, lvl, _ in hs:
        if i > start_idx and lvl <= level:
            end = i
            break
    if stop_at_marker:
        for i in range(start_idx + 1, end):
            if lines[i].startswith(RELATED_MARKER):
                return i
    return end


def table_rows(lines):
    rows = []
    for line in lines:
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", s[1:-1])]
            rows.append(cells)
    return rows


def analyse(text):
    """Parse a dev-planner plan (top level `##`). Returns (errors, info)."""
    errors = []
    lines = text.split("\n")
    hs = headings(lines)
    if text.lstrip().startswith("## Decisions needed"):
        return ["this is a `## Decisions needed` block — don't save it; return it as your reply"], {}
    if any(lvl == 1 for _, lvl, _ in hs):
        errors.append("remove the `# ` title — the caller adds the plan's title")
    if not text.lstrip().startswith("## Overview"):
        errors.append("the plan must start with `## Overview` (nothing before it)")
    h2 = [(i, t) for i, lvl, t in hs if lvl == 2]
    titles = [t for _, t in h2]
    for t in titles:
        if t not in SECTIONS:
            errors.append(f"`## {t}`: not a plan section. Allowed, in this order: {', '.join(SECTIONS)}. "
                          "Nothing goes after the last section — no file lists or summaries")
    for t, n in Counter(titles).items():
        if n > 1:
            errors.append(f"`## {t}` appears {n} times")
    known = [t for t in titles if t in SECTIONS]
    if known != sorted(known, key=SECTIONS.index):
        errors.append("sections out of order — use: " + ", ".join(SECTIONS))
    for t in REQUIRED:
        if t not in titles:
            errors.append(f"`## {t}` is missing")
    for n, line in enumerate(lines, 1):
        for m in ABS_PATH.finditer(line):
            errors.append(f"line {n}: absolute path `{m.group(0)}` — write it relative to the repo root "
                          "(outside the repo: `../local-mock-backend/...`, `../DOCS/...`)")

    def body(title):
        for i, t in h2:
            if t == title:
                end = section_span(lines, hs, i, 2)
                return i, end
        return None

    info = {"steps": 0, "severity": Counter(), "high": [], "open_questions": "", "followups": []}
    span = body("Implementation Steps")
    if span:
        steps = [t for i, lvl, t in hs if span[0] < i < span[1] and lvl == 3 and re.match(r"Step \d+\b", t)]
        nums = [int(re.match(r"Step (\d+)", t).group(1)) for t in steps]
        if nums != list(range(1, len(nums) + 1)):
            errors.append(f"steps must be `### Step 1: …`, `### Step 2: …` in order (found {nums})")
        info["steps"] = len(steps)
        if not steps and not "\n".join(lines[span[0] + 1:span[1]]).strip():
            errors.append("`## Implementation Steps` is empty — add the steps, or one line on why no code changes")
    span = body("Potential Problems & Mitigations")
    if span:
        rows = table_rows(lines[span[0] + 1:span[1]])
        if len(rows) < 3:
            errors.append("`## Potential Problems & Mitigations` needs the table `| Risk | Severity | Mitigation |` with a row per risk")
        else:
            header = [c.lower() for c in rows[0]]
            if "severity" not in header:
                errors.append("risk table: no `Severity` column")
            else:
                si = header.index("severity")
                for r in rows[2:]:
                    sev = r[si].split()[0].strip("*") if si < len(r) and r[si].split() else ""
                    if sev not in SEVERITIES:
                        errors.append(f"risk table: severity `{r[si] if si < len(r) else ''}` — start it with High, Medium or Low")
                        continue
                    info["severity"][sev] += 1
                    if sev == "High":
                        info["high"].append(r[0] + (f" — {r[si + 1]}" if si + 1 < len(r) else ""))
    span = body("Open Questions")
    if span:
        info["open_questions"] = "\n".join(lines[span[0] + 1:span[1]]).strip()
    span = body("Proposed follow-ups")
    if span:
        cands, cerr = candidates(lines, hs, span[0], 2, span[1])
        errors += cerr
        if not cands:
            errors.append("`## Proposed follow-ups` has no `### <title>` blocks — omit the section if there are none")
        info["followups"] = [c["title"] for c in cands]
    return errors, info


def candidates(lines, hs, start, level, end):
    """Follow-up candidates under the heading at `start` (one level deeper)."""
    out, errors = [], []
    subs = [(i, t) for i, lvl, t in hs if start < i < end and lvl == level + 1]
    for k, (i, title) in enumerate(subs):
        stop = subs[k + 1][0] if k + 1 < len(subs) else end
        fields, cur, gap = {}, None, False
        for line in lines[i + 1:stop]:
            m = re.match(r"^- \*\*(" + "|".join(map(re.escape, FU_FIELDS)) + r"):\*\*\s*(.*)$", line)
            if m:
                cur, gap = m.group(1), False
                fields[cur] = [m.group(2)]
            elif not line.strip() or line.strip() == "---":
                gap = gap or cur is not None
            elif cur and (line.startswith("  ") or not gap):
                fields[cur].append(line[2:] if line.startswith("  ") else line)
            else:
                errors.append(f"follow-up `{title}`: text after its fields (`{line.strip()[:60]}`) — "
                              "nothing goes after the plan's last section: no file lists, summaries or notes")
                break
        for f in FU_FIELDS:
            if f not in fields:
                errors.append(f"follow-up `{title}`: missing `- **{f}:**`")
        out.append({"title": title, "fields": fields, "start": i, "end": stop})
    return out, errors


def summary(info):
    sev = ", ".join(f"{info['severity'][s]} {s}" for s in SEVERITIES if info["severity"][s]) or "none"
    return (f"{info['steps']} steps · risks: {sev} · open questions: "
            f"{'yes' if info['open_questions'] and info['open_questions'].lower().strip('.') not in ('none', 'no') else 'none'}"
            f" · follow-ups: {len(info['followups'])}")


def shift_headings(text, by=1):
    lines = text.split("\n")
    mask = in_code_mask(lines)
    return "\n".join(("#" * by + l if (not c and re.match(r"^#{1,5}\s", l)) else l)
                     for l, c in zip(lines, mask))


def cell(s):
    return re.sub(r"(?<!\\)\|", r"\\|", " ".join(s.split()))


# ---------- collect (steps 1-2) ----------

def md_comments(items, title="Comments"):
    out = []
    for c in items:
        body = (c.get("body") or "").strip()
        if not body:
            continue
        out.append(f"### {c['user']['login']} · {(c.get('created_at') or c.get('submitted_at') or '')[:10]}\n\n{body}\n")
    return (f"## {title}\n\n" + "\n".join(out)) if out else ""


def find_images(text):
    """(url, context line) for every image link on GitHub hosts, in order of appearance."""
    out = []
    lines = text.split("\n")
    for k, line in enumerate(lines):
        for m in re.finditer(r'!\[[^\]]*\]\((https?://[^)\s]+)\)|<img[^>]*?\bsrc="([^"]+)"', line):
            url = m.group(1) or m.group(2)
            if not any(h in url for h in IMG_HOSTS):
                continue
            ctx = re.sub(r'!\[[^\]]*\]\([^)]*\)|<img[^>]*>', "", line).strip()
            if not ctx:
                ctx = next((lines[j].strip() for j in range(k - 1, -1, -1) if lines[j].strip()
                            and not re.search(r"!\[|<img", lines[j])), "")
            out.append((url, ctx[:200]))
    return out


def frontmatter(path):
    t = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    fm = {}
    for line in (m.group(1).split("\n") if m else []):
        k, _, v = line.partition(":")
        v = re.sub(r"\s+#.*$", "", v).strip()
        fm[k.strip()] = [int(x) for x in re.findall(r"\d+", v)] if k.strip() in ("pr", "issue") else v
    return fm


def followup_item(fu, n):
    lines = fu.read_text(encoding="utf-8").split("\n")
    start = next((i for i, l in enumerate(lines) if re.match(rf"^### {n}\.", l)), None)
    if start is None:
        raise Problems(f"no item {n} in {fu}")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^(### |## )", lines[i])), len(lines))
    return "\n".join(lines[start:end]).strip().rstrip("-").strip()


def parse_task_arg(arg):
    a = arg.strip()
    m = re.fullmatch(r"(?i)(?:follow-?ups?|fu|item)[\s#-]*(\d+)", a)
    if m:
        return "followup", int(m.group(1))
    m = re.search(r"/(issues|pull)/(\d+)", a)
    if m:
        return ("issue" if m.group(1) == "issues" else "pr"), int(m.group(2))
    m = re.fullmatch(r"(?i)(?:(issue|pr|pull request)\s*)?#?(\d+)", a)
    if m:
        kind = (m.group(1) or "").lower()
        return ("pr" if kind in ("pr", "pull request") else "number"), int(m.group(2))
    raise Problems(f"can't read {arg!r} as an issue, PR or follow-up — pass the task in words with --text")


def cmd_collect(a):
    main_root, sap, docs = roots()
    me_script = Path(__file__).resolve()
    E = ext()
    ctx = {"mode": "A", "issue": [], "pr": []}
    parts, image_sources, ask, notes = [], [], [], []

    if a.text:
        text = sys.stdin.read().strip()
        if not text:
            raise Problems("--text: pass the task on stdin (<<'TASK' … TASK)")
        kind, n = "text", None
        label = a.label or "task"
    elif not a.arg:
        raise Problems("give the task: an issue/PR number or link, `follow-up <n>`, or --text")
    else:
        kind, n = parse_task_arg(" ".join(a.arg))
        label = None
    if kind == "number":
        r = E.api(f"repos/{REPO}/issues/{n}")
        if r["status"] != 200:
            raise Problems(f"#{n}: GitHub answered HTTP {r['status']} {r.get('err', '')}")
        kind = "pr" if r["json"].get("pull_request") else "issue"

    if kind == "text":
        ctx.update(kind="text", title="")
        parts.append(f"# Task\n\n{text}\n")
    elif kind == "followup":
        label = f"fu-{n}"
        item = followup_item(docs / "FOLLOW-UPS.md", n)
        ctx.update(kind="followup", number=n, title=re.sub(r"^### \d+\.\s*", "", item.split("\n")[0]))
        parts.append(f"# Task: follow-up item {n} from DOCS/FOLLOW-UPS.md\n\n"
                     f"Treat it as the task's spec and refer to it by its number.\n\n{item}\n")
        notes.append(f"Report: remind the user to set follow-up {n} to `done` (with the PR link) once the PR is merged.")
    elif kind == "issue":
        label = str(n)
        r = E.api(f"repos/{REPO}/issues/{n}")
        if r["status"] != 200:
            raise Problems(f"issue #{n}: GitHub answered HTTP {r['status']} {r.get('err', '')}")
        iss = r["json"]
        comments = E.pages(f"repos/{REPO}/issues/{n}/comments")
        ctx.update(kind="issue", number=n, title=iss["title"], issue=[n])
        body = (iss.get("body") or "").strip()
        parts.append(f"# Issue #{n}: {iss['title']}\n\nState: {iss['state']} · {iss['html_url']}\n\n"
                     f"## Body\n\n{body or '(empty)'}\n")
        image_sources += [("issue body", body)] + [(f"comment by {c['user']['login']}", c.get("body") or "") for c in comments]
        if comments:
            parts.append(md_comments(comments))
        ep = E.api(f"repos/{REPO}/issues/{n}/parent")
        if ep["status"] == 200 and ep["json"]:
            e = ep["json"]
            ctx["epic"] = e["number"]
            parts.append(f"## Parent epic #{e['number']}: {e['title']} — context only\n\n"
                         f"The plan covers issue #{n} only; the epic tells you where it fits.\n\n"
                         f"{(e.get('body') or '').strip()}\n")
        elif ep["status"] not in (404, 410):
            notes.append(f"epic lookup failed (HTTP {ep['status']}) — planned without the epic")
    elif kind == "pr":
        label = f"pr-{n}"
        r = E.api(f"repos/{REPO}/pulls/{n}")
        if r["status"] != 200:
            raise Problems(f"PR #{n}: GitHub answered HTTP {r['status']} {r.get('err', '')}")
        pr = r["json"]
        author, head = pr["user"]["login"], pr["head"]["sha"]
        closing = E.closing(n)
        if closing is None:
            closing = sorted({int(x) for x in re.findall(
                r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+(?:" + re.escape(REPO) + r")?#(\d+)",
                pr.get("body") or "")})
            notes.append("closing issues read from the PR body (no gh)")
        if a.mine or a.not_mine:
            mine = bool(a.mine)
        else:
            me = E.user()
            if me is None:
                print(f"PR #{n} is by {author}. Can't tell who you are (no gh). "
                      "Ask the user whether it's their PR, then re-run with --mine or --not-mine.")
                return 3
            mine = me.lower() == author.lower()
        ctx.update(kind="pr", number=n, title=pr["title"], pr=[n], issue=closing, head=head, author=author,
                   mode="B" if mine else "A")
        f = E.git("fetch", "origin", f"+pull/{n}/head:refs/remotes/origin/pr/{n}")
        got = E.git("rev-parse", f"refs/remotes/origin/pr/{n}")
        if f["rc"]:
            notes.append(f"git fetch of the PR head failed: {f['err']}")
        if got["out"] != head:
            notes.append(f"origin/pr/{n} is {got['out'][:8] or 'missing'}, the PR head is {head[:8]} — the planner must not trust the ref")
        ctx["head_short"] = head[:8]
        body = (pr.get("body") or "").strip()
        parts.append(f"# PR #{n}: {pr['title']}\n\nAuthor: {author} · State: {pr['state']}"
                     f"{' (draft)' if pr.get('draft') else ''} · {pr['html_url']}\n"
                     f"Code: `origin/pr/{n}` (head `{head[:8]}`) — read it with `git show origin/pr/{n}:<path>` "
                     f"and `git diff origin/main...origin/pr/{n}`, not from the working tree.\n\n"
                     f"## Description\n\n{body or '(empty)'}\n")
        image_sources.append(("PR description", body))
        for c in closing:
            ir = E.api(f"repos/{REPO}/issues/{c}")
            if ir["status"] == 200:
                parts.append(f"## Closes issue #{c}: {ir['json']['title']}\n\n{(ir['json'].get('body') or '').strip()}\n")
                image_sources.append((f"issue #{c}", ir["json"].get("body") or ""))
        conv = E.pages(f"repos/{REPO}/issues/{n}/comments")
        reviews = E.pages(f"repos/{REPO}/pulls/{n}/reviews")
        inline = E.pages(f"repos/{REPO}/pulls/{n}/comments")
        image_sources += [(f"comment by {c['user']['login']}", c.get("body") or "") for c in conv]
        gh_md = [md_comments(conv, "Conversation"), md_comments(reviews, "Reviews")]
        if inline:
            rows = ["## Inline review threads\n"]
            order = {c["id"]: k for k, c in enumerate(inline)}
            inline = sorted(inline, key=lambda c: (order.get(c.get("in_reply_to_id") or c["id"], 0), c["created_at"]))
            for c in inline:
                outdated = c.get("line") is None
                ln = c.get("line") or c.get("original_line")
                rows.append(f"### `{c['path']}:{ln}` · {c['user']['login']} · {c['created_at'][:10]}"
                            f"{' · outdated (the code under it has changed)' if outdated else ''}"
                            f"{' · reply' if c.get('in_reply_to_id') else ''}\n\n{c['html_url']}\n\n{(c.get('body') or '').strip()}\n")
            gh_md.append("\n".join(rows))
        gh_text = "\n".join(x for x in gh_md if x).strip()
        if not mine:
            if gh_text:
                parts.append(gh_text + "\n")
        else:
            run_reviews = []
            kb = sorted((docs / "aurora-dashboard-kb" / "prs").glob(f"{n}-*.md"))
            for p in kb:
                run_reviews.append({"source": "review-and-comment-pr report", "path": str(p),
                                    "date": str(frontmatter(p).get("date", "")),
                                    "size": f"{len(p.read_text(encoding='utf-8').splitlines())} lines"})
            tr = docs / "pr-reviews" / f"pr-{n}-review.md"
            if tr.is_file():
                run_reviews.append({"source": "triple-review report", "path": str(tr),
                                    "date": str(frontmatter(tr).get("date", "")),
                                    "size": f"{len(tr.read_text(encoding='utf-8').splitlines())} lines"})
            if gh_text:
                threads = sum(1 for c in inline if not c.get("in_reply_to_id"))
                run_reviews.append({"source": "GitHub comments", "path": "github.md",
                                    "date": max([c.get("created_at") or c.get("submitted_at") or "" for c in conv + reviews + inline])[:10],
                                    "size": f"{len([c for c in conv if (c.get('body') or '').strip()])} comments, "
                                            f"{len([r for r in reviews if (r.get('body') or '').strip()])} reviews with text, "
                                            f"{threads} inline threads ({sum(1 for c in inline if c.get('line') is None and not c.get('in_reply_to_id'))} outdated)"})
            ctx["reviews"] = run_reviews
            if run_reviews:
                ask.append("Which reviews to plan from (multi-select; the user may name another file): " +
                           "; ".join(f"{i}. {r['source']} ({r['date']}, {r['size']})" for i, r in enumerate(run_reviews, 1)))
            else:
                ask.append("No review found for this PR (no KB report, no triple-review, no GitHub comments) — ask the user for one, or stop.")
            plans = docs / "plans"
            orig = [p for p in sorted(plans.glob("*.md")) if p.name != "README.md" and not re.search(r"-pr-\d+-fixes\.md$", p.name)
                    and n in (frontmatter(p).get("pr") or [])]
            how = "pr"
            if not orig and closing:
                orig = [p for p in sorted(plans.glob("*.md")) if p.name != "README.md"
                        and not re.search(r"-pr-\d+-fixes\.md$", p.name)
                        and set(closing) & set(frontmatter(p).get("issue") or [])]
                how = "issue"
            ctx["original_plan_candidates"] = [p.name for p in orig]
            if len(orig) == 1:
                ctx["original_plan"] = orig[0].name
                notes.append(f"original plan: {orig[0].name} (found by `{how}:`)")
            else:
                ask.append("Original plan — " + ("several match: " + ", ".join(p.name for p in orig) if orig else "none found")
                           + ". Ask the user which (or none); pass it to write as --original-plan <file|none>.")
            fx = sorted(plans.glob(f"*-pr-{n}-fixes.md"))
            if fx:
                ctx["fixes_file"] = str(fx[0])
                notes.append(f"earlier rounds: {fx[0]} — give the planner this path")
            ctx["pr_title"] = pr["title"]
            ctx["gh_review"] = gh_text

    run = main_root / ".claude" / "runs" / "create-plan" / re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-")
    if run.exists():
        for f in run.rglob("*"):
            if f.is_file():
                f.unlink()
    (run / "images").mkdir(parents=True, exist_ok=True)
    ctx["run"] = str(run)
    if ctx.get("gh_review"):
        (run / "github.md").write_text(f"# PR #{n} — GitHub review comments\n\n" + ctx.pop("gh_review") + "\n", encoding="utf-8")
        for r in ctx.get("reviews", []):
            if r["path"] == "github.md":
                r["path"] = str(run / "github.md")
    ctx.pop("gh_review", None)

    imgs, failed, failed_ctx = [], [], []
    for src, text in image_sources:
        for url, where in find_images(text):
            dest = run / "images" / f"{len(imgs) + 1}.png"
            ok, v = E.download(url, dest)
            if ok:
                imgs.append((dest, src, where))
            else:
                failed.append(f"{url} (HTTP {v['status']} {v['type']})")
                failed_ctx.append((url, src, where))
    if imgs or failed:
        parts.append("## Images\n\nScreenshots show the state when the text was written — the code may have moved on; "
                     "check them against the code.\n\n" +
                     "\n".join(f"- `{p}` — {src}" + (f": \"{w}\"" if w else "") for p, src, w in imgs) +
                     ("\n" if imgs and failed else "") +
                     "\n".join(f"- not downloaded: {u} — {src}" + (f": \"{w}\"" if w else "") for u, src, w in failed_ctx) + "\n")
    (run / "task.md").write_text("\n".join(x for x in parts if x).rstrip() + "\n", encoding="utf-8")

    f = E.git("fetch", "origin", "main")
    ctx["fetch_ok"] = f["rc"] == 0
    head = git("rev-parse", "--short", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    behind = git("rev-list", "--count", "HEAD..origin/main", check=False) or "0"
    ctx["behind"] = int(behind) if behind.isdigit() else 0
    if ctx["mode"] == "A" and ctx["behind"]:
        log = git("log", "--oneline", "HEAD..origin/main", "--", "packages/", "apps/", check=False)
        ask.append(f"The working copy ({branch} @ {head}) is {ctx['behind']} commit(s) behind origin/main"
                   + (f"; in packages/ and apps/:\n" + "\n".join("    " + l for l in log.splitlines()) if log else
                      " (none of them in packages/ or apps/)")
                   + "\n  Ask: plan on the current code (write records the lag in Base), or stop so they can update first.")
    kb_readme = docs / "aurora-dashboard-kb" / "README.md"
    pin = re.search(r"Pinned to commit `([0-9a-f]{7,40})`", kb_readme.read_text(encoding="utf-8")) if kb_readme.is_file() else None
    if pin:
        lag = git("rev-list", "--count", f"{pin.group(1)}..origin/main", "--", "packages/", "apps/", check=False)
        ctx["kb_pin"], ctx["kb_lag"] = pin.group(1), int(lag) if lag.isdigit() else None
    (run / "context.json").write_text(json.dumps(ctx, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    what = {"text": "a task in words", "followup": f"follow-up item {n}",
            "issue": f"issue #{n}", "pr": f"PR #{n}"}[ctx["kind"]]
    out = [f"Mode: {ctx['mode']} — {what}" + (f": {ctx['title']}" if ctx.get("title") else "")
           + (f" (by {ctx['author']}, {'yours' if ctx['mode'] == 'B' else 'not yours'})" if ctx["kind"] == "pr" else ""),
           f"Run folder: {run}",
           f"Paths: MAIN_ROOT={main_root} SAP_DIR={sap} DOCS_DIR={docs}",
           f"Task file: {run / 'task.md'} — give the planner this path; don't paste or read it",
           ]
    if ctx.get("epic"):
        out.append(f"Epic: #{ctx['epic']} (in task.md as context)")
    if ctx["issue"] or ctx["pr"]:
        out.append(f"Links for write: issue {ctx['issue'] or '—'}, pr {ctx['pr'] or '—'}")
    out.append(f"Images: {len(imgs)} downloaded into {run / 'images'}" + (f"; failed: {', '.join(failed)}" if failed else "")
               if imgs or failed else "Images: none")
    out.append("git fetch origin main: " + ("ok" if ctx["fetch_ok"] else f"FAILED ({f['err']}) — using the local origin/main; say so in the report"))
    out.append(f"Code: {branch} @ {head}, {ctx['behind']} commit(s) behind origin/main" + (" (mode B plans on the PR head)" if ctx["mode"] == "B" else ""))
    if pin:
        out.append(f"KB: pinned {ctx['kb_pin']}, {ctx['kb_lag']} commit(s) behind origin/main in packages/ and apps/")
    for x in notes:
        out.append(f"Note: {x}")
    out.append("Planner saves its plan with (put this into its launch prompt):")
    out.append(f"  python3 {me_script} save --run {run} <<'PLAN'\n  <the plan>\n  PLAN")
    out.append("Ask the user:" + ("".join(f"\n- {q}" for q in ask) if ask else " nothing"))
    print("\n".join(out))
    return 0


# ---------- save ----------

def cmd_save(a):
    run = Path(a.run)
    if not run.is_dir():
        raise Problems(f"run folder {run} doesn't exist — use the path from your launch prompt")
    text = sys.stdin.read().strip("\n")
    if not text.strip():
        raise Problems("empty input — pass the plan in a heredoc: <<'PLAN' … PLAN")
    errors, info = analyse(text)
    if errors:
        print(f"NOT saved — {len(errors)} problem(s). Fix them and run the same command again:")
        for e in errors:
            print(f"- {e}")
        return 1
    (run / "plan.md").write_text(text + "\n", encoding="utf-8")
    print(f"saved {run / 'plan.md'} · {summary(info)}")
    return 0


# ---------- write ----------

def base_line():
    branch, sha = git("rev-parse", "--abbrev-ref", "HEAD"), git("rev-parse", "--short", "HEAD")
    s = f"`{branch}` @ `{sha}`"
    if git("status", "--porcelain"):
        s += " + uncommitted changes"
    behind = git("rev-list", "--count", "HEAD..origin/main", check=False)
    if behind.isdigit() and int(behind):
        s += f" · {behind} commit{'s' if int(behind) > 1 else ''} behind origin/main"
    return s


def nums(v):
    return "[" + ", ".join(str(n) for n in v) + "]"


def risks_cell(info, top):
    sev = ", ".join(f"{info['severity'][s]} {s}" for s in SEVERITIES if info["severity"][s]) or "none"
    return f"{sev}: {top}" if top else sev


def index_row(readme, link, row_cells, keep_date=True):
    """Insert a row (newest first) or replace the row that links to `link`. Returns 'added'/'updated'."""
    if not readme.exists():
        readme.write_text(INDEX_HEADER, encoding="utf-8")
    lines = readme.read_text(encoding="utf-8").split("\n")
    row = "| " + " | ".join(row_cells) + " |"
    for i, l in enumerate(lines):
        if f"](./{link})" in l:
            if keep_date:
                old = [c.strip() for c in re.split(r"(?<!\\)\|", l.strip()[1:-1])]
                row = "| " + " | ".join([old[0]] + row_cells[1:]) + " |"
            lines[i] = row
            readme.write_text("\n".join(lines), encoding="utf-8")
            return "updated"
    for i, l in enumerate(lines):
        if re.fullmatch(r"\s*\|(\s*:?-{3,}:?\s*\|)+\s*", l):
            lines.insert(i + 1, row)
            readme.write_text("\n".join(lines), encoding="utf-8")
            return "added"
    raise Problems(f"{readme}: no table separator line found — add the row by hand")


def add_pr(path, n):
    t = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    if not m:
        return f"{path.name}: no frontmatter — `pr: [{n}]` not added"
    fm = m.group(1)
    pm = re.search(r"^pr:\s*(.*)$", fm, re.M)
    if pm:
        have = [int(x) for x in re.findall(r"\d+", pm.group(1))]
        if n in have:
            return f"{path.name}: already has pr {n}"
        fm2 = fm[:pm.start()] + "pr: " + nums(have + [n]) + fm[pm.end():]
    else:
        sm = re.search(r"^status:.*$", fm, re.M)
        at = sm.end() if sm else len(fm)
        fm2 = fm[:at] + f"\npr: [{n}]" + fm[at:]
    path.write_text("---\n" + fm2 + "\n---\n" + t[m.end():], encoding="utf-8")
    return f"{path.name}: added pr {n}"


def run_related(docs):
    script = docs / "tools" / "update-related.py"
    if not script.is_file():
        return "update-related.py not found — skipped"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip().splitlines()
    return ("ok" if r.returncode == 0 else f"exit {r.returncode}") + (f" — {out[-1]}" if out else "")


def cmd_write(a):
    main_root, sap, docs = roots(a.docs)
    run = Path(a.run)
    src = run / "plan.md"
    if not src.is_file():
        raise Problems(f"{src} doesn't exist — the planner hasn't saved its plan (plan.py save)")
    plan = src.read_text(encoding="utf-8").strip("\n")
    errors, info = analyse(plan)
    if errors:
        raise Problems("plan.md doesn't pass the checks (send these to the planner):\n" + "\n".join(f"- {e}" for e in errors))
    cpath = run / "context.json"
    cx = json.loads(cpath.read_text(encoding="utf-8")) if cpath.is_file() else {}
    if a.fixes is None and cx.get("mode") == "B":
        a.fixes = cx["number"]
    if not a.issue and not a.no_links:
        a.issue = cx.get("issue") or []
    if not a.pr and not a.no_links and a.fixes is None:
        a.pr = cx.get("pr") or []
    a.pr_title = a.pr_title or cx.get("pr_title")
    a.original_plan = a.original_plan or cx.get("original_plan")
    task = " ".join(a.task.split())
    problems = []
    if len(task) > TASK_MAX:
        problems.append(f"--task is {len(task)} characters — one sentence, about 150 at most")
    if a.reviewed and not re.fullmatch(r"\d+/\d+", a.reviewed):
        problems.append("--reviewed takes N/M (findings/fixed)")
    if problems:
        raise Problems("\n".join(problems))
    analysis = info["steps"] == 0
    status_fm = "analysis" if analysis else "not-implemented"
    status_txt = "analysis" if analysis else "not implemented"
    reviewed = ""
    if a.reviewed:
        n, m = a.reviewed.split("/")
        reviewed = f"**Reviewed:** {n} findings, {m} fixed\n"
    plans = docs / "plans"
    plans.mkdir(exist_ok=True)
    d = today()
    report = []

    if a.fixes is None:
        if not a.title or not a.slug:
            raise Problems("mode A needs --title and --slug")
        slug = re.sub(r"[^a-z0-9]+", "-", a.slug.lower()).strip("-")
        name = f"{d}-{slug}.md"
        path = plans / name
        if path.exists() and not a.overwrite:
            raise Problems(f"{path} exists — pick another --slug, or --overwrite to replace it (and its index row)")
        fm = ["---", "type: plan", f"date: {d}", f"status: {status_fm}"]
        if a.pr:
            fm.append(f"pr: {nums(a.pr)}")
        if a.issue:
            fm.append(f"issue: {nums(a.issue)}")
        fm.append("---")
        head = (f"# Plan: {a.title}\n\n**Date:** {d} · **Status:** {status_txt}\n"
                f"**Base:** {base_line()}\n{reviewed}\n")
        path.write_text("\n".join(fm) + "\n" + head + plan + "\n", encoding="utf-8")
        report.append(f"Plan: {path}")
        tcell = f"{task}; {info['steps']} steps" if not analysis else f"{task}; analysis, no code changes"
        how = index_row(plans / "README.md", name,
                        [d, cell(tcell), cell(risks_cell(info, a.top_risk)), status_txt,
                         f"[{name}](./{name})"], keep_date=False)
        report.append(f"Index: row {how}")
        written = {"file": str(path), "mode": "A"}
    else:
        pr = a.fixes
        try:
            head_sha = git("rev-parse", "--short", f"refs/remotes/origin/pr/{pr}")
        except Problems:
            raise Problems(f"origin/pr/{pr} not found — fetch it first (step 1, mode B)")
        found = sorted(plans.glob(f"*-pr-{pr}-fixes.md"))
        if len(found) > 1:
            raise Problems(f"several fixes files for PR #{pr}: {', '.join(f.name for f in found)} — ask the user")
        body = shift_headings(plan, 1)
        src_txt = cell(a.sources or "review")
        if not found:
            if not a.pr_title:
                raise Problems("round 1 needs --pr-title")
            k = 1
            name = f"{d}-pr-{pr}-fixes.md"
            path = plans / name
            orig = a.original_plan or "none"
            if not a.original_plan and cx.get("original_plan_candidates") is not None and len(cx["original_plan_candidates"]) != 1:
                raise Problems("round 1 needs --original-plan <file|none> (collect found " +
                               (", ".join(cx["original_plan_candidates"]) or "none") + ")")
            orig_line = "none" if orig == "none" else f"[{Path(orig).name}](./{Path(orig).name})"
            fm = ["---", "type: plan", f"date: {d}", f"status: {status_fm}", f"pr: [{pr}]"]
            if a.issue:
                fm.append(f"issue: {nums(a.issue)}")
            fm.append("---")
            text = ("\n".join(fm) + f"\n# Fixes: PR #{pr} — {a.pr_title}\n\n"
                    f"**Original plan:** {orig_line}\n**Status:** round 1 {status_txt}\n\n")
            text += (f"## Round 1 — {d} · {src_txt}\n\n**Base:** `origin/pr/{pr}` @ `{head_sha}`\n"
                     f"{reviewed}\n{body}\n")
            path.write_text(text, encoding="utf-8")
        else:
            path = found[0]
            name = path.name
            t = path.read_text(encoding="utf-8")
            lines = t.split("\n")
            hs = headings(lines)
            k = 1 + sum(1 for _, lvl, ti in hs if lvl == 2 and re.match(r"Round \d+\b", ti))
            block = (f"## Round {k} — {d} · {src_txt}\n\n**Base:** `origin/pr/{pr}` @ `{head_sha}`\n"
                     f"{reviewed}\n{body}\n")
            at = next((i for i, l in enumerate(lines) if l.startswith(RELATED_MARKER)), len(lines))
            pre = "\n".join(lines[:at]).rstrip("\n")
            post = "\n".join(lines[at:])
            t = pre + "\n\n" + block + ("\n" + post if post.strip() else "")
            t = re.sub(r"^status:.*$", f"status: {status_fm}", t, count=1, flags=re.M)
            t, n = re.subn(r"^\*\*Status:\*\*.*$", f"**Status:** round {k} {status_txt}", t, count=1, flags=re.M)
            if not n:
                report.append("warning: no `**Status:**` line in the fixes file — not updated")
            path.write_text(t, encoding="utf-8")
        report.append(f"Fixes file: {path} (round {k})")
        tcell = f"PR #{pr} fixes, round {k}: {task}; " + (f"{info['steps']} steps" if not analysis else "analysis, no code changes")
        how = index_row(plans / "README.md", name,
                        [d, cell(tcell), cell(risks_cell(info, a.top_risk)), status_txt,
                         f"[{name}](./{name})"], keep_date=True)
        report.append(f"Index: row {how}")
        if a.original_plan and a.original_plan != "none":
            op = Path(a.original_plan)
            op = op if op.is_absolute() else plans / op.name
            report.append("Original plan: " + (add_pr(op, pr) if op.is_file() else f"{op} not found"))
        written = {"file": str(path), "mode": "B", "round": k}

    (run / "written.json").write_text(json.dumps(written), encoding="utf-8")
    report.append(f"Related: {run_related(docs)}")
    report.append(f"Summary: {summary(info)}")
    if info["high"]:
        report.append("High risks:\n" + "\n".join(f"- {h}" for h in info["high"]))
    if info["open_questions"]:
        report.append("Open questions:\n" + info["open_questions"])
    if info["followups"]:
        report.append("Follow-up candidates (decide each, then run `plan.py followups`):\n" +
                      "\n".join(f"{i}. {t}" for i, t in enumerate(info["followups"], 1)))
        fu = docs / "FOLLOW-UPS.md"
        if fu.is_file():
            ft = fu.read_text(encoding="utf-8").split("\n")
            report.append("FOLLOW-UPS.md sections: " + "; ".join(l[3:] for l in ft if re.match(r"^## [A-Z]\. ", l)))
            s = next((i for i, l in enumerate(ft) if l.startswith("## Summary")), None)
            if s is not None:
                e = next((i for i in range(s + 1, len(ft)) if ft[i].startswith("## ")), len(ft))
                rows = [l for l in ft[s + 1:e] if re.match(r"^\|\s*\d+\s*\|", l)]
                report.append("FOLLOW-UPS.md summary (check for duplicates):\n" + "\n".join(rows))
    print("\n".join(report))
    return 0


# ---------- followups ----------

def parse_pairs(values, what):
    out = {}
    for v in values or []:
        m = re.fullmatch(r"(\d+)=(.+)", v.strip())
        if not m:
            raise Problems(f"--{what} {v!r}: use <candidate>=<value>")
        out[int(m.group(1))] = m.group(2).strip()
    return out


def cmd_followups(a):
    main_root, sap, docs = roots(a.docs)
    run = Path(a.run)
    w = run / "written.json"
    if not w.is_file():
        raise Problems("run `plan.py write` first")
    path = Path(json.loads(w.read_text())["file"])
    t = path.read_text(encoding="utf-8")
    lines = t.split("\n")
    hs = headings(lines)
    secs = [(i, lvl) for i, lvl, ti in hs if ti == "Proposed follow-ups"]
    if not secs:
        raise Problems(f"{path.name} has no `Proposed follow-ups` section — nothing to file (already done?)")
    start, level = secs[-1]
    end = section_span(lines, hs, start, level)
    cands, cerr = candidates(lines, hs, start, level, end)
    if cerr:
        raise Problems("\n".join(cerr))
    files, refs, topics = parse_pairs(a.file, "file"), parse_pairs(a.ref, "ref"), parse_pairs(a.topic, "topic")
    skips = {int(x) for x in (a.skip or [])}
    problems = []
    for i in range(1, len(cands) + 1):
        n = (i in files) + (i in refs) + (i in skips)
        if n != 1:
            problems.append(f"candidate {i} ({cands[i - 1]['title']}): give exactly one of --file / --ref / --skip")
    extra = (set(files) | set(refs) | skips) - set(range(1, len(cands) + 1))
    if extra:
        problems.append(f"no such candidate(s): {sorted(extra)} (there are {len(cands)})")
    fu = docs / "FOLLOW-UPS.md"
    if not fu.is_file():
        problems.append(f"{fu} not found")
    if problems:
        raise Problems("\n".join(problems))

    reg = fu.read_text(encoding="utf-8").split("\n")
    s0 = next(i for i, l in enumerate(reg) if l.startswith("## Summary"))
    summ = {}
    for i in range(s0 + 1, len(reg)):
        if reg[i].startswith("## "):
            break
        m = re.match(r"^\|\s*(\d+)\s*\|(.*)$", reg[i])
        if m:
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", reg[i].strip()[1:-1])]
            summ[int(m.group(1))] = (i, cells)
    for i, n in refs.items():
        if not n.isdigit() or int(n) not in summ:
            problems.append(f"--ref {i}={n}: no item {n} in the summary table")
    for i, sec in files.items():
        if not (re.fullmatch(r"[A-Z]", sec) or sec.startswith("new:")):
            problems.append(f"--file {i}={sec}: use a section letter (A, B, …) or new:<area name>")
        elif re.fullmatch(r"[A-Z]", sec) and not any(re.match(rf"^## {sec}\. ", l) for l in reg):
            problems.append(f"--file {i}={sec}: no section `## {sec}.` in FOLLOW-UPS.md")
    if problems:
        raise Problems("\n".join(problems))

    plan_name = path.name
    next_n = max(int(x) for x in re.findall(r"^### (\d+)\.", "\n".join(reg), re.M)) + 1
    links, filed = [], []
    for i, c in enumerate(cands, 1):
        if i in skips:
            links.append(f"- Not filed: {c['title']}")
        elif i in refs:
            n = int(refs[i])
            links.append(f"- [FOLLOW-UPS.md → item {n}](../FOLLOW-UPS.md) — {summ[n][1][1]} "
                         f"(already existed; covers \"{c['title']}\")")
        else:
            n = next_n
            next_n += 1
            item = [f"### {n}. {c['title']}", ""]
            for f in FU_FIELDS:
                v = c["fields"][f]
                item.append(f"**{FU_REGISTRY_LABEL[f]}:** {v[0]}".rstrip())
                item += v[1:]
                item.append("")
            item += [f"**Source:** plan [{plan_name}](./plans/{plan_name})", "", "**Status:** open."]
            filed.append((n, c["title"], files[i], topics.get(i, c["title"]), item))
            links.append(f"- [FOLLOW-UPS.md → item {n}](../FOLLOW-UPS.md) — {c['title']}")

    out_report = []
    for n, title, sec, topic, item in filed:
        upd = next(i for i, l in enumerate(reg) if re.match(r"^Updated:", l)) if any(re.match(r"^Updated:", l) for l in reg) else len(reg)
        if sec.startswith("new:"):
            area = sec[4:].strip()
            letters = [re.match(r"^## ([A-Z])\. ", l).group(1) for l in reg if re.match(r"^## [A-Z]\. ", l)]
            letter = chr(ord(max(letters)) + 1) if letters else "A"
            k = upd - 1
            while k > 0 and not reg[k].strip():
                k -= 1
            block = ([] if reg[k] == "---" else ["", "---"]) + ["", f"## {letter}. {area}", ""] + item + ["", "---"]
            reg[k + 1:k + 1] = block
            sec_name = f"{letter}. {area}"
        else:
            hi = next(i for i, l in enumerate(reg) if re.match(rf"^## {sec}\. ", l))
            nxt = next((i for i in range(hi + 1, len(reg)) if reg[i].startswith("## ") or re.match(r"^Updated:", reg[i])), len(reg))
            members = [int(m.group(1)) for l in reg[hi:nxt] for m in [re.match(r"^### (\d+)\.", l)] if m]
            areas = [summ[m][1][2] for m in members if m in summ]
            area = areas[-1] if areas else reg[hi][3:].split(". ", 1)[-1]
            k = nxt - 1
            while k > hi and not reg[k].strip():
                k -= 1
            block = ([] if reg[k] == "---" else ["", "---"]) + [""] + item + ["", "---"]
            reg[k + 1:k + 1] = block
            sec_name = reg[hi][3:]
        # summary row: after the last row of the same area, else at the end of the table
        s_end = next(j for j in range(s0 + 1, len(reg)) if reg[j].startswith("## "))
        rows = [(i, [c.strip() for c in re.split(r"(?<!\\)\|", reg[i].strip()[1:-1])])
                for i in range(s0 + 1, s_end) if re.match(r"^\|\s*\d+\s*\|", reg[i])]
        same = [i for i, c in rows if len(c) > 2 and c[2] == area]
        at = (same[-1] if same else rows[-1][0]) + 1
        reg.insert(at, f"| {n} | {cell(topic)} | {area} | open |")
        out_report.append(f"Filed: item {n} — {title} (section {sec_name}, area {area})")
    reg = [re.sub(r"^Updated: .*$", f"Updated: {today()}", l) for l in reg]
    if filed:
        fu.write_text("\n".join(reg), encoding="utf-8")

    head = "#" * level + " Follow-ups"
    new_sec = [head, ""] + links + [""]
    lines[start:end] = new_sec
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    for i in refs:
        out_report.append(f"Referenced: item {refs[i]} for \"{cands[i - 1]['title']}\"")
    for i in sorted(skips):
        out_report.append(f"Not filed: {cands[i - 1]['title']}")
    out_report.append(f"Plan: `{head.strip('# ')}` section written in {path.name}")
    print("\n".join(out_report))
    return 0


def main():
    p = argparse.ArgumentParser(prog="plan.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("collect")
    s.add_argument("arg", nargs="*", help="issue/PR number or link, or `follow-up <n>`")
    s.add_argument("--text", action="store_true", help="the task in words, on stdin")
    s.add_argument("--label", help="with --text: a short slug for the run folder")
    s.add_argument("--mine", action="store_true", help="the PR is the user's (mode B) — when gh can't tell")
    s.add_argument("--not-mine", action="store_true", help="the PR is someone else's (mode A)")
    s = sub.add_parser("save")
    s.add_argument("--run", required=True)
    s = sub.add_parser("write")
    s.add_argument("--run", required=True)
    s.add_argument("--task", required=True, help="index Task: one sentence, what and why (step count is added)")
    s.add_argument("--top-risk", default="", help="index Risks: the most important risk in a few words")
    s.add_argument("--title", help="mode A: short plan title")
    s.add_argument("--slug", help="mode A: kebab-case file slug")
    s.add_argument("--issue", type=int, nargs="*", default=[], help="default: from collect (context.json)")
    s.add_argument("--pr", type=int, nargs="*", default=[], help="default: from collect (context.json)")
    s.add_argument("--no-links", action="store_true", help="don't take issue/pr numbers from collect")
    s.add_argument("--reviewed", help="N/M: plan-review findings / fixed; omit if the review didn't run")
    s.add_argument("--overwrite", action="store_true")
    s.add_argument("--fixes", type=int, help="mode B: the user's PR number (default: from collect)")
    s.add_argument("--pr-title", help="mode B, round 1: the PR title")
    s.add_argument("--original-plan", help="mode B: original plan file name in DOCS/plans, or none")
    s.add_argument("--sources", help="mode B: review sources, e.g. 'review-and-comment-pr report, Copilot'")
    s.add_argument("--docs", help=argparse.SUPPRESS)
    s = sub.add_parser("followups")
    s.add_argument("--run", required=True)
    s.add_argument("--file", action="append", help="<candidate>=<section letter> or <candidate>=new:<area name>")
    s.add_argument("--topic", action="append", help="<candidate>=<short topic for the summary table>")
    s.add_argument("--ref", action="append", help="<candidate>=<existing item number>")
    s.add_argument("--skip", action="append", help="<candidate> not to file")
    s.add_argument("--docs", help=argparse.SUPPRESS)
    a = p.parse_args()
    try:
        return {"collect": cmd_collect, "save": cmd_save, "write": cmd_write, "followups": cmd_followups}[a.cmd](a)
    except Problems as e:
        print(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
