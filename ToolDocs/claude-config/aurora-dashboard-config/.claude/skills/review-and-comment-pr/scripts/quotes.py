#!/usr/bin/env python3
"""Code quotes and line citations for review-and-comment-pr reports (Phase 3).

Used by render.py on findings.json, and on its own for an Update block
(render.py doesn't handle that mode yet):

  quotes.py --run <run-dir> --report <file.md> [--update]
                                                 check a hand-written Markdown file;
                                                 --update: only its newest "## Update — …" block
  quotes.py --run <run-dir> --describer          out/describer.json -> describer.md,
                                                 placeholders resolved, to copy from

Placeholders (findings.json text fields):
  [[code:<path>:<from>-<to>]]          lines from-to of <path> at the PR head,
  [[code:<path>:<line>]]               inserted as a fenced block (on its own line)
  [[code:<path> | <text> | <n>]]       n lines from the one line containing <text>
  [[at:<path>:<line>]]                 -> `path:line`, checked
  [[at:<path> | <text>]]               -> `path:N`, N = the one line containing <text>
Checks: placeholders resolve; plain `path:line` citations exist and are in
range; fenced blocks typed by hand (not in a fix, not diff/text/console/
shell) appear verbatim at the head or base commit.

Exit codes (CLI): 0 = clean, 1 = problems listed, 2 = usage error.
"""
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

LANG = {".ts": "ts", ".tsx": "tsx", ".js": "js", ".jsx": "jsx", ".mjs": "js", ".json": "json",
        ".md": "markdown", ".py": "python", ".yml": "yaml", ".yaml": "yaml", ".sh": "bash",
        ".css": "css", ".scss": "scss", ".po": "po", ".html": "html"}
EXEMPT_LANGS = {"diff", "text", "console", "sh", "bash", "shell", "txt"}
ELISION = re.compile(r"^\s*(\.\.\.|…|//\s*(\.\.\.|…)|/\*\s*(\.\.\.|…)\s*\*/|#\s*(\.\.\.|…))\s*$")
PLACEHOLDER = re.compile(r"\[\[(code|at):(.+?)\]\](?!\])")   # text may contain "]" (e.g. `x["k"]`)
PLACEHOLDER_START = re.compile(r"\[\[(?:code|at):")                # anything PLACEHOLDER did not parse
CITE = re.compile(r"`([\w.$@/\[\]()+-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?`")
FENCE = re.compile(r"(?ms)^([ \t]*)(`{3,}|~{3,})([^\n`]*)\n(.*?)^[ \t]*\2[ \t]*$")
CAPTION = re.compile(r"^\s*(?://|#|<!--)\s*`?([\w.$@/\[\]()+-]+\.[A-Za-z0-9]+):(\d+)(?:-\d+)?`?\s*(?:-->)?\s*$")
MAX_BLOCK = 30
INTERNAL = re.compile(r"\b(headRefOid|baseRefOid|headRefName|baseRefName)\b|(?<![\w/.-])(context|discussion|candidates|findings|texts|describer)\.json\b"
                      r"|(?<![\w/.-])(pr-body\.md|compose\.md|pr\.diff|delta\.diff|issue-\d+\.md)(?![\w/])"
                      # this review's own steps — the reader doesn't know them
                      r"|(?i:\bfinders?[ -][a-g](?:(?:,\s*|\s+and\s+)[a-g])*\b|\bscorers?\b|\bdescriber\b|\bfact-?check(?:er)?\b)")


class Repo:
    def __init__(self, ctx):
        self.root = ctx["repo"]["root"]
        self.head = ctx["pr"]["head"]["oid"]
        self.base = ctx["pr"]["base"]["oid"]
        self.changed = [f["path"] for f in ctx["pr"]["files"]]
        self._cache = {}
        self.warnings = []

    def lines(self, path, rev=None):
        rev = rev or self.head
        key = (rev, path)
        if key not in self._cache:
            p = subprocess.run(["git", "cat-file", "-p", f"{rev}:{path}"], cwd=self.root,
                               capture_output=True, text=True)
            self._cache[key] = p.stdout.split("\n")[:-1] if p.returncode == 0 and p.stdout.endswith("\n") \
                else (p.stdout.split("\n") if p.returncode == 0 else None)
        return self._cache[key]

    def resolve_name(self, path):
        """A short path (`NetworksList.tsx`, `types/network.ts`) -> the one changed file it names."""
        if "/" in path and (path in self.changed or self.lines(path) is not None):
            return path
        hits = [p for p in self.changed if p == path or p.endswith("/" + path)]
        return hits[0] if len(hits) == 1 else (path if "/" in path else None)

    def find(self, path, text):
        ls = self.lines(path)
        return [i + 1 for i, l in enumerate(ls) if text in l] if ls is not None else None

    def grep_files(self, needle):
        p = subprocess.run(["git", "grep", "-F", "-l", needle, self.head, "--", "."], cwd=self.root,
                           capture_output=True, text=True)
        return [l.split(":", 1)[1] for l in p.stdout.splitlines()][:20] if p.returncode == 0 else []


