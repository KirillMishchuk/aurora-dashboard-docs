#!/usr/bin/env python3
"""Collect everything review-and-comment-pr needs about a PR (Steps 1-3).

Usage:
  collect.py [<pr>] [--issue N | --no-issue] [--rerun] [--run-dir DIR] [--no-input]

<pr> is a number, a URL, or nothing (the PR for the current branch).
Run from inside the aurora-dashboard repo. Read-only: fetches commits by
SHA (never a branch or ref), never checks anything out.

Writes <run-dir>/context.json plus pr.diff, pr-body.md, issue-<N>.md,
discussion.json, copilot-instructions.md (and delta.diff on an update),
then prints a short summary. Default run dir:
<main repo>/.claude/runs/review-and-comment-pr/<number>-<sha8>/

Exit codes: 0 = done, act on "Mode:"; 1 = could not collect (message
printed); 2 = usage error; 3 = needs an answer (question and re-run flag
printed; asked in the terminal instead when stdin is a TTY).
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
SKILL = "review-and-comment-pr"
MAX_ISSUE_CANDIDATES = 10
SLUG_STOPWORDS = {"add", "and", "the", "a", "an", "for", "to", "of", "in", "on", "with"}
SLUG_MAX_WORDS = 8
BOT_HINTS = ("[bot]", "copilot", "github-actions", "cobaltcore-bot", "dependabot", "renovate")
# this skill's published comments: the report (also the older header without "by [...]") and Update blocks
OWN_REPORT = re.compile(r"^\s*## (?:PR Review Report\b|Update — \d{4}-\d{2}-\d{2}, head `[0-9a-f]{7,40}`)")
# Generated files: listed in context.json, left out of pr.diff (the compiled
# Lingui catalogs alone can be >80% of a diff). Catalog sources (.po) stay in
# the diff — UI strings are reviewed there.
GENERATED = (r"(^|/)locales/[^/]+/messages\.(ts|js)$", r"(^|/)routeTree\.gen\.ts$")
DIFF_EXCLUDES = (":(exclude,glob)**/locales/*/messages.ts", ":(exclude,glob)**/locales/*/messages.js",
                 ":(exclude,glob)**/routeTree.gen.ts")
PR_FIELDS = ("number,title,body,author,url,state,isDraft,baseRefName,headRefName,"
             "baseRefOid,headRefOid,mergedAt,closedAt,additions,deletions,"
             "changedFiles,files,createdAt,mergeable")


class CollectError(Exception):
    """Collection can't continue; message goes to the user (exit 1)."""


class NeedsInput(Exception):
    """A decision only the user can make (exit 3)."""

    def __init__(self, question, flags):
        super().__init__(question)
        self.question, self.flags = question, flags


# ---------------------------------------------------------------- shell

def run(cmd, cwd, ok=(0,), timeout=180):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise CollectError(f"'{cmd[0]}' not found — install it and re-run")
    except subprocess.TimeoutExpired:
        raise CollectError(f"timed out: {' '.join(cmd)}")
    if p.returncode not in ok:
        err = (p.stderr or p.stdout).strip()
        if cmd[0] == "gh" and re.search(r"auth login|not logged|authentication", err, re.I):
            raise CollectError("gh is not signed in to GitHub — run `gh auth login`")
        raise CollectError(f"{' '.join(cmd)} failed ({p.returncode}): {err[:400]}")
    return p


def gh_json(args, cwd, ok=(0,)):
    out = run(["gh"] + args, cwd, ok).stdout
    return json.loads(out) if out.strip() else None


def git(args, cwd, ok=(0,)):
    return run(["git"] + args, cwd, ok)


# ---------------------------------------------------------------- pure helpers

def slugify(title):
    t = re.sub(r"^\s*\w+(\([^)]*\))?!?:\s*", "", title)       # type(scope):
    t = re.sub(r"\([^)]*\)", " ", t)                           # (…), (#1236)
    t = t.lower().replace("'", "").replace("’", "")
    words = [w for w in re.split(r"[^a-z0-9]+", t) if w and w not in SLUG_STOPWORDS]
    return "-".join(words[:SLUG_MAX_WORDS]) or "pr"


def matches_any(path, patterns):
    return any(re.search(p, path) for p in patterns)


def is_bot(login):
    login = (login or "").lower()
    return any(h in login for h in BOT_HINTS)


def is_release(pr):
    matched = []
    if pr["headRefName"] == "changeset-release/main":
        matched.append("head branch changeset-release/main")
    login = (pr.get("author") or {}).get("login", "")
    if login in ("cobaltcore-bot", "app/cobaltcore-bot"):
        matched.append(f"author {login}")
    if "changesets/action" in (pr.get("body") or ""):
        matched.append("body mentions changesets/action")
    return matched


