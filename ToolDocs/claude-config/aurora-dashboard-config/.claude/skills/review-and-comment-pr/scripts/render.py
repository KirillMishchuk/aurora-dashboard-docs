#!/usr/bin/env python3
"""Render a review-and-comment-pr report from the run folder (Steps 5.3-7).

Usage:
  render.py --run <run-dir> [--check | --dry-run]

Reads <run-dir>/context.json (from collect.py) and, for modes full/rerun,
<run-dir>/findings.json (written by the orchestrator; format in
references/findings-format.md). Validates the findings, lays them out into
Required Changes / Improvements, numbers them, derives the verdict, builds
the report from the fixed template, checks its Markdown, writes it to DOCS,
upserts the PR's row in the reports index and runs DOCS/tools/update-related.py.
Mode status: applies context.json report.status_update to the existing
report and its index row (no findings.json needed). Mode update: renders an
"## Update — <today>, head `<sha>`" block (Verdict, Fixed since last analysis,
the delta's findings numbered after the report's earlier ones, What changed),
inserts it before the report's footer — replacing an earlier block for the
same head — and updates the footer, the status and the index Date cell.

--check    validate findings.json only; write nothing
--dry-run  write <run-dir>/report.md only; don't touch DOCS

Exit codes: 0 = written; 1 = validation or Markdown errors (listed; nothing
written to DOCS); 2 = usage error.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the skill's scripts
sys.path.insert(0, str(Path(__file__).resolve().parent))
import quotes  # noqa: E402  (same folder)

SKILL = "review-and-comment-pr"
SKILL_URL = ("https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/"
             "aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md")
SEVERITIES = ["Critical", "Major", "Moderate", "Low", "Trivial"]
MARKER = {"Critical": "🔴", "Major": "🟠", "Moderate": "🟡", "Low": "🟢", "Trivial": "⚪"}
REQUIRED_SEVERITIES = {"Critical", "Major", "Moderate"}
# a Required Change blocks the merge only when it breaks behaviour or safety; conventions (UI/UX, Performance,
# Code Quality, …) and anything with a precedent tag are the team's call
BLOCKING_CATEGORIES = {"Bug", "Security"}
CATEGORIES = ["Bug", "Security", "Accessibility", "UI/UX", "Code Quality", "Performance",
              "Docs", "Test coverage"]
SCORES = {50, 75, 100}
SCOPE_MAX_CHARS = 100
LABELS = {"PR state", "PR body", "PR files", "CI"}
CONFIDENCE = {"High", "Medium", "Low"}
AFFECTED_MAX_WORDS = 45
ISSUE_MAX_CHARS = 120
NBSP4 = "&nbsp;&nbsp;&nbsp;&nbsp;"
REF = re.compile(r"\[\[ref:([a-z0-9-]+)\]\]")
HARD_NUMBER = re.compile(r"\b(?:CR|P|I)\d{1,2}\b")


def strip_code(text):
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1", " ", text)
    return re.sub(r"(`+).+?\1", " ", text)


def text_fields(fd):
    """(where, text) for every free-text field the report shows."""
    yield "summary", fd.get("summary") or ""
    for k, v in (fd.get("earlier") or {}).items() if isinstance(fd.get("earlier"), dict) else []:
        if isinstance(v, dict):
            yield f"earlier.{k}.note", v.get("note") or ""
    for sec in ("findings", "process"):
        for i, f in enumerate(fd.get(sec) or []):
            for k in ("issue", "title", "explanation", "fix"):
                yield f"{sec}[{i}].{k}", f.get(k) or ""
    for pid, v in (fd.get("process_overrides") or {}).items():
        for k in ("issue", "title", "explanation", "fix"):
            yield f"process_overrides.{pid}.{k}", v.get(k) or ""
    for k, v in (fd.get("overview") or {}).items():
        yield f"overview.{k}", v or ""
    for k, v in (fd.get("qa") or {}).items():
        for i, x in enumerate(v or []):
            yield f"qa.{k}[{i}]", x or ""


def resolve_refs(text, nums):
    return link_comments(REF.sub(lambda m: nums[m.group(1)], text))


COMMENT_URLS = {}   # comment id -> (author, url) from discussion.json; filled by load_comment_urls(ctx)
# a bare comment id in text: "comment 6293554974", "issuecomment-6293554974", "r4360389025"
BARE_COMMENT = re.compile(r"\b(?:([Cc]omment) (\d{8,})|issuecomment-(\d{8,})|r(\d{8,}))\b")
# left alone: code spans, Markdown links, bare URLs
NOT_PLAIN = re.compile(r"(`[^`\n]*`|\[[^\]\n]*\]\([^)\s]*\)|https?://\S+)")


def load_comment_urls(ctx):
    """Every comment and inline thread in discussion.json by id; own reports included (a link to them is fine)."""
    COMMENT_URLS.clear()
    f = Path(ctx.get("run_dir") or ".") / ((ctx.get("discussion") or {}).get("file") or "discussion.json")
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return COMMENT_URLS

    def walk(c):
        if c.get("url"):
            COMMENT_URLS[str(c.get("id"))] = (c.get("user") or "?", c["url"])
        for r in c.get("replies") or []:
            walk(r)
    for c in d.get("threads") or []:
        walk(c)
    for c in d.get("comments") or []:
        m = re.search(r"issuecomment-(\d+)", c.get("url") or "")
        if m:
            COMMENT_URLS[m.group(1)] = (c.get("author") or "?", c["url"])
    return COMMENT_URLS


def link_comments(text):
    """A comment id the text names bare becomes a link to that comment (ids not in discussion.json stay as they are)."""
    if not COMMENT_URLS or not text:
        return text

    def sub(m):
        i = m.group(2) or m.group(3) or m.group(4)
        if i not in COMMENT_URLS:
            return m.group(0)
        label = f"r{i}" if m.group(4) else (m.group(1) or "comment")
        return f"[{label}]({COMMENT_URLS[i][1]})"
    return "".join(p if NOT_PLAIN.fullmatch(p) else BARE_COMMENT.sub(sub, p) for p in NOT_PLAIN.split(text))


class Invalid(Exception):
    pass


# ---------------------------------------------------------------- helpers

def git(args, cwd, ok=(0,)):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    return p if p.returncode in ok else None


def width(s):
    w = 0
    for ch in s:
        if unicodedata.combining(ch) or ch in "‍️︎":
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def cell(s):
    return s.replace("|", "\\|")


def table(header, rows):
    cols = list(zip(*([header] + rows)))
    widths = [max(3, max(width(c) for c in col)) for col in cols]
    def line(cells):
        return "| " + " | ".join(c + " " * (widths[i] - width(c)) for i, c in enumerate(cells)) + " |"
    return "\n".join([line(header), "| " + " | ".join("-" * w for w in widths) + " |"]
                     + [line(r) for r in rows])


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def is_path_location(loc):
    return loc not in LABELS


def fmt_location(loc):
    return f"`{loc}`" if is_path_location(loc) else loc


# ---------------------------------------------------------------- validation

class Checker:
    def __init__(self, ctx):
        self.ctx, self.errors, self.warnings = ctx, [], []
        self.root = ctx["repo"]["root"]
        self.head = ctx["pr"]["head"]["oid"]
        self._lines = {}

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def text(self, obj, key, where, required=True, single_line=False, max_chars=None):
        v = obj.get(key)
        if v is None or (isinstance(v, str) and not v.strip()):
            if required:
                self.err(f"{where}.{key}", "missing or empty")
            return None
        if not isinstance(v, str):
            self.err(f"{where}.{key}", f"must be a string, got {type(v).__name__}")
            return None
        if single_line and "\n" in v.strip():
            self.err(f"{where}.{key}", "must be one line")
        if max_chars and len(v) > max_chars:
            self.warnings.append(f"{where}.{key}: {len(v)} chars, aim for ≤ {max_chars}")
        if re.search(r"(?<![\w/])(\.\.\.|…)/", v):
            self.err(f"{where}.{key}", "abbreviated path (…/ or .../) — write the full repo-relative path")
        return v

    def file_lines(self, path):
        if path not in self._lines:
            p = git(["cat-file", "-p", f"{self.head}:{path}"], self.root)
            if p is None:
                t = git(["cat-file", "-t", f"{self.head}:{path}"], self.root)
                self._lines[path] = "tree" if t and t.stdout.strip() == "tree" else None
            else:
                self._lines[path] = p.stdout.count("\n") + (0 if p.stdout.endswith("\n") or not p.stdout else 1)
        return self._lines[path]

    def location(self, loc, where):
        if not is_path_location(loc):
            return
        m = re.match(r"^(?P<path>[^:`]+?)(?::(?P<a>\d+)(?:-(?P<b>\d+))?)?$", loc)
        if not m or loc.startswith(("/", "./", "../")):
            self.err(where, f"{loc!r} is neither `path:line` (repo-relative) nor one of {sorted(LABELS)}")
            return
        path, a, b = m.group("path"), m.group("a"), m.group("b")
        n = self.file_lines(path)
        if n is None:
            self.err(where, f"{path} does not exist at head {self.head[:8]}")
        elif n == "tree":
            if a:
                self.err(where, f"{path} is a directory, it has no line {a}")
        elif a and (int(a) < 1 or int(a) > n or (b and not int(a) <= int(b) <= n)):
            self.err(where, f"{loc}: {path} has {n} lines at head {self.head[:8]}")

    def item(self, f, where, scored):
        if scored:
            if f.get("score") not in SCORES:
                s = f.get("score")
                self.err(f"{where}.score", f"{s!r} — must be 50, 75 or 100"
                         + (" (below 50: leave the issue out of findings.json)" if isinstance(s, int) and s < 50 else ""))
            if f.get("severity") not in SEVERITIES:
                self.err(f"{where}.severity", f"{f.get('severity')!r} not one of {SEVERITIES}")
            if f.get("category") not in CATEGORIES:
                self.err(f"{where}.category", f"{f.get('category')!r} not one of {CATEGORIES}"
                         + (" (Process items go to `process`)" if f.get("category") == "Process" else ""))
        self.text(f, "issue", where, single_line=True, max_chars=ISSUE_MAX_CHARS)
        self.text(f, "title", where, single_line=True)
        loc = self.text(f, "location", where, single_line=True)
        if loc and " | " not in loc:  # an unresolved "path | text" was already reported by quotes.py
            self.location(loc, f"{where}.location")
        self.text(f, "explanation", where)
        self.text(f, "fix", where)


EARLIER_STATUS = ("fixed", "partly", "open", "dropped")   # dropped: a merge-conflict finding — no longer reviewed


def number_key(n):
    """CR1 < CR2 < … < P1 < … < I1 < … — the report's own order."""
    m = re.match(r"^(CR|P|I)(\d+)$", n)
    return (("CR", "P", "I").index(m.group(1)), int(m.group(2))) if m else (9, 0)