def dedent(lines):
    ind = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(ind) if ind else 0
    return [l[cut:] if l.strip() else "" for l in lines]


def fenced(lines, path):
    lines = list(lines)
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    body = "\n".join(dedent(lines))
    ticks = "`" * max(3, max((len(m) for m in re.findall(r"`+", body)), default=0) + 1)
    ext = Path(path).suffix.lower()
    return f"{ticks}{LANG.get(ext, '')}\n{body}\n{ticks}"


def near(repo, path, text):
    ls = repo.lines(path) or []
    stripped = {l.strip(): i + 1 for i, l in enumerate(ls) if l.strip()}
    close = difflib.get_close_matches(text.strip(), list(stripped), n=3, cutoff=0.5)
    return "; ".join(f"line {stripped[c]}: {c[:70]!r}" for c in close) or "no similar line"


def resolve_target(repo, inner, where, errors, want_count):
    """-> (path, from, to) or None. inner: 'path:a-b' | 'path:a' | 'path | text [| n]'."""
    if "|" in inner:
        # path | text [| n] — split on " | " around the path and the count only, so the text
        # itself may contain "|" or "||"
        m = re.match(r"^\s*([^|]+?)\s+\|\s+(.+?)" + (r"\s+\|\s+(\S+)\s*$" if want_count else r"\s*$"), inner)
        if not m:
            errors.append(f"{where}: malformed [[{'code' if want_count else 'at'}:{inner}]] — "
                          + ("use path | text | n" if want_count else "use path | text"))
            return None
        parts = list(m.groups())
        path = repo.resolve_name(parts[0]) or parts[0]
        hits = repo.find(path, parts[1])
        if hits is None:
            errors.append(f"{where}: {path} does not exist at head {repo.head[:8]}")
            return None
        if len(hits) != 1:
            errors.append(f"{where}: {parts[1]!r} " + (f"is on {len(hits)} lines of {path} ({', '.join(map(str, hits[:6]))}) — "
                          "make the text unique or give the line number" if hits else
                          f"is not in {path} at head — closest: {near(repo, path, parts[1])}"))
            return None
        n = 1
        if want_count:
            if not parts[2].isdigit() or int(parts[2]) < 1:
                errors.append(f"{where}: line count {parts[2]!r} must be a positive number")
                return None
            n = int(parts[2])
        a, b = hits[0], hits[0] + n - 1
    else:
        m = re.match(r"^(.+?):(\d+)(?:-(\d+))?$", inner.strip())
        if not m:
            errors.append(f"{where}: malformed placeholder {inner!r} — use path:from-to or path | text")
            return None
        path = repo.resolve_name(m.group(1)) or m.group(1)
        a, b = int(m.group(2)), int(m.group(3) or m.group(2))
    ls = repo.lines(path)
    if ls is None:
        errors.append(f"{where}: {path} does not exist at head {repo.head[:8]}")
        return None
    if not (1 <= a <= b <= len(ls)):
        errors.append(f"{where}: {path}:{a}-{b} is out of range ({len(ls)} lines at head)")
        return None
    if b - a + 1 > MAX_BLOCK:
        errors.append(f"{where}: {b - a + 1} lines quoted from {path} — keep an excerpt to {MAX_BLOCK} lines or fewer")
        return None
    return path, a, b


def segments(lines):
    segs, cur = [], []
    for l in lines:
        if ELISION.match(l):
            if cur:
                segs.append(cur)
            cur = []
        elif l.strip():
            cur.append(l.strip())
    if cur:
        segs.append(cur)
    return segs