def finder_f_files(paths):
    return [p for p in paths
            if (p.startswith("packages/aurora/src/server/") or p.startswith("packages/signal-openstack/"))
            and not p.endswith(".test.ts")]


def touches_published_src(paths):
    return any(re.match(r"^packages/[^/]+/src/", p) for p in paths)


def issue_candidates(body, nwo):
    """Issue numbers the PR body links, in order, with how they were linked."""
    text = re.sub(r"<!--.*?-->", " ", body or "", flags=re.S)   # template comments
    text = re.sub(r"```.*?```", " ", text, flags=re.S)           # code blocks
    owner_repo = re.escape(nwo)
    found = []

    def add(n, how):
        if n not in [f["number"] for f in found]:
            found.append({"number": n, "how": how})

    kw = r"(?i)\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?|part of)\s*:?\s+(?:" + owner_repo + r")?#(\d+)\b"
    for m in re.finditer(kw, text):
        add(int(m.group(2)), m.group(1).lower())
    for m in re.finditer(r"github\.com/" + owner_repo + r"/issues/(\d+)", text):
        add(int(m.group(1)), "url")
    for m in re.finditer(r"(?<![\w/-])" + owner_repo + r"#(\d+)\b", text):
        add(int(m.group(1)), "repo-ref")
    for m in re.finditer(r"(?<![\w/&#])#(\d+)\b", text):
        add(int(m.group(1)), "bare")
    return found


def parse_report(text):
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    fm_status = None
    if fm:
        m = re.search(r"^status:\s*(\S+)", fm.group(1), re.M)
        fm_status = m.group(1) if m else None
    m = re.search(r"\*\*Status:\*\*\s*([^·\n]+)", text)
    status_line = m.group(1).strip() if m else None
    status_word = None
    if status_line:
        w = re.search(r"\b(draft|open|merged|closed)\b", status_line)
        status_word = w.group(1) if w else None
    footers = [l for l in text.splitlines() if l.startswith("_Analyzed")]
    footer = footers[-1] if footers else None
    old_head = None
    if footer:
        def clean(ms):
            return [m.group(1) for m in ms
                    if not re.match(r"[`\s]*(not analyzed|\(?previous version)", footer[m.end():m.end() + 30])]
        upd = clean(re.finditer(r"updated for\s+`?([0-9a-f]{7,40})`?", footer))
        com = clean(re.finditer(r"\bcommit\s+`?([0-9a-f]{7,40})`?", footer))
        old_head = (upd or com or [None])[-1]
    return {"status_frontmatter": fm_status, "status_line": status_line,
            "status_word": status_word, "footer": footer, "old_head": old_head}


def status_now(pr):
    created = pr["createdAt"][:10]
    if pr["state"] == "MERGED":
        d = (pr.get("mergedAt") or "")[:10]
        return {"frontmatter": "merged", "line": f"merged {d}", "word": "merged",
                "index_date": f"{created} → merged {d}"}
    if pr["state"] == "CLOSED":
        d = (pr.get("closedAt") or "")[:10]
        return {"frontmatter": "closed", "line": f"closed {d}", "word": "closed",
                "index_date": f"{created} → closed {d}"}
    word = "draft" if pr["isDraft"] else "open"
    return {"frontmatter": "open", "line": word, "word": word, "index_date": f"{created} ({word})"}


def footer_with(footer, suffix):
    if not footer:
        return None
    i = footer.rfind(" · skill:")
    if i < 0:
        i = len(footer.rstrip("_ "))
    return footer[:i] + suffix + footer[i:]


def decide_mode(pr, now, rep, head_short, today):
    """-> (mode, status_update or None, reason). rep is parse_report() or None."""
    closed = pr["state"] in ("MERGED", "CLOSED")
    if rep is None:
        return ("none", None, f"{pr['state'].lower()} PR without a report — nothing to document") if closed \
            else ("full", None, "no report yet")
    same_status = rep["status_frontmatter"] == now["frontmatter"] and (closed or rep["status_word"] == now["word"])
    upd = None
    if not same_status:
        upd = {"frontmatter_status": now["frontmatter"], "status_line": now["line"],
               "index_date": now["index_date"], "footer_old": None, "footer_new": None}
    if closed:
        if same_status:
            return "none", None, f"report already says {now['frontmatter']}"
        suffix = f" · status updated {today}: {now['frontmatter']}"
        if rep["old_head"] and not pr["headRefOid"].startswith(rep["old_head"]):
            suffix += f" · last head `{head_short}` not analyzed"
        upd["footer_old"], upd["footer_new"] = rep["footer"], footer_with(rep["footer"], suffix)
        return "status", upd, f"PR {now['frontmatter']} since the report"
    if not rep["old_head"]:
        raise CollectError("the existing report's footer names no analyzed commit — "
                           "can't tell whether the head moved; check the report by hand")
    if pr["headRefOid"].startswith(rep["old_head"]):
        if same_status:
            return "current", None, "report is current (same head, same status)"
        return "status", upd, f"{rep['status_word']} → {now['word']}, same head"
    return "update", upd, f"head moved {rep['old_head']} → {head_short}"