def check_earlier(c, earlier, numbers):
    """Every earlier finding gets a status and a one-line note — nothing left out, nothing invented."""
    if not isinstance(earlier, dict):
        c.err("earlier", "must be an object: {\"CR1\": {\"status\": …, \"note\": …}, …}")
        return
    missing = sorted(numbers - set(earlier), key=number_key)
    if missing:
        c.err("earlier", f"missing {', '.join(missing)} — give every earlier finding a status (template in compose.md)")
    for k in sorted(earlier, key=number_key):
        v, w = earlier[k], f"earlier.{k}"
        if k not in numbers:
            c.err(w, "not a finding of the earlier report")
            continue
        if not isinstance(v, dict) or set(v) != {"status", "note"}:
            c.err(w, "must be {\"status\": \"fixed\" | \"partly\" | \"open\", \"note\": \"one line\"}")
            continue
        if v["status"] not in EARLIER_STATUS:
            c.err(f"{w}.status", f"{v['status']!r} not one of {list(EARLIER_STATUS)}")
        note = c.text(v, "note", w, single_line=True)
        if note and re.search(r"\[\[(code|at):", note):
            c.err(f"{w}.note", "one line of text — no [[code:…]] / [[at:…]] placeholders here")


def validate(ctx, fd):
    c = Checker(ctx)
    q_errors, q_warnings = quotes.resolve_findings(ctx, fd)   # placeholders -> code/line numbers; hand-typed code checked
    c.errors += q_errors
    c.warnings += q_warnings
    c.errors += field_markdown_problems(fd)
    release = ctx["flags"]["release"]["is_release"]
    update = ctx["mode"] == "update"
    if fd.get("schema_version") != 1:
        c.err("schema_version", "must be 1")
    known = {"schema_version", "summary", "confidence", "findings", "process", "process_overrides",
             "overview", "qa", "provenance_extra", "index_affected", "dismissed", "scope", "earlier"}
    for k in fd:
        if k not in known:
            c.err(k, f"unknown key (allowed: {', '.join(sorted(known))})")
    if fd.get("scope") is not None:
        sc = c.text(fd, "scope", "", single_line=True)
        if sc and len(sc) > SCOPE_MAX_CHARS:
            c.err("scope", f"{len(sc)} characters — one short line, about {SCOPE_MAX_CHARS} at most")
    if update:
        if fd.get("earlier") is None:
            c.err("earlier", "missing — a status for every earlier finding (the template in compose.md)")
        else:
            check_earlier(c, fd["earlier"], earlier_numbers(ctx))
    else:
        c.text(fd, "summary", "")
        if fd.get("earlier") is not None:
            c.err("earlier", "exists only on an Update")
    if fd.get("confidence") not in CONFIDENCE:
        c.err("confidence", f"{fd.get('confidence')!r} not one of {sorted(CONFIDENCE)}")
    prec_repo = quotes.Repo(ctx)
    for i, f in enumerate(fd.get("findings") or []):
        c.item(f, f"findings[{i}]", scored=True)
        if isinstance(f, dict):
            quotes.check_precedent(prec_repo, f.get("precedent"), f"findings[{i}].precedent", c.errors)
    for i, f in enumerate(fd.get("process") or []):
        c.item(f, f"process[{i}]", scored=False)
    ids = {p["id"] for p in ctx.get("process", [])}
    for k, v in (fd.get("process_overrides") or {}).items():
        if k not in ids:
            c.err(f"process_overrides.{k}", f"no such Process item in context.json (have: {sorted(ids) or 'none'})")
        for key in v:
            if key not in ("title", "issue", "location", "explanation", "fix"):
                c.err(f"process_overrides.{k}.{key}", "unknown key")
        if "location" in v:
            c.location(v["location"], f"process_overrides.{k}.location")
    ov = fd.get("overview") or {}
    c.text(ov, "what", "overview")
    c.text(ov, "how", "overview", required=not (release or update))
    c.text(ov, "affects", "overview", required=not (release or update))
    qa = fd.get("qa") or {}
    for key, req in (("core_path", not (release or update)), ("edge_cases", not update)):
        v = qa.get(key)
        if not v and req:
            c.err(f"qa.{key}", "missing or empty")
        elif v and not (isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)):
            c.err(f"qa.{key}", "must be a list of non-empty strings")
    pe = fd.get("provenance_extra", [])
    if not isinstance(pe, list) or not all(isinstance(x, str) for x in pe):
        c.err("provenance_extra", "must be a list of strings")
    aff = c.text(fd, "index_affected", "", required=not update, single_line=True)
    if aff and len(aff.split()) > AFFECTED_MAX_WORDS:
        c.err("index_affected", f"{len(aff.split())} words — keep it to about 40")
    if aff and "Verdict" in aff:
        c.err("index_affected", "leave the verdict out — render.py appends it")
    # an Update block shows no Process items from context.json, so [[ref:]] can't point at them there
    ids = [] if update else [p["id"] for p in ctx.get("process", [])]
    earlier = earlier_numbers(ctx) if update else set()  # an Update may name the report's earlier findings
    for sec in ("findings", "process"):
        for i, f in enumerate(fd.get(sec) or []):
            if "id" in f:
                if not re.match(r"^[a-z0-9-]+$", str(f["id"])):
                    c.err(f"{sec}[{i}].id", "use lowercase letters, digits and dashes")
                elif f["id"] in ids:
                    c.err(f"{sec}[{i}].id", f"duplicate id {f['id']!r}")
                ids.append(f["id"])
    for where, t in text_fields(fd):
        for m in REF.finditer(t):
            if m.group(1) not in ids:
                c.err(where, f"[[ref:{m.group(1)}]] — no finding or Process item has that id"
                      + (" in this Update block; name an earlier finding by its number (e.g. CR2)" if update else ""))
        # the describer's overview never numbers findings — an epic's "P1" there is not one
        hard = [] if where.startswith("overview.") else HARD_NUMBER.findall(strip_code(t))
        hard = [h for h in hard if h not in earlier]
        if hard:
            c.err(where, f"hard-coded finding number {hard[0]} — numbers are assigned by render.py; "
                         "give the finding an `id` and write [[ref:<id>]]. If it isn't a finding number "
                         f"(e.g. an epic's priority {hard[0]}), put it in backticks: `{hard[0]}`")
    ids = [f.get("id") if isinstance(f, dict) else None for f in fd.get("findings") or []]

    def by_id(m):  # findings[3] -> findings.c12 — the key you edit in texts.json
        i = int(m.group(1))
        return f"findings.{ids[i]}" if i < len(ids) and ids[i] else m.group(0)
    c.errors = [re.sub(r"findings\[(\d+)\]", by_id, e.lstrip(".")) for e in c.errors]
    c.warnings = [re.sub(r"findings\[(\d+)\]", by_id, w) for w in c.warnings]
    return c


