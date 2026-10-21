#!/usr/bin/env python3
"""Claude Code hook: keep PR-report Markdown renderable on GitHub.

PostToolUse (Write/Edit): checks a report written under
  DOCS/aurora-dashboard-kb/prs/*.md (not README.md).
PreToolUse (Bash): checks the --body-file of `gh pr comment` and blocks
  the post if the Markdown is broken.
Exit 2 + stderr = problems shown to Claude (and, before a post, the call
is blocked). Anything else, or any error in this script, exits 0.
"""
import json, re, sys

ALLOWED = {"details", "summary", "strong", "br", "sub", "sup"}
TAG = re.compile(r"</?([A-Za-z][A-Za-z0-9-]*)\b[^>]*>")
HOWTO = ("Fix: wrap inline code that itself contains a backtick in a longer "
         "fence with spaces — `` t`Try Again` `` — or move it into a fenced "
         "block; never escape a backtick with \\ (escapes don't work inside "
         "code); put HTML-like text such as <div> inside backticks; write paths in full, never `.../`.")

def check(path):
    problems, fence, opened, closed = [], None, 0, 0
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.rstrip("\n")
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            if fence is None: fence = m.group(1)
            elif m.group(1).startswith(fence): fence = None
            continue
        if fence: continue
        for ab in re.finditer(r"`((?:\.\.\.|…)/[^`]*)`", line):
            problems.append(f"line {n}: abbreviated path `{ab.group(1)[:60]}` — write the full repo-relative path (packages/aurora/src/...); the comment is public, short paths are ambiguous and not clickable")
        outside, i = [], 0
        while i < len(line):
            if line[i] == "\\" and i + 1 < len(line) and line[i + 1] == "`":
                problems.append(f"line {n}: escaped backtick \\` outside code")
                i += 2; continue
            if line[i] == "`":
                j = i
                while j < len(line) and line[j] == "`": j += 1
                run = line[i:j]
                k = re.search(r"(?<!`)" + run + r"(?!`)", line[j:])
                if not k:
                    problems.append(f"line {n}: unclosed code span at column {i + 1}")
                    outside.append(line[i:]); break
                i = j + k.end(); continue
            outside.append(line[i]); i += 1
        for t in TAG.finditer("".join(outside)):
            name = t.group(1).lower()
            if name not in ALLOWED:
                problems.append(f"line {n}: raw HTML <{t.group(1)}> outside code")
            elif name == "details":
                if t.group(0).startswith("</"): closed += 1
                else: opened += 1
    if fence: problems.append("end of file: unclosed fenced code block")
    if opened != closed:
        problems.append(f"<details> opened {opened} times, closed {closed} times")
    return problems

def target(data):
    tool, inp = data.get("tool_name"), data.get("tool_input") or {}
    if tool in ("Write", "Edit", "MultiEdit"):
        p = inp.get("file_path") or ""
        if "/DOCS/aurora-dashboard-kb/prs/" in p and p.endswith(".md") and not p.endswith("/README.md"):
            return p, "report"
    if tool == "Bash":
        cmd = inp.get("command") or ""
        if re.search(r"\bgh\s+pr\s+comment\b", cmd):
            m = re.search(r"--body-file[=\s]+(['\"]?)([^'\"\s]+)\1", cmd)
            if m: return m.group(2), "post"
    return None, None

def main():
    try:
        data = json.load(sys.stdin)
        path, kind = target(data)
        if not path: return 0
        problems = check(path)
    except Exception:
        return 0
    if not problems: return 0
    head = ("Blocked: the PR comment's Markdown would render broken on GitHub. "
            "Fix the report, re-slice the comment and try again."
            if kind == "post" else
            "The report's Markdown will render broken on GitHub — fix these lines now.")
    print(head + f"\nFile: {path}\n" + "\n".join(problems[:20]) + "\n" + HOWTO, file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main())