# ---------------------------------------------------------------- collection steps

def find_paths():
    cwd = os.getcwd()
    try:
        top = git(["rev-parse", "--show-toplevel"], cwd).stdout.strip()
        common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd).stdout.strip()
    except CollectError:
        raise CollectError("not inside a git repository — run from the aurora-dashboard repo")
    main_root = Path(common).parent
    docs = main_root.parent / "DOCS"
    prs = docs / "aurora-dashboard-kb" / "prs"
    if not prs.is_dir():
        raise CollectError(f"{prs} not found — the DOCS folder must sit next to the repo")
    return Path(top), main_root, docs, prs


def find_report(prs, number):
    hits = sorted(p for p in prs.iterdir() if re.match(rf"^{number}-.*\.md$", p.name))
    if len(hits) > 1:
        raise CollectError(f"several reports for #{number}: " + ", ".join(h.name for h in hits)
                           + " — merge or remove the extra one first")
    return hits[0] if hits else None


def fetch_commit(oid, number, cwd):
    """Make <oid> available locally by SHA; no refs created. -> how it was fetched."""
    if git(["cat-file", "-e", f"{oid}^{{commit}}"], cwd, ok=(0, 1, 128)).returncode == 0:
        return "already local"
    if git(["fetch", "-q", "origin", oid], cwd, ok=(0, 1, 128)).returncode == 0:
        return "fetched by SHA"
    if number is not None:
        git(["fetch", "-q", "origin", f"pull/{number}/head"], cwd)
        got = git(["rev-parse", "FETCH_HEAD"], cwd).stdout.strip()
        if got != oid:
            raise CollectError(f"pull/{number}/head is {got[:8]}, expected {oid[:8]} — the PR moved; re-run")
        return "fetched via pull/<n>/head"
    raise CollectError(f"can't fetch {oid[:8]}")


def changed_files(base, head, cwd):
    """Complete changed-file list (gh caps `files` at 100) from the merge base, like `gh pr diff`."""
    files = []
    for line in git(["diff", "--numstat", "--no-renames", f"{base}...{head}"], cwd).stdout.splitlines():
        a, d, path = line.split("\t", 2)
        files.append({"path": path, "additions": int(a) if a.isdigit() else 0,
                      "deletions": int(d) if d.isdigit() else 0, "generated": matches_any(path, GENERATED)})
    return files


def _blob(rev, path, cwd):
    """File text at rev, "" if it doesn't exist there, None if it isn't text."""
    p = subprocess.run(["git", "cat-file", "-p", f"{rev}:{path}"], cwd=cwd, capture_output=True)
    if p.returncode != 0:
        return ""
    try:
        return p.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _unified(path, a, b):
    import difflib
    if a == b:
        return ""
    lines = list(difflib.unified_diff(a.splitlines(keepends=True), b.splitlines(keepends=True),
                                      f"a/{path}" if a else "/dev/null", f"b/{path}" if b else "/dev/null"))
    body = "".join(l if l.endswith("\n") else l + "\n\\ No newline at end of file\n" for l in lines)
    return f"diff --git a/{path} b/{path}\n" + body


def _hunks(diff_text):
    """A one-file unified diff -> (header lines, [hunk lines])."""
    head, hunks = [], []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("@@"):
            hunks.append([line])
        elif hunks:
            hunks[-1].append(line)
        else:
            head.append(line)
    return head, hunks


def _change(hunk):
    return (tuple(l[1:] for l in hunk[1:] if l.startswith("-")), tuple(l[1:] for l in hunk[1:] if l.startswith("+")))


def _drop_base_hunks(file_diff, base_diff):
    """Leave out of a file's delta every hunk that is exactly a change the base made between the merge-bases
    (same lines removed and added) — the fallback when merge-file can't bring the old head up to the new base."""
    _, base_hunks = _hunks(base_diff)
    base_changes = {_change(h) for h in base_hunks}
    head, hunks = _hunks(file_diff)
    keep = [h for h in hunks if _change(h) not in base_changes]
    if len(keep) == len(hunks):
        return file_diff, 0
    return ("".join(head) + "".join("".join(h) for h in keep) if keep else ""), len(hunks) - len(keep)