# ---------------------------------------------------------------- layout

def default_process(item, ctx):
    supplied = (ctx.get("issue") or {}).get("supplied")
    pkgs = sorted({m.group(1) for f in ctx["pr"]["files"]
                   for m in [re.match(r"^packages/([^/]+)/src/", f["path"])] if m})
    base = {
        "draft": {"title": "PR is still a draft", "issue": "PR is still a draft", "location": "PR state",
                  "explanation": "The PR is marked as a draft, so the author doesn't consider it ready to merge yet.",
                  "fix": "Mark it ready for review once the Required Changes are addressed."},
        "no-linked-issue": {
            "title": "No linked issue", "issue": "The PR description links no issue", "location": "PR body",
            "explanation": (f"The description links no issue. Acceptance was graded against #{supplied['number']}, "
                            "which the reviewer supplied; the PR itself should say what it closes."
                            if supplied else "The description links no issue, so the acceptance criteria can't be verified."),
            "fix": "Add `Closes #<n>` (or `Part of #<n>`) to the description."},
        "missing-changeset": {
            "title": "No changeset", "issue": "Published package code changed without a `.changeset/*.md`",
            "location": "PR files",
            "explanation": ("The PR changes published code under " + ", ".join(f"`packages/{p}/src`" for p in pkgs)
                            + " but adds no changeset, so the change gets no version bump or changelog entry."),
            "fix": "Run `pnpm changeset`, pick the bump type and commit the generated `.changeset/*.md`."},
    }.get(item["id"], {"title": item.get("text", item["id"]), "issue": item.get("text", item["id"]),
                       "location": item.get("where", "PR state"), "explanation": item.get("text", ""), "fix": "—"})
    return base