def match_at(ls, segs):
    """Index (into ls) of the first line where segs match in order, or None."""
    idx = [i for i, l in enumerate(ls) if l.strip()]
    seq = [ls[i].strip() for i in idx]
    first = None
    pos = 0
    for seg in segs:
        hit = next((i for i in range(pos, len(seq) - len(seg) + 1) if seq[i:i + len(seg)] == seg), None)
        if hit is None:
            return None
        first = idx[hit] if first is None else first
        pos = hit + len(seg)
    return first


def block_found(repo, lines):
    """Is this hand-typed block verbatim (ignoring indentation and blank lines) at head or base?"""
    segs = segments(lines)
    if not segs:
        return True
    cands = list(dict.fromkeys(repo.changed + repo.grep_files(segs[0][0])))
    for rev in (repo.head, repo.base):
        for path in cands:
            ls = repo.lines(path, rev)
            if ls and match_at(ls, segs) is not None:
                return True
    return False


def check_hand_blocks(repo, text, where, errors):
    for m in FENCE.finditer(text):
        lang = m.group(3).strip().lower()
        if lang in EXEMPT_LANGS:
            continue
        body = m.group(4).split("\n")
        cap = CAPTION.match(body[0]) if body else None
        if cap:  # "// path:line" caption: the rest must sit at exactly that line
            path, n = repo.resolve_name(cap.group(1)) or cap.group(1), int(cap.group(2))
            ls, segs = repo.lines(path), segments(body[1:])
            if ls is None:
                errors.append(f"{where}: code block caption {cap.group(1)}:{n} — no such file at head {repo.head[:8]}")
                continue
            at = match_at(ls, segs) if segs else n - 1
            if at is None:
                errors.append(f"{where}: code block captioned {cap.group(1)}:{n} is not verbatim in that file at head — "
                              "quote it with [[code:…]]")
            elif at + 1 != n:
                errors.append(f"{where}: code block captioned {cap.group(1)}:{n} starts at line {at + 1}, not {n}")
            continue
        if not block_found(repo, body):
            first = next((l.strip() for l in m.group(4).split("\n") if l.strip()), "")
            errors.append(f"{where}: hand-typed code block starting {first[:60]!r} is not verbatim at head or base — "
                          "quote repo code with [[code:…]]; mark commands, output or other commits' code as ```text")


def check_cites(repo, text, where, errors, warnings=None):
    plain = FENCE.sub("", text)
    for m in CITE.finditer(plain):
        path = repo.resolve_name(m.group(1))
        if path is None:
            continue  # a bare name not among the changed files: can't tell which file — not checked
        a, b = int(m.group(2)), int(m.group(3) or m.group(2))
        ls = repo.lines(path)
        if ls is None:
            if repo.lines(path, repo.base) is None and warnings is not None:
                warnings.append(f"{where}: `{m.group(0).strip('`')}` — {path} is not in this PR's head or base "
                                "(fine if it cites another PR's file)")
        elif not (1 <= a <= b <= len(ls)):
            errors.append(f"{where}: `{m.group(0).strip('`')}` is out of range ({len(ls)} lines at head)")


def resolve_text(repo, text, where, errors, code_ok=True, is_fix=False):
    """Check a findings.json text field and return it with placeholders replaced."""
    if not text:
        return text
    if not is_fix:
        check_hand_blocks(repo, PLACEHOLDER.sub("", text), where, errors)

    def sub(m):
        kind, inner = m.group(1), m.group(2)
        if kind == "code":
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start: line_end if line_end >= 0 else len(text)]
            if line.strip() != m.group(0):
                errors.append(f"{where}: [[code:…]] must stand on its own line")
                return m.group(0)
            if not code_ok:
                errors.append(f"{where}: [[code:…]] is only allowed in explanation, fix and overview")
                return m.group(0)
            t = resolve_target(repo, inner, where, errors, want_count=" | " in inner)
            return fenced(repo.lines(t[0])[t[1] - 1:t[2]], t[0]) if t else m.group(0)
        t = resolve_target(repo, inner, where, errors, want_count=False)
        if not t:
            return m.group(0)
        return f"`{t[0]}:{t[1]}`" if t[1] == t[2] else f"`{t[0]}:{t[1]}-{t[2]}`"

    out = PLACEHOLDER.sub(sub, text)
    internal = sorted({m.group(0) for m in INTERNAL.finditer(FENCE.sub("", text))})
    if internal:
        errors.append(f"{where}: names run-folder files or fields ({', '.join(internal)}) — write for the PR's readers: "
                      "\"the head commit\", \"the PR description\", \"the linked issue\", \"CI\"")
    if PLACEHOLDER_START.search(PLACEHOLDER.sub("", text)):
        errors.append(f"{where}: unparsed [[code:…]]/[[at:…]] placeholder — it must open and close on one line with ]]")
    check_cites(repo, out, where, errors, repo.warnings)
    return out