def delta_diff(old, head, files, cwd, base=None, note=None):
    """The PR's own change between two heads, limited to the PR's files (generated files left out).

    A merge of the base branch in between also changes the PR's own files (locale catalogs, a shared file
    main touched). Those lines aren't the author's work: for a file the base changed between the two
    merge-bases, the old head's version is first brought up to the new base (a 3-way `git merge-file`), and
    the delta is taken against that — so only what the author changed is left. Where that merge conflicts,
    the plain `old..head` diff of the file loses the hunks that are exactly a base change. `note` (a dict)
    gets the files of each kind."""
    paths = [f["path"] for f in files if not f["generated"]]
    if not paths:
        return ""
    plain = lambda ps: git(["diff", f"{old}..{head}", "--"] + [":(literal)" + p for p in ps], cwd).stdout  # noqa: E731
    if not base:
        return plain(paths)
    old_mb = git(["merge-base", old, base], cwd, ok=(0, 1)).stdout.strip()
    new_mb = git(["merge-base", head, base], cwd, ok=(0, 1)).stdout.strip()
    if not old_mb or not new_mb or old_mb == new_mb:
        return plain(paths)
    moved = set(git(["diff", "--name-only", "--no-renames", f"{old_mb}..{new_mb}", "--"]
                    + [":(literal)" + p for p in paths], cwd).stdout.split("\n")) - {""}
    import tempfile
    out, kept, cleaned = [], [], []
    with tempfile.TemporaryDirectory(prefix="delta-") as t:
        for p in paths:
            if p not in moved:
                kept.append(p)
                continue
            ours, b_old, b_new, theirs = (_blob(r, p, cwd) for r in (old, old_mb, new_mb, head))
            if None in (ours, b_old, b_new, theirs):
                kept.append(p)
                continue
            fs = []
            for name, text in (("ours", ours), ("base", b_old), ("theirs", b_new)):
                fp = Path(t) / name
                fp.write_text(text, encoding="utf-8")
                fs.append(str(fp))
            m = subprocess.run(["git", "merge-file", "-p", *fs], cwd=cwd, capture_output=True)
            if m.returncode != 0:  # conflicts (>0) or an error (<0): keep the plain diff for this file
                kept.append(p)
                continue
            cleaned.append(p)
            out.append((p, _unified(p, m.stdout.decode("utf-8"), theirs)))
    hunked = []
    for p in [p for p in kept if p in moved]:  # merge-file couldn't: drop the hunks that are base changes
        d, n = _drop_base_hunks(plain([p]), git(["diff", f"{old_mb}..{new_mb}", "--", ":(literal)" + p], cwd).stdout)
        if n:
            kept.remove(p)
            hunked.append(p)
            out.append((p, d))
    if note is not None:
        note.update({"base_changes_removed": sorted(cleaned + hunked),
                     "plain": [p for p in kept if p in moved]})
    text = {p: d for p, d in out}
    plain_text = plain(kept) if kept else ""
    # plain diff for the untouched files, then the cleaned ones in path order
    return plain_text + "".join(text[p] for p in sorted(text) if text[p])


def supplied_issue_from_footer(footer):
    m = re.search(r"against (?:epic |issue )?#(\d+) supplied", footer or "")
    return int(m.group(1)) if m else None


def resolve_issue(n, nwo, cwd):
    data = gh_json(["api", "--method", "GET", f"repos/{nwo}/issues/{n}"], cwd, ok=(0, 1))
    if not data or "number" not in data:
        return None
    return {"number": n, "is_pr": "pull_request" in data, "title": data.get("title", ""),
            "state": (data.get("state") or "").upper(), "url": data.get("html_url", ""),
            "body": data.get("body") or ""}


def write_issue(run_dir, iss):
    name = f"issue-{iss['number']}.md"
    (run_dir / name).write_text(f"# #{iss['number']}: {iss['title']}\n\nState: {iss['state']} · {iss['url']}\n\n"
                                f"{iss['body']}\n", encoding="utf-8")
    return name


def collect_issue(pr, nwo, args, cwd, release):
    linked, mentioned_prs = [], []
    seen = set()
    for ref in pr.get("closingIssuesReferences") or []:
        n = ref.get("number")
        if n and n not in seen:
            seen.add(n)
            linked.append({"number": n, "how": "closing-ref"})
    for c in issue_candidates(pr.get("body"), nwo):
        if c["number"] not in seen and c["number"] != pr["number"]:
            seen.add(c["number"])
            linked.append(c)
    resolved = []
    for c in linked[:MAX_ISSUE_CANDIDATES]:
        iss = resolve_issue(c["number"], nwo, cwd)
        if iss is None:
            continue
        if iss["is_pr"]:
            mentioned_prs.append(c["number"])
        else:
            resolved.append(dict(iss, how=c["how"]))
    supplied = None
    if not resolved and not release:
        n = args["issue"]
        if n is None and not args["no_issue"]:
            n = ask("This PR links no issue. Give an issue/epic number to grade acceptance "
                    "criteria against, or say none.", ["--issue <N>", "--no-issue"], args, kind="issue")
        if n:
            supplied = resolve_issue(n, nwo, cwd)
            if supplied is None or supplied["is_pr"]:
                raise CollectError(f"#{n} is not an issue in {nwo}")
    return resolved, supplied, mentioned_prs