def blocks(f):
    return f.get("category") in BLOCKING_CATEGORIES and not f.get("precedent")


def layout(ctx, fd, start=None, ctx_process=True):
    """start: {'CR': n, 'P': n, 'I': n} — numbers already used (an Update continues after them)."""
    start = start or {"CR": 0, "P": 0, "I": 0}
    order = {s: i for i, s in enumerate(SEVERITIES)}
    found = sorted(enumerate(fd.get("findings") or []), key=lambda t: (order[t[1]["severity"]], t[0]))
    req = [f for _, f in found if f["severity"] in REQUIRED_SEVERITIES]
    imp = [f for _, f in found if f["severity"] not in REQUIRED_SEVERITIES]
    procs = []
    for p in (ctx.get("process", []) if ctx_process else []):
        d = default_process(p, ctx)
        d.update((fd.get("process_overrides") or {}).get(p["id"], {}))
        procs.append(d)
    procs += fd.get("process") or []
    for i, f in enumerate(req, start["CR"] + 1):
        f["n"] = f"CR{i}"
    for i, f in enumerate(procs, start["P"] + 1):
        f["n"], f["category"], f["severity"] = f"P{i}", "Process", None
    for i, f in enumerate(imp, start["I"] + 1):
        f["n"] = f"I{i}"
    nums = {f["id"]: f["n"] for f in req + imp + (fd.get("process") or []) if f.get("id")}
    if ctx_process:
        nums.update({p["id"]: d["n"] for p, d in zip(ctx.get("process", []), procs)})
    for f in req + procs + imp:
        for k in ("issue", "title", "explanation", "fix"):
            f[k] = resolve_refs(f[k], nums)
    fd["_nums"] = nums
    if any(blocks(f) for f in req):
        rec = "Request Changes"
    elif req:  # every Required Change is a convention, an existing pattern or deferred by a maintainer
        rec = "Approve with changes"
    elif procs:
        rec = "Approve with process to-dos"
    else:
        rec = "Approve with nits" if imp else "Approve"
    return req, procs, imp, rec


def recommendation_md(rec):
    return {"Request Changes": "🔴 Request Changes", "Approve with changes": "🟡 Approve with changes",
            "Approve with process to-dos": "🟡 Approve with process to-dos",
            "Approve with nits": "🟢 Approve with nits", "Approve": "🟢 Approve"}.get(rec, rec)


def carried(v):
    """An earlier finding not fully fixed whose note names one of this Update's findings ([[ref:…]]): what is
    left of it is that new finding, so it is counted there — not twice."""
    return v["status"] in ("partly", "open") and bool(REF.search(v.get("note") or ""))


def before_merge(req, procs, scope, earlier=None):
    """The verdict's short list: blockers, team calls (Required Changes with a precedent tag), process to-dos;
    on an Update also the earlier Required Changes and Process items that are still open."""
    must = [f["n"] for f in req if blocks(f)]
    team = [f["n"] for f in req if not blocks(f)]
    L = []
    if must:
        L.append(f"- **Must fix before merge**{f' ({scope.strip()})' if scope else ''}: {', '.join(must)}")
    if team:
        L.append(f"- **Team call** (convention, existing pattern or deferred by a maintainer): {', '.join(team)}")
    still = [(n, v["status"]) for n, v in sorted((earlier or {}).items(), key=lambda kv: number_key(kv[0]))
             if v["status"] not in ("fixed", "dropped") and not carried(v) and not n.startswith("I")]
    if still:
        tag = lambda n, s: n + (" (partly)" if s == "partly" else "")  # noqa: E731
        cr = ", ".join(tag(n, s) for n, s in still if n.startswith("CR"))
        pp = ", ".join(tag(n, s) for n, s in still if n.startswith("P"))
        L.append("- **Still open from the earlier review:** " + " · ".join(x for x in (cr, pp) if x))
    if procs:
        L.append(f"- **Process:** {', '.join(f['n'] for f in procs)}")
    return L + [""] if L else []


def verdict_index(rec, req, procs, imp):
    if not (req or procs or imp):
        return "Verdict: Approve — clean"
    parts = []
    if req or procs:
        markers = "".join(MARKER[f["severity"]] for f in req)
        if procs:
            markers += (" + " if markers else "") + f"{len(procs)} process"
        parts.append(f"{plural(len(req) + len(procs), 'Required Change')} ({markers})")
    if imp:
        parts.append(plural(len(imp), "Improvement"))
    head = "Verdict: " + (rec if rec in ("Request Changes", "Approve with changes", "Approve with process to-dos")
                          else "Approve")
    return head + " — " + ", ".join(parts)


# ---------------------------------------------------------------- rendering

def findings_section(heading, items, scored_cols=True):
    out = [heading, ""]
    if not items:
        return out + ["None.", ""]
    rows = []
    for f in items:
        sev = f"{MARKER[f['severity']]} {f['severity']}" if f.get("severity") else "—"
        rows.append([f["n"], sev, f["category"], precedent_cell(f.get("precedent")), cell(f["issue"].strip()),
                     cell(fmt_location(f["location"].strip()))])
    out += [table(["#", "Severity", "Category", "Precedent", "Issue", "Location"], rows), "",
            "<details><summary><strong>Explanation &amp; Fix</strong></summary>", ""]
    for f in items:
        out += [f"**{f['n']} — {f['title'].strip()}** · {f['category']} · {fmt_location(f['location'].strip())}",
                f["explanation"].strip()] + precedent_line(f.get("precedent")) + [f"_Fix:_ {f['fix'].strip()}", ""]
    return out + ["</details>", ""]