def resolve_location(repo, loc, where, errors):
    if "|" not in loc:
        return loc
    t = resolve_target(repo, loc, where, errors, want_count=False)
    return f"{t[0]}:{t[1]}" if t else loc


def resolve_findings(ctx, fd):
    """Resolve every placeholder in findings.json in place. -> (errors, warnings)."""
    repo, errors = Repo(ctx), []
    if isinstance(fd.get("summary"), str):
        fd["summary"] = resolve_text(repo, fd["summary"], "summary", errors, code_ok=False)
    items = [(f"{sec}[{i}]", f) for sec in ("findings", "process")
             for i, f in enumerate(fd.get(sec) or []) if isinstance(f, dict)]
    items += [(f"process_overrides.{k}", v) for k, v in (fd.get("process_overrides") or {}).items() if isinstance(v, dict)]
    for where, f in items:
        for k in ("issue", "title", "explanation", "fix"):
            if isinstance(f.get(k), str):
                f[k] = resolve_text(repo, f[k], f"{where}.{k}", errors,
                                    code_ok=k in ("explanation", "fix"), is_fix=k == "fix")
        if isinstance(f.get("location"), str):
            f["location"] = resolve_location(repo, f["location"].strip(), f"{where}.location", errors)
    ov = fd.get("overview") or {}
    for k, v in list(ov.items()):
        if isinstance(v, str):
            ov[k] = resolve_text(repo, v, f"overview.{k}", errors)
    qa = fd.get("qa") or {}
    for k, v in list(qa.items()):
        if isinstance(v, list):
            qa[k] = [resolve_text(repo, x, f"qa.{k}[{i}]", errors, code_ok=False) if isinstance(x, str) else x
                     for i, x in enumerate(v)]
    return errors, repo.warnings


def describer_md(run_dir):
    ctx = json.loads((run_dir / "context.json").read_text(encoding="utf-8"))
    d = json.loads((run_dir / "out" / "describer.json").read_text(encoding="utf-8"))
    repo, errors = Repo(ctx), []
    ov, qa = d.get("overview") or {}, d.get("qa") or {}
    L = ["# Describer's result, placeholders resolved", ""]
    for k, title in (("what", "What was done"), ("how", "How it is implemented"), ("affects", "What it affects")):
        if ov.get(k):
            L += [f"## {title}", "", resolve_text(repo, ov[k], f"overview.{k}", errors), ""]
    if qa.get("core_path"):
        L += ["## Core Path", ""] + [f"{i}. {resolve_text(repo, x, f'qa.core_path[{i - 1}]', errors, code_ok=False)}"
                                     for i, x in enumerate(qa["core_path"], 1)] + [""]
    if qa.get("edge_cases"):
        L += ["## Edge Cases", ""] + [f"- {resolve_text(repo, x, f'qa.edge_cases[{i}]', errors, code_ok=False)}"
                                      for i, x in enumerate(qa["edge_cases"])] + [""]
    out = run_dir / "describer.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"{out}: written" + (" — problems:\n  " + "\n  ".join(errors) if errors else ""))
    return 1 if errors else 0