def ask(question, flags, args, kind):
    if sys.stdin.isatty() and not args["no_input"]:
        ans = input(f"{question}\n> ").strip().lower()
        if kind == "issue":
            if ans in ("", "none", "no", "n"):
                return None
            m = re.match(r"#?(\d+)$", ans)
            if not m:
                raise CollectError(f"not an issue number: {ans!r}")
            return int(m.group(1))
        return ans in ("y", "yes", "rerun", "да")
    raise NeedsInput(question, flags)


def collect_ci(number, cwd):
    p = run(["gh", "pr", "checks", str(number), "--json", "name,state,bucket,link,workflow"],
            cwd, ok=(0, 1, 8))
    try:
        checks = json.loads(p.stdout) if p.stdout.strip() else []
    except ValueError:
        msg = (p.stderr or p.stdout).strip()
        if "no checks" in msg.lower():
            checks = []
        else:
            return {"error": msg[:200]}
    out = {"total": len(checks), "pass": 0, "fail": 0, "pending": 0, "skipping": 0, "cancel": 0,
           "failed": [], "pending_names": []}
    for c in checks:
        b = c.get("bucket") or "pending"
        out[b] = out.get(b, 0) + 1
        if b == "fail":
            out["failed"].append({"name": c.get("name"), "link": c.get("link")})
        elif b == "pending":
            out["pending_names"].append(c.get("name"))
    return out


def collect_changeset(base, head, cwd, published):
    p = git(["diff", "--name-status", "--no-renames", f"{base}...{head}", "--", ".changeset/"], cwd)
    files, bumps = [], []
    for line in p.stdout.splitlines():
        st, path = line.split("\t", 1)
        if not path.endswith(".md") or path.endswith("README.md") or st == "D":
            continue
        files.append(path)
        text = git(["show", f"{head}:{path}"], cwd).stdout
        fm = re.match(r"^---\n(.*?)\n---", text, re.S)
        for m in re.finditer(r"^\s*['\"]?([^'\"\n:]+)['\"]?\s*:\s*(major|minor|patch)\s*$",
                             fm.group(1) if fm else "", re.M):
            bumps.append({"file": path, "package": m.group(1).strip(), "bump": m.group(2)})
    return {"files": files, "bumps": bumps, "missing": published and not files}


def collect_discussion(number, nwo, cwd):
    top = gh_json(["pr", "view", str(number), "--json", "comments,reviews"], cwd) or {}
    comments = [{"author": (c.get("author") or {}).get("login"), "created": c.get("createdAt"),
                 "url": c.get("url"), "body": c.get("body", "")} for c in top.get("comments", [])]
    reviews = [{"author": (r.get("author") or {}).get("login"), "state": r.get("state"),
                "submitted": r.get("submittedAt"), "body": r.get("body", "")} for r in top.get("reviews", [])]
    inline, inline_read = [], True
    try:
        jq = ('.[] | {id, in_reply_to_id, user: .user.login, user_type: .user.type, path, line, '
              'original_line, commit_id, created_at, url: .html_url, body}')
        out = run(["gh", "api", "--method", "GET", "--paginate",
                   f"repos/{nwo}/pulls/{number}/comments", "--jq", jq], cwd).stdout
        inline = [json.loads(l) for l in out.splitlines() if l.strip()]
    except CollectError:
        inline_read = False
    for item in comments + reviews:
        item["bot"] = is_bot(item["author"])
        item["own_report"] = bool(OWN_REPORT.match(item["body"] or ""))
        if item["own_report"]:  # don't anchor finder d on our own earlier verdicts
            item["own_kind"] = "update" if item["body"].lstrip().startswith("## Update") else "review"
            item["body"] = "(earlier review-and-comment-pr report — omitted; see the url)"
    roots, by_id = [], {}
    for c in inline:
        c["bot"] = c.get("user_type") == "Bot" or is_bot(c.get("user"))
        c["replies"] = []
        by_id[c["id"]] = c
    for c in inline:
        parent = by_id.get(c.get("in_reply_to_id"))
        (parent["replies"] if parent else roots).append(c)
    data = {"comments": comments, "reviews": [r for r in reviews if r["body"] or r["state"] != "COMMENTED"],
            "threads": roots, "inline_read": inline_read}
    summary = {"comments": len(comments), "reviews": len(data["reviews"]), "threads": len(roots),
               "bot_items": sum(i["bot"] for i in comments + data["reviews"] + roots),
               "own_reports_excluded": sum(i["own_report"] for i in comments + reviews),
               "inline_read": inline_read}
    return data, summary