def precedent_cell(p):
    """The table tag: existing pattern in merged code, deferred by a maintainer, or none."""
    if not p:
        return "—"
    return "existing code" if p["kind"] == "existing" else f"[deferred]({p['ref']})"


def precedent_line(p):
    if not p:
        return []
    if p["kind"] == "existing":
        return [f"_Precedent:_ the same pattern is already in merged code — `{p['ref']}`."]
    return [f"_Precedent:_ a maintainer accepted or deferred the same point — [discussion]({p['ref']})."]


def short(text, limit, first_sentence=True):
    """First sentence (or a word-boundary cut), code spans kept whole, safe for a table cell."""
    t = " ".join(str(text).split())
    m = re.match(r"(.+?[.!?])(\s|$)", t) if first_sentence else None
    if m and len(m.group(1)) <= limit:
        t = m.group(1)
    elif len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    if t.count("`") % 2:
        t = t[:t.rfind("`")].rstrip() + "…"
    parts = re.split(r"(`[^`]*`)", t)  # escape HTML-like text outside code spans
    t = "".join(p if p.startswith("`") else p.replace("<", "&lt;").replace(">", "&gt;") for p in parts)
    return cell(t)


def dismissed_section(items):
    if not items:
        return []
    rows = [[str(d["score"]), short(d["claim"], 140),
             cell(fmt_location(str(d["location"]).strip())), short(d["reason"], 200)] for d in items]
    return ["---", "", "## Checked and dismissed", "", "<details>",
            f"<summary><strong>Candidates scored below 50 ({len(items)})</strong></summary>", "",
            table(["Score", "Candidate", "Location", "Why"], rows), "", "</details>", ""]


def _discussion(ctx):
    f = Path(ctx.get("run_dir") or ".") / ((ctx.get("discussion") or {}).get("file") or "discussion.json")
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def not_taken_up(ctx, items):
    """Dismissed candidates that a reviewer's comment raised: a short answer in the posted review, so a
    comment (e.g. Copilot's) we checked and disagree with isn't left looking ignored. The thread is found
    by the comment id the finder cited in `discussion` (r<id> or issuecomment-<id>) in discussion.json."""
    by_id = load_comment_urls(ctx)
    own = {u for c in (_discussion(ctx).get("comments") or []) if c.get("own_report") for u in [c.get("url")]}
    rows = []
    for it in items:
        # "r4360389025", "issuecomment-…", or a full thread URL ("…#discussion_r4360389025")
        ids = re.findall(r"(?:\br|discussion_r|issuecomment-)(\d{6,})\b", it.get("discussion") or "")
        refs = list(dict.fromkeys(f"{by_id[i][0]} [{'r' + i if 'discussion_r' in by_id[i][1] else 'comment'}]"
                                  f"({by_id[i][1]})" for i in ids if i in by_id and by_id[i][1] not in own))
        if refs:
            rows.append([", ".join(refs), link_comments(short(it["claim"], 300, False)),
                         link_comments(short(it["reason"], 400, False))])
    if not rows:
        return []
    return ["### 🗨️ &nbsp; Review comments not taken up", "",
            "Raised in the review discussion, checked at this head and not counted as findings:", "",
            table(["Raised by", "Claim", "Why not a finding"], rows), ""]


def reviewed_line(ctx):
    """'Reviewed at head … · base … · time' — which code the findings hold for."""
    p = ctx["pr"]
    ts = ctx.get("generated_at") or ""
    when = f"{ts[:10]} {ts[11:16]} UTC" if len(ts) >= 16 else ctx.get("today", "")
    head = f"[`{p['head']['short']}`]({p['url']}/commits/{p['head']['oid']})"
    base_oid = (p.get("base") or {}).get("oid") or ""
    base = f"`{p['base']['ref']}`" + (f" at `{base_oid[:8]}`" if base_oid else "")
    return f"_Reviewed at head {head} · base {base} · {when}_"


def fold(summary, body):
    return ["<details>", f"<summary><strong>{summary}</strong></summary>", "", body.strip(), "", "</details>", ""]


def render(ctx, fd, today):
    p, f = ctx["pr"], ctx["flags"]
    load_comment_urls(ctx)
    req, procs, imp, rec = layout(ctx, fd)
    issues = [i["number"] for i in (ctx.get("issue") or {}).get("linked", [])]
    now = ctx["status_now"]
    L = ["---", "type: pr-report", f"date: {today}", f"status: {now['frontmatter']}", f"pr: [{p['number']}]",
         f"issue: [{', '.join(map(str, issues))}]", f"author: {p['author']}", f"branch: {p['head']['ref']}", "---", "",
         f"# PR #{p['number']}: {p['title']}", "",
         f"**Author:** {p['author']} · **Status:** {now['line']} · **Base:** `{p['base']['ref']}` ← `{p['head']['ref']}`",
         f"**Size:** {plural(p['changed_files'], 'file')}, +{p['additions']} / −{p['deletions']} · "
         f"**Created:** {p['created']} · [View on GitHub]({p['url']})", ""]
    if f["base_not_main"]:
        L += [f"> **Base branch is `{p['base']['ref']}`, not `main`.**", ""]
    L += ["---", "", f"## PR Review Report by [{SKILL}]({SKILL_URL})", "",
          reviewed_line(ctx), "",
          "### ⚖️ &nbsp; Verdict", "",
          f"Recommendation: **{recommendation_md(rec)}** {NBSP4} Confidence to Merge: **{fd['confidence']}**", ""]
    L += before_merge(req, procs, fd.get("scope"))
    L += [          resolve_refs(fd["summary"].strip(), fd["_nums"]), ""]
    L += findings_section("### 🔧 &nbsp; Required Changes", req + procs)
    L += findings_section("### 💡 &nbsp; Improvements", imp)
    L += not_taken_up(ctx, fd.get("dismissed") or [])
    nums = fd["_nums"]
    ov = {k: resolve_refs(v, nums) for k, v in fd["overview"].items() if v}
    qa = {k: [resolve_refs(x, nums) for x in v] for k, v in fd["qa"].items() if v}
    L += ["---", "", "## Solution Overview", ""]
    L += fold("What was done", ov["what"])
    if ov.get("how"):
        L += fold("How it is implemented", ov["how"])
    if ov.get("affects"):
        L += fold("What it affects (blast radius)", ov["affects"])
    L += ["---", "", "## QA Test Plan", ""]
    if qa.get("core_path"):
        L += fold("Core Path", "\n".join(f"{i}. {s.strip()}" for i, s in enumerate(qa["core_path"], 1)))
    L += fold("Edge Cases", "\n".join(f"- {s.strip()}" for s in qa["edge_cases"]))
    L += dismissed_section(fd.get("dismissed") or [])
    prov = ctx.get("provenance", ["read-only"]) + [x for x in fd.get("provenance_extra", []) if x]
    L += ["---", "", f"_Analyzed {today} · commit `{p['head']['short']}` · {' · '.join(prov)} · skill: {SKILL}_", ""]
    text = "\n".join(L)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, (req, procs, imp, rec)