def main(argv):
    if len(argv) == 3 and argv[0] == "--run" and argv[2] == "--describer":
        return describer_md(Path(argv[1]))
    update = argv[4:] == ["--update"]
    if len(argv) != (5 if update else 4) or argv[0] != "--run" or argv[2] != "--report":
        print(__doc__)
        return 2
    ctx = json.loads((Path(argv[1]) / "context.json").read_text(encoding="utf-8"))
    text = Path(argv[3]).read_text(encoding="utf-8")
    text = text.split("<!-- related:auto", 1)[0]
    if update:  # the older sections quote older heads — check only the new block
        starts = [m.start() for m in re.finditer(r"^## Update — ", text, re.M)]
        if not starts:
            print(f"{argv[3]}: no '## Update — …' block found")
            return 1
        text = text[starts[-1]:]
        end = re.search(r"^---\n\n_Analyzed|^## (?!Update — )", text[1:], re.M)
        if end:
            text = text[:end.start() + 1]
    repo, errors = Repo(ctx), []
    check_hand_blocks(repo, text, argv[3], errors)
    check_cites(repo, text, argv[3], errors, repo.warnings)
    internal = sorted({m.group(0) for m in INTERNAL.finditer(FENCE.sub("", text))})
    if internal:
        errors.append(f"{argv[3]}: names run-folder files or fields ({', '.join(internal)}) — write for the PR's readers")
    if PLACEHOLDER_START.search(text):
        errors.append(f"{argv[3]}: unresolved [[code:…]]/[[at:…]] placeholders — render.py resolves them; "
                      "for an Update, copy resolved text from quotes.py --describer")
    print("\n".join(errors) if errors else "Quotes and citations: OK")
    if repo.warnings:
        print("Warnings:\n  " + "\n  ".join(repo.warnings))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


PRECEDENT_KINDS = ("existing", "deferred")
PRECEDENT_URL = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/(pull|issues)/\d+\S*$")


def check_precedent(repo, p, where, errors):
    """A finding's precedent tag: null, {"kind": "existing", "ref": "<path:line at base>"}
    or {"kind": "deferred", "ref": "<GitHub PR/issue/comment URL>"}."""
    if p is None:
        return
    if not isinstance(p, dict) or set(p) != {"kind", "ref"}:
        errors.append(f"{where}: null or {{\"kind\", \"ref\"}}")
        return
    kind, ref = p.get("kind"), p.get("ref")
    if kind not in PRECEDENT_KINDS:
        errors.append(f"{where}.kind: {kind!r} not one of {list(PRECEDENT_KINDS)}")
        return
    if not isinstance(ref, str) or not ref.strip():
        errors.append(f"{where}.ref: missing or empty")
        return
    if kind == "existing":
        m = re.match(r"^([^\s:]+):(\d+)$", ref.strip())
        if not m:
            errors.append(f"{where}.ref: {ref!r} — a full repo-relative path:line in the merged code (baseRefOid)")
            return
        lines = repo.lines(m.group(1), repo.base)
        if lines is None:
            errors.append(f"{where}.ref: {m.group(1)} does not exist at base {repo.base[:8]} — "
                          "an existing pattern must be in code already merged")
        elif not 1 <= int(m.group(2)) <= len(lines):
            errors.append(f"{where}.ref: {m.group(1)} has {len(lines)} lines at base {repo.base[:8]}")
    elif not PRECEDENT_URL.match(ref.strip()):
        errors.append(f"{where}.ref: {ref!r} — the URL of the PR, issue or comment where a maintainer "
                      "accepted or deferred it (https://github.com/<owner>/<repo>/pull/<n>…)")


EARLIER_ROW = re.compile(r"^\| *(?:CR|P|I)\d+ *\|.*\|\s*$", re.M)


def earlier_rows(report_path, head_short, detail=False):
    """[(number, severity, issue, location)] of the existing report's finding rows (5 columns, or 6 with
    Precedent), without an Update block for this head — the one list every script uses for "earlier".
    detail=True appends the Precedent cell ("" for a 5-column row, "—" for none) and the Category cell."""
    text = Path(report_path).read_text(encoding="utf-8")
    m = re.search(r"^## Update — [^\n]*head `" + re.escape(head_short) + "`", text, re.M)
    if m:
        rest = text[m.end():]
        nxt = re.search(r"^## Update — ", rest, re.M)
        foot = rest.find("\n---\n\n_Analyzed")
        text = text[:m.start()] + text[m.end() + (nxt.start() if nxt else (foot if foot >= 0 else len(rest))):]
    rows = []
    for line in EARLIER_ROW.findall(text):
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]  # an escaped \| stays in its cell
        if len(cells) >= 5:
            rows.append((cells[0], cells[1], cells[-2], cells[-1])
                        + (((cells[3] if len(cells) >= 6 else ""), cells[2]) if detail else ()))
    return rows