# ---------------------------------------------------------------- main

def parse_args(argv):
    a = {"pr": None, "issue": None, "no_issue": False, "rerun": False, "run_dir": None, "no_input": False}
    it = iter(argv)
    for x in it:
        if x == "--issue":
            v = next(it, "")
            if not re.match(r"#?\d+$", v):
                raise ValueError("--issue needs a number")
            a["issue"] = int(v.lstrip("#"))
        elif x == "--no-issue":
            a["no_issue"] = True
        elif x == "--rerun":
            a["rerun"] = True
        elif x == "--no-input":
            a["no_input"] = True
        elif x == "--run-dir":
            a["run_dir"] = next(it, None)
            if not a["run_dir"]:
                raise ValueError("--run-dir needs a path")
        elif x in ("-h", "--help"):
            raise ValueError("")
        elif x.startswith("-") or a["pr"] is not None:
            raise ValueError(f"unexpected argument: {x}")
        else:
            a["pr"] = x
    if a["issue"] is not None and a["no_issue"]:
        raise ValueError("--issue and --no-issue exclude each other")
    return a


def main(argv):
    try:
        args = parse_args(argv)
    except ValueError as e:
        print((f"ERROR: {e}\n" if str(e) else "") + __doc__)
        return 2
    today = dt.date.today().isoformat()
    top, main_root, docs, prs_dir = find_paths()
    cwd = str(top)

    view = ["pr", "view"] + ([args["pr"]] if args["pr"] else [])
    try:
        pr = gh_json(view + ["--json", PR_FIELDS + ",closingIssuesReferences"], cwd)
    except CollectError as e:
        if "closingIssuesReferences" not in str(e):
            raise
        pr = gh_json(view + ["--json", PR_FIELDS], cwd)
    number = pr["number"]
    nwo = re.search(r"github\.com/([^/]+/[^/]+)/pull/", pr["url"]).group(1)
    head, base = pr["headRefOid"], pr["baseRefOid"]
    head_short = head[:8]
    paths = [f["path"] for f in pr["files"]]
    release = is_release(pr)
    now = status_now(pr)

    rep_path = find_report(prs_dir, number)
    rep = parse_report(rep_path.read_text(encoding="utf-8")) if rep_path else None
    mode, status_update, reason = decide_mode(pr, now, rep, head_short, today)
    if mode == "current":
        if args["rerun"] or ask(f"The report {rep_path.name} is current (head {head_short}, status "
                                f"{now['line']}). Stop, or re-run from scratch (overwrites the report)?",
                                ["--rerun", "(or stop)"], args, kind="rerun"):
            mode, reason = "rerun", "re-run of a current report, confirmed"
        else:
            mode, reason = "none", "report is current; the user chose to stop"

    run_dir = Path(args["run_dir"]) if args["run_dir"] else \
        main_root / ".claude" / "runs" / SKILL / f"{number}-{head_short}"
    report_path = rep_path or prs_dir / f"{number}-{slugify(pr['title'])}.md"

    ctx = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today": today,
        "repo": {"name_with_owner": nwo, "root": cwd},
        "docs": str(docs),
        "run_dir": str(run_dir),
        "pr": {
            "number": number, "title": pr["title"], "url": pr["url"],
            "author": (pr.get("author") or {}).get("login"), "state": pr["state"],
            "is_draft": pr["isDraft"], "created": pr["createdAt"][:10],
            "merged_at": (pr.get("mergedAt") or "")[:10] or None,
            "closed_at": (pr.get("closedAt") or "")[:10] or None,
            "base": {"ref": pr["baseRefName"], "oid": base},
            "head": {"ref": pr["headRefName"], "oid": head, "short": head_short},
            "additions": pr["additions"], "deletions": pr["deletions"],
            "changed_files": pr["changedFiles"], "mergeable": pr.get("mergeable"),
            "files": [{"path": f["path"], "additions": f["additions"], "deletions": f["deletions"]}
                      for f in pr["files"]],
            "body_file": "pr-body.md", "diff_file": "pr.diff",
        },
        "flags": {
            "base_not_main": pr["baseRefName"] != "main",
            "release": {"is_release": bool(release), "matched": release},
            "finder_f": {"needed": bool(finder_f_files(paths)), "files": finder_f_files(paths)},
            "touches_published_src": touches_published_src(paths),
        },
        "mode": mode, "mode_reason": reason,
        "report": {"path": str(report_path), "exists": rep_path is not None,
                   **({k: rep[k] for k in ("status_frontmatter", "status_line", "old_head", "footer")}
                      if rep else {"status_frontmatter": None, "status_line": None, "old_head": None, "footer": None}),
                   "old_head_reachable": None, "delta": None, "status_update": status_update},
        "status_now": {k: now[k] for k in ("frontmatter", "line", "index_date")},
        "process": [], "provenance": ["read-only"],
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    if mode in ("full", "rerun", "update"):
        for stale in ("findings.json", "report.md"):  # left by an earlier run on the same head
            if (run_dir / stale).exists():
                (run_dir / stale).unlink()
    (run_dir / "pr-body.md").write_text(pr.get("body") or "", encoding="utf-8")

    if mode in ("full", "rerun", "update"):
        reused = None
        if args["issue"] is None and not args["no_issue"] and rep:
            reused = args["issue"] = supplied_issue_from_footer(rep["footer"])
        # Ask early (before the slow part) so a needed answer costs seconds, not minutes.
        linked, supplied, mentioned_prs = collect_issue(pr, nwo, args, cwd, bool(release))
        ctx["fetch"] = {"head": fetch_commit(head, number, cwd), "base": fetch_commit(base, None, cwd)}
        pr["files"] = changed_files(base, head, cwd)
        paths = [f["path"] for f in pr["files"]]
        ctx["pr"]["files"] = pr["files"]
        ctx["flags"]["finder_f"] = {"needed": bool(finder_f_files(paths)), "files": finder_f_files(paths)}
        ctx["flags"]["touches_published_src"] = touches_published_src(paths)
        (run_dir / "pr.diff").write_text(git(["diff", f"{base}...{head}", "--", "."] + list(DIFF_EXCLUDES), cwd).stdout,
                                         encoding="utf-8")
        ctx["pr"]["generated_files_not_in_diff"] = [f["path"] for f in pr["files"] if f["generated"]]

        if mode == "update":
            old = rep["old_head"]
            full_old = git(["rev-parse", "--verify", "-q", f"{old}^{{commit}}"], cwd, ok=(0, 1, 128)).stdout.strip()
            reachable = bool(full_old) and git(["merge-base", "--is-ancestor", full_old, head], cwd,
                                               ok=(0, 1, 128)).returncode == 0
            ctx["report"]["old_head_reachable"] = reachable
            if reachable:
                ctx["report"]["delta"] = f"{full_old}..{head}"
                dnote = {}
                (run_dir / "delta.diff").write_text(delta_diff(full_old, head, pr["files"], cwd, base, dnote),
                                                    encoding="utf-8")
                ctx["report"]["delta_base_changes_removed"] = dnote.get("base_changes_removed", [])
            else:
                ctx["report"]["delta"] = "whole-pr"
            ctx["report"]["footer_new"] = footer_with(rep["footer"], f" · updated for `{head_short}` on {today}")

        ctx["issue"] = {
            "linked": [{k: i[k] for k in ("number", "how", "title", "state", "url")} | {"file": write_issue(run_dir, i)}
                       for i in linked],
            "supplied": ({k: supplied[k] for k in ("number", "title", "state", "url")}
                         | {"file": write_issue(run_dir, supplied)}) if supplied else None,
            "source": "pr-body" if linked else (("previous report" if reused else "user") if supplied else "none"),
            "mentioned_prs": mentioned_prs,
        }
        ctx["ci"] = collect_ci(number, cwd)
        ctx["changeset"] = collect_changeset(base, head, cwd, ctx["flags"]["touches_published_src"])
        disc, ctx["discussion"] = collect_discussion(number, nwo, cwd)
        ctx["discussion"]["file"] = "discussion.json"
        (run_dir / "discussion.json").write_text(json.dumps(disc, indent=1, ensure_ascii=False), encoding="utf-8")

        ci_md = git(["show", f"{head}:.github/copilot-instructions.md"], cwd, ok=(0, 128))
        if ci_md.returncode == 0:
            (run_dir / "copilot-instructions.md").write_text(ci_md.stdout, encoding="utf-8")
        claude_md = top / "CLAUDE.md"
        ctx["standards"] = {"copilot_instructions_file": "copilot-instructions.md" if ci_md.returncode == 0 else None,
                            "claude_md": str(claude_md), "claude_md_exists": claude_md.is_file()}

        if pr["isDraft"]:
            ctx["process"].append({"id": "draft", "where": "PR state", "text": "PR is still a draft"})
        if not linked and not release:
            ctx["process"].append({"id": "no-linked-issue", "where": "PR body",
                                   "text": "PR body links no issue" + (f" (graded against #{supplied['number']} supplied by the reviewer)" if supplied else "")})
        if ctx["changeset"]["missing"] and not release:
            ctx["process"].append({"id": "missing-changeset", "where": "PR files",
                                   "text": "published package code changed without a .changeset/*.md"})
        if supplied:
            ctx["provenance"].append(f"acceptance graded against #{supplied['number']} supplied by the reviewer")
        if not ctx["discussion"]["inline_read"]:
            ctx["provenance"].append("review threads not read")
        if "error" in ctx["ci"]:
            ctx["provenance"].append("CI not read")

    out = run_dir / "context.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ctx, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    print(summary(ctx))
    return 0