# ---------------------------------------------------------------- DOCS writes

ROW_RE = re.compile(r"^\| \[#(\d+)\]\(")


def upsert_index(readme, ctx, row_date, affected, verdict):
    p = ctx["pr"]
    lines = readme.read_text(encoding="utf-8").split("\n")
    rows = [i for i, l in enumerate(lines) if ROW_RE.match(l)]
    if not rows:
        raise Invalid(f"{readme}: no index table rows found — add the table by hand first")
    name = Path(ctx["report"]["path"]).name
    row = (f"| [#{p['number']}]({p['url']}) | {row_date} | {cell(p['title'])} | "
           f"{cell(affected.strip())} {verdict} | [{name}](./{name}) |")
    existing = [i for i in rows if ROW_RE.match(lines[i]).group(1) == str(p["number"])]
    if existing:
        lines[existing[0]] = row
        for i in reversed(existing[1:]):
            del lines[i]
        action = "replaced"
    else:
        key = (p["created"], p["number"])
        at = rows[-1] + 1
        for i in rows:
            m = re.search(r"\| (\d{4}-\d{2}-\d{2})", lines[i])
            other = (m.group(1) if m else "0000-00-00", int(ROW_RE.match(lines[i]).group(1)))
            if other < key:
                at = i
                break
        lines.insert(at, row)
        action = "inserted"
    readme.write_text("\n".join(lines), encoding="utf-8")
    return action


def set_index_date(readme, number, date_cell):
    lines = readme.read_text(encoding="utf-8").split("\n")
    for i, l in enumerate(lines):
        m = ROW_RE.match(l)
        if m and m.group(1) == str(number):
            cells = l.split(" | ")
            cells[1] = date_cell
            lines[i] = " | ".join(cells)
            readme.write_text("\n".join(lines), encoding="utf-8")
            return "Date cell updated"
    return "no index row for this PR — add it by hand"


UPDATE_TAIL = re.compile(r" · Update \d{4}-\d{2}-\d{2} \(`[0-9a-f]+`\):[^|]*$")


def update_tail(today, short, req, procs, imp, fixed=None, rec=None):
    """' · Update <date> (`sha`): <recommendation> — …' — the PR's state at that head and what the block added."""
    parts = []
    if req or procs:
        markers = "".join(MARKER[f["severity"]] for f in req)
        if procs:
            markers += (" + " if markers else "") + f"{len(procs)} process"
        parts.append(f"{plural(len(req) + len(procs), 'Required Change')} ({markers})")
    if imp:
        parts.append(plural(len(imp), "Improvement"))
    return (f" · Update {today} (`{short}`): " + (f"{rec} — " if rec else "")
            + (", ".join(parts) if parts else "no new findings")
            + (f"; {fixed} earlier fixed" if fixed is not None else ""))


def set_index_update(readme, number, tail):
    """Replace the row's Update tail (or add one) at the end of its affected/verdict cell."""
    lines = readme.read_text(encoding="utf-8").split("\n")
    for i, l in enumerate(lines):
        m = ROW_RE.match(l)
        if m and m.group(1) == str(number):
            cells = l.split(" | ")
            if len(cells) < 5:
                return "Update tail NOT added — unexpected row format"
            cells[3] = UPDATE_TAIL.sub("", cells[3]) + tail
            lines[i] = " | ".join(cells)
            readme.write_text("\n".join(lines), encoding="utf-8")
            return "Update tail set"
    return "no index row for this PR — add it by hand"


LINE_PREFIX = re.compile(r"^line \d+: ")


def field_markdown_problems(fd):
    """The Markdown check, per text field — so an error names the field to fix, not a line of report.md."""
    hooks = Path(__file__).resolve().parents[3] / "hooks"
    sys.path.insert(0, str(hooks))
    try:
        import check_report_md
    except Exception:
        return []
    import tempfile
    out = []
    for where, text in text_fields(fd):
        if not isinstance(text, str) or not text.strip():
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
            tf.write(text + "\n")
        try:
            for prob in check_report_md.check(tf.name):
                out.append(where + ": " + LINE_PREFIX.sub("", prob))
        finally:
            os.unlink(tf.name)
    return out


def markdown_problems(path):
    hooks = Path(__file__).resolve().parents[3] / "hooks"
    sys.path.insert(0, str(hooks))
    try:
        import check_report_md
    except Exception:
        return None
    return check_report_md.check(str(path))


def run_related(docs):
    tool = Path(docs) / "tools" / "update-related.py"
    if not tool.is_file():
        return "update-related.py not found — skipped (say so when reporting back)"
    p = subprocess.run([sys.executable, str(tool)], capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()
    warn = [l for l in out.splitlines() if re.search(r"(?i)duplicate|warn|error", l)]
    return ("ok" if p.returncode == 0 else f"exit {p.returncode}") + ("" if not warn else ":\n  " + "\n  ".join(warn))


UPDATE_HEAD = re.compile(r"^## Update — ", re.M)
FOOTER = "\n---\n\n_Analyzed"


def earlier_numbers(ctx):
    """CR/P/I numbers already in the report (without an Update block for this head) — an Update may cite them."""
    try:
        return {r[0] for r in quotes.earlier_rows(ctx["report"]["path"], ctx["pr"]["head"]["short"])}
    except (OSError, KeyError, TypeError):
        return set()


def used_numbers(report_text):
    used = {"CR": 0, "P": 0, "I": 0}
    for kind, n in re.findall(r"^\| *(CR|P|I)(\d+) *\|", report_text, re.M):
        used[kind] = max(used[kind], int(n))
    return used


def update_recommendation(ctx, req, procs, imp, earlier):
    """The PR's state at this head: the Update's own findings plus the earlier ones not fixed yet,
    by the same rule as layout(): blocks() on the earlier rows' Category and Precedent cells."""
    try:
        row = {r[0]: {"category": r[5], "precedent": r[4] not in ("", "—", "-")} for r in
               quotes.earlier_rows(ctx["report"]["path"], ctx["pr"]["head"]["short"], detail=True)}
    except (OSError, KeyError, TypeError):
        row = {}
    still = [n for n, v in (earlier or {}).items() if v["status"] not in ("fixed", "dropped") and not carried(v)]
    old = [row.get(n, {"category": "Bug"}) for n in still if n.startswith("CR")]  # unknown row: count it as blocking
    must = [f for f in req if blocks(f)] + [r for r in old if blocks(r)]
    team = [f for f in req if not blocks(f)] + [r for r in old if not blocks(r)]
    if must:
        return "Request Changes"
    if team:
        return "Approve with changes"
    if procs or any(n.startswith("P") for n in still):
        return "Approve with process to-dos"
    return "Approve with nits" if imp or any(n.startswith("I") for n in still) else "Approve"


def render_update(ctx, fd, today, report_text):
    """-> (block, layout tuple). The block goes before the report's footer."""
    short = ctx["pr"]["head"]["short"]
    base_text = strip_update(report_text, short)
    load_comment_urls(ctx)
    req, procs, imp, rec = layout(ctx, fd, start=used_numbers(base_text), ctx_process=False)
    nums = fd["_nums"]
    ov = {k: resolve_refs(v, nums) for k, v in (fd.get("overview") or {}).items() if v}
    L = [f"## Update — {today}, head `{short}`", "", reviewed_line(ctx), ""]
    earlier = fd["earlier"]
    rec = update_recommendation(ctx, req, procs, imp, earlier)
    # the verdict first, as in the main report: earlier findings still open count as much as new ones
    L += ["### ⚖️ &nbsp; Verdict", "",
          f"Recommendation: **{recommendation_md(rec)}** {NBSP4} Confidence to Merge: **{fd['confidence']}**", ""]
    L += before_merge(req, procs, fd.get("scope"), earlier)
    by = {s: [(n, resolve_refs(v["note"].strip(), nums)) for n, v in sorted(earlier.items(), key=lambda kv: number_key(kv[0]))
              if v["status"] == s] for s in EARLIER_STATUS}
    L += ["### Fixed since last analysis", ""]
    L += [f"- {n} — {note}" for n, note in by["fixed"]] or ["None of the earlier findings is fixed yet."]
    L += [""]
    for s, title in (("partly", "Partly fixed"), ("open", "Still open"), ("dropped", "No longer reviewed")):
        if by[s]:
            L += [f"**{title}**", ""] + [f"- {n} — {note}" for n, note in by[s]] + [""]
    L += findings_section("### 🔧 &nbsp; Required Changes", req + procs)
    L += findings_section("### 💡 &nbsp; Improvements", imp)
    L += not_taken_up(ctx, fd.get("dismissed") or [])
    # the delta's walkthrough last and folded, as Solution Overview in the main report: statuses and findings first
    L += ["### What changed", ""] + fold("What was done", ov["what"])
    for k, title in (("how", "How it is implemented"), ("affects", "What it affects (blast radius)")):
        if ov.get(k):
            L += fold(title, ov[k])
    block = re.sub(r"\n{3,}", "\n\n", "\n".join(L)).rstrip() + "\n"
    return block, (req, procs, imp, rec)


def strip_update(text, short):
    """The report without an earlier Update block for the same head (a re-render replaces it)."""
    m = re.search(r"^## Update — [^\n]*head `" + re.escape(short) + "`", text, re.M)
    if not m:
        return text
    rest = text[m.end():]
    nxt = UPDATE_HEAD.search(rest)
    end = m.end() + (nxt.start() if nxt else (rest.find(FOOTER) if FOOTER in rest else len(rest)))
    return text[:m.start()].rstrip("\n") + "\n" + text[end:].lstrip("\n") if nxt else \
        text[:m.start()].rstrip("\n") + text[end:]


def insert_update(ctx, block, today, tail=None):
    path = Path(ctx["report"]["path"])
    t = strip_update(path.read_text(encoding="utf-8"), ctx["pr"]["head"]["short"])
    i = t.rfind(FOOTER)
    if i < 0:
        raise Invalid(f"{path}: no '---' + '_Analyzed' footer to insert the Update before")
    t = t[:i].rstrip("\n") + "\n\n" + block + t[i:]
    footer_old, footer_new = ctx["report"].get("footer"), ctx["report"].get("footer_new")
    if footer_old and footer_new and footer_old in t and f"updated for `{ctx['pr']['head']['short']}`" not in footer_old:
        t = t.replace(footer_old, footer_new, 1)
    su = ctx["report"].get("status_update")
    if su:
        t = re.sub(r"(?m)^status:\s*\S+", f"status: {su['frontmatter_status']}", t, count=1)
        t = re.sub(r"(\*\*Status:\*\*\s*)[^·\n]+?(\s*·|\s*$)", lambda m: m.group(1) + su["status_line"] + m.group(2),
                   t, count=1, flags=re.M)
    path.write_text(t, encoding="utf-8")
    readme = Path(ctx["docs"]) / "aurora-dashboard-kb" / "prs" / "README.md"
    idx = set_index_date(readme, ctx["pr"]["number"], su["index_date"]) if su else "Date unchanged (status didn't change)"
    if tail:
        idx += "; " + set_index_update(readme, ctx["pr"]["number"], tail)
    return path, idx


def apply_status(ctx):
    su = ctx["report"]["status_update"]
    path = Path(ctx["report"]["path"])
    t = path.read_text(encoding="utf-8")
    t = re.sub(r"(?m)^status:\s*\S+", f"status: {su['frontmatter_status']}", t, count=1)
    t, n = re.subn(r"(\*\*Status:\*\*\s*)[^·\n]+?(\s*·|\s*$)", lambda m: m.group(1) + su["status_line"] + m.group(2),
                   t, count=1, flags=re.M)
    if su.get("footer_old") and su.get("footer_new"):
        if su["footer_old"] not in t:
            raise Invalid("footer in the report changed since collect.py read it — re-run collect.py")
        t = t.replace(su["footer_old"], su["footer_new"], 1)
    path.write_text(t, encoding="utf-8")
    idx = set_index_date(Path(ctx["docs"]) / "aurora-dashboard-kb" / "prs" / "README.md",
                         ctx["pr"]["number"], su["index_date"])
    return [f"Report: {path} (status → {su['status_line']})", f"Index: {idx}",
            f"Related: {run_related(ctx['docs'])}"]


# ---------------------------------------------------------------- main

def main(argv):
    args = {"run": None, "check": False, "dry": False}
    it = iter(argv)
    try:
        for x in it:
            if x == "--run":
                args["run"] = next(it)
            elif x == "--check":
                args["check"] = True
            elif x == "--dry-run":
                args["dry"] = True
            else:
                raise StopIteration
    except StopIteration:
        print(__doc__)
        return 2
    if not args["run"]:
        print(__doc__)
        return 2
    run_dir = Path(args["run"])
    try:
        ctx = json.loads((run_dir / "context.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: {run_dir}/context.json not found — run collect.py first")
        return 2
    today = dt.date.today().isoformat()
    mode = ctx["mode"]

    if mode == "status":
        if args["check"] or args["dry"]:
            print(f"Mode status: would set {ctx['report']['status_update']}")
            return 0
        try:
            print("\n".join(apply_status(ctx)))
        except Invalid as e:
            print(f"ERROR: {e}")
            return 1
        return 0
    if mode not in ("full", "rerun", "update"):
        print(f"ERROR: mode {mode!r} — render.py handles full, rerun, update and status")
        return 1

    fp = run_dir / "findings.json"
    try:
        fd = json.loads(fp.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: {fp} not found — write it first (references/findings-format.md)")
        return 1
    except ValueError as e:
        print(f"INVALID findings.json — not valid JSON: {e}")
        return 1
    chk = validate(ctx, fd)
    if chk.errors:
        print(f"INVALID findings.json — {len(chk.errors)} error(s), nothing written:\n  " + "\n  ".join(chk.errors))
        if chk.warnings:
            print("Warnings:\n  " + "\n  ".join(chk.warnings))
        return 1
    if args["check"]:
        print("findings.json: valid" + ("\nWarnings:\n  " + "\n  ".join(chk.warnings) if chk.warnings else ""))
        return 0

    if mode == "update":
        report_text = Path(ctx["report"]["path"]).read_text(encoding="utf-8")
        text, (req, procs, imp, rec) = render_update(ctx, fd, today, report_text)
    else:
        text, (req, procs, imp, rec) = render(ctx, fd, today)
    draft = run_dir / "report.md"
    draft.write_text(text, encoding="utf-8")
    md = markdown_problems(draft)
    if md:
        print(f"MARKDOWN PROBLEMS in {draft} — fix the text (texts.json, or findings.json on a release PR), "
              "re-run; nothing written to DOCS:\n  "
              + "\n  ".join(md[:20]))
        return 1
    sev = "".join(MARKER[f["severity"]] for f in req)
    if mode == "update":
        L = [f"Update block: {len(req)} Required Changes {sev}, {len(procs)} Process, {len(imp)} Improvements "
             f"({', '.join(f['n'] for f in req + procs + imp) or 'none'})",
             "Markdown: " + ("OK" if md == [] else "check skipped (hook not installed)")]
        if chk.warnings:
            L.append("Warnings:\n  " + "\n  ".join(chk.warnings))
        fixed = sum(v["status"] == "fixed" for v in fd["earlier"].values()) if fd.get("earlier") else None
        tail = update_tail(today, ctx["pr"]["head"]["short"], req, procs, imp, fixed, rec)
        if args["dry"]:
            print("\n".join([f"Draft: {draft} (dry run — DOCS untouched)"] + L + [f"Index row tail would be:{tail}"]))
            return 0
        try:
            path, idx = insert_update(ctx, text, today, tail)
        except Invalid as e:
            print(f"ERROR: {e}")
            return 1
        print("\n".join([f"Report: {path} (Update block inserted before the footer)",
                         f"Draft (for the fact-check): {draft}"] + L +
                        [f"Index: {idx}", f"Related: {run_related(ctx['docs'])}"]))
        return 0
    L = [f"Verdict: {recommendation_md(rec)} · Confidence {fd['confidence']}",
         f"Findings: {len(req)} Required Changes {sev}, {len(procs)} Process, {len(imp)} Improvements",
         "Markdown: " + ("OK" if md == [] else "check skipped (hook not installed)")]
    if chk.warnings:
        L.append("Warnings:\n  " + "\n  ".join(chk.warnings))
    verdict = verdict_index(rec, req, procs, imp)
    if args["dry"]:
        L.insert(0, f"Draft: {draft} (dry run — DOCS untouched)")
        L.append(f"Index row would end with: {verdict}")
        print("\n".join(L))
        return 0
    target = Path(ctx["report"]["path"])
    target.write_text(text, encoding="utf-8")
    try:
        action = upsert_index(Path(ctx["docs"]) / "aurora-dashboard-kb" / "prs" / "README.md", ctx,
                              ctx["status_now"]["index_date"], fd["index_affected"], verdict)
    except Invalid as e:
        action = f"NOT updated — {e}"
    L = [f"Report: {target}", f"Draft (for the fact-check): {draft}"] + L + \
        [f"Index: row {action} — {verdict}", f"Related: {run_related(ctx['docs'])}"]
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