def summary(c):
    p, f = c["pr"], c["flags"]
    state = p["state"].lower() + (" (draft)" if p["is_draft"] else "")
    L = [f"PR #{p['number']} {p['title']} — {state} · {p['base']['ref']} ← {p['head']['ref']}",
         f"Head {p['head']['oid']} · base {p['base']['oid']}",
         f"{p['changed_files']} files +{p['additions']}/−{p['deletions']} · mergeable: {p['mergeable']}",
         f"Mode: {c['mode']} — {c['mode_reason']}",
         f"Report: {c['report']['path']}" + (" (exists)" if c["report"]["exists"] else " (new)")]
    if c["report"]["status_update"]:
        su = c["report"]["status_update"]
        L.append(f"Status update: status: {su['frontmatter_status']} · **Status:** {su['status_line']} · "
                 f"index Date: {su['index_date']}" + (" · footer suffix in context.json" if su["footer_new"] else ""))
    if c["mode"] not in ("full", "rerun", "update"):
        L.append(f"Context: {c['run_dir']}/context.json")
        return "\n".join(L)
    if c["mode"] == "update":
        rm = c["report"].get("delta_base_changes_removed") or []
        L.append(f"Delta: {c['report']['delta']}" + (f" · base-branch changes left out of {len(rm)} file(s)" if rm else "") + ("" if c["report"]["old_head_reachable"]
                                                    else " — old head unreachable (force-push?)"))
    L.append(f"Release PR: {'yes (' + '; '.join(f['release']['matched']) + ')' if f['release']['is_release'] else 'no'}"
             f" · Finder f: {'yes (' + str(len(f['finder_f']['files'])) + ' files)' if f['finder_f']['needed'] else 'no'}"
             f" · Base: {p['base']['ref']}" + (" — NOT main" if f["base_not_main"] else ""))
    if f["finder_f"]["needed"]:
        L.append("Finder f files: " + ", ".join(f["finder_f"]["files"]))
    ci = c["ci"]
    if "error" in ci:
        L.append(f"CI: not read — {ci['error']}")
    else:
        L.append(f"CI: {ci['pass']} pass, {ci['fail']} fail"
                 + (f" ({', '.join(x['name'] for x in ci['failed'])})" if ci["failed"] else "")
                 + f", {ci['pending']} pending" + ("" if ci["total"] else " — no checks reported"))
    cs = c["changeset"]
    L.append("Changeset: " + ("; ".join(f"{b['package']} {b['bump']}" for b in cs["bumps"]) or ", ".join(cs["files"])
                              if cs["files"] else ("MISSING — published code changed" if cs["missing"] else "none (not needed)")))
    i = c["issue"]
    if i["linked"]:
        L.append("Issue: " + ", ".join(f"#{x['number']} ({x['how']}, {x['state'].lower()})" for x in i["linked"]))
    else:
        L.append("Issue: PR links none" + (f"; #{i['supplied']['number']} supplied by the user"
                                           + (" (reused from the previous report)" if i["source"] == "previous report" else "")
                                           if i["supplied"] else ""))
    d = c["discussion"]
    L.append(f"Discussion: {d['comments']} comments, {d['reviews']} reviews, {d['threads']} inline threads "
             f"({d['bot_items']} by bots)" + (f" · {d['own_reports_excluded']} own earlier report(s)" if d["own_reports_excluded"] else "")
             + ("" if d["inline_read"] else " · inline threads NOT read"))
    if p.get("generated_files_not_in_diff"):
        L.append(f"Generated files left out of pr.diff: {len(p['generated_files_not_in_diff'])}")
    L.append("Process: " + (", ".join(x["id"] for x in c["process"]) or "none"))
    L.append("Provenance: " + " · ".join(c["provenance"]))
    L.append(f"Context: {c['run_dir']}/context.json")
    return "\n".join(L)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except NeedsInput as e:
        print(f"NEEDS INPUT: {e.question}\nRe-run with: " + "   or   ".join(e.flags))
        sys.exit(3)
    except CollectError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
