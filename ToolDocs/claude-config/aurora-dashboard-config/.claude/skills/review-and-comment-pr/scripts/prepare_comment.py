#!/usr/bin/env python3
"""Prepare a review-and-comment-pr report for posting as a PR comment.

Usage: prepare_comment.py <report.md> <pr-number> [--update]

Slices the review portion (from "## PR Review Report" to the end of the
QA Test Plan, without frontmatter, title and the "_Analyzed" footer; with
--update, only the newest "## Update — …" block) into
/tmp/pr-<number>-comment.md, scans it for what must not go public, checks
the Markdown, and prints a summary for the hand-off. Exit 0 = clean,
1 = blocking hits, 2 = usage/slicing error.
"""
import os, re, subprocess, sys

SCAN = [
    ("secret", r"-----BEGIN [A-Z ]*KEY-----"),
    ("secret", r"(?i)\b(authorization|bearer)\s*[:=]\s*\S{8,}"),
    ("secret", r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{8,}"),
    ("secret", r"\bAKIA[0-9A-Z]{16}\b"),
    ("secret", r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    ("secret", r"(?<![\w/.-])(?=[A-Za-z0-9+=]*\d)(?=[A-Za-z0-9+=]*[A-Za-z])[A-Za-z0-9+=]{40,}(?![\w/.-])"),
    ("local path", r"(/Users/[^/\s`]+|/home/[^/\s`]+|[A-Za-z]:\\Users\\|/private/var/|/private/tmp/|/var/folders/)"),
    ("internal host", r"(?i)\b[\w.-]+\.(internal|corp|local|lan)\b"),
    ("internal host", r"(?i)\b(github\.tools\.sap|[\w.-]*\.cloud\.sap|[\w.-]*\.sap\.corp|jira\.|confluence\.|grafana\.|wiki\.)"),
    ("private IP", r"\b(10\.\d{1,3}|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    ("e-mail", r"\b[\w.+-]+@[\w-]+(\.[\w-]+)*\.[A-Za-z]{2,}\b"),
    ("env data", r"(?i)\b(OS_PASSWORD|OS_APPLICATION_CREDENTIAL_SECRET|OS_AUTH_TOKEN|AWS_SECRET_ACCESS_KEY)\b"),
]

def slice_comment(text, update):
    footer = text.find("\n---\n\n_Analyzed")
    if update:
        starts = [m.start() for m in re.finditer(r"^## Update — ", text, re.M)]
        if not starts: raise ValueError("no '## Update — …' block found")
        a = starts[-1]
        b = footer if footer > a else len(text)
        nxt = re.search(r"^## (?!Update — )", text[a + 1:b], re.M)
        if nxt: b = a + 1 + nxt.start()
    else:
        a = text.find("## PR Review Report")
        if a < 0: raise ValueError("no '## PR Review Report' heading found")
        b = footer if footer > a else len(text)
        internal = text.find("\n---\n\n## Checked and dismissed", a)  # KB-only section, never posted
        if 0 < internal < b: b = internal
    return text[a:b].rstrip() + "\n"

def markdown_problems(path):
    hook = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "hooks", "check_report_md.py")
    sys.path.insert(0, os.path.dirname(os.path.abspath(hook)))
    try:
        import check_report_md
    except Exception:
        return None  # hook not installed on this machine: skip, don't block
    return check_report_md.check(path)

MAX_COMMENT = 60000   # GitHub caps a comment at 65536 characters
KB_URL = "https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/"


def fit(body, report):
    """A too long review drops its Solution Overview (it stays in the KB report) — -> (body, note)."""
    if len(body) <= MAX_COMMENT:
        return body, None
    a = body.find("\n---\n\n## Solution Overview")
    b = body.find("\n---\n\n## ", a + 1) if a >= 0 else -1
    if a < 0:
        return body, f"{len(body)} chars, over {MAX_COMMENT}, and no Solution Overview to leave out"
    i = report.replace("\\", "/").find("aurora-dashboard-kb/")
    link = f"[the full report]({KB_URL}{report.replace(chr(92), '/')[i:]})" if i >= 0 else "the full report in the KB"
    body = body[:a] + f"\n---\n\n## Solution Overview\n\nLeft out of this comment for length — see {link}.\n" \
        + (body[b:] if b >= 0 else "")
    return body, f"Solution Overview left out for length (now {len(body)} chars)"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2: print(__doc__); return 2
    report, number = args
    try:
        body = slice_comment(open(report, encoding="utf-8").read(), "--update" in sys.argv)
    except Exception as e:
        print(f"ERROR: {e}"); return 2
    body, fit_note = fit(body, report)
    out = f"/tmp/pr-{number}-comment.md"
    open(out, "w", encoding="utf-8").write(body)

    hits = []
    section = ""
    for n, line in enumerate(body.splitlines(), 1):
        if line.startswith("#"): section = line.strip("# ").strip()
        for kind, pat in SCAN:
            for m in re.finditer(pat, line):
                hits.append(f"  line {n} [{section[:40]}] {kind}: {m.group(0)[:80]}")
    md = markdown_problems(out)

    try:
        login = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True, timeout=20).stdout.strip() or "?"
    except Exception:
        login = "? (gh not available)"
    verdict = re.search(r"^Recommendation:.*$", body, re.M)
    reviewed = re.search(r"^_Reviewed at .*_$", body, re.M)
    counts = {k: len(re.findall(rf"^\| *{k}\d+ *\|", body, re.M)) for k in ("CR", "P", "I")}
    links = sorted(set(re.findall(r"https?://[^\s)>\]]+", body)))

    print(f"Comment file: {out} ({len(body)} chars, {body.count(chr(10))} lines)")
    if fit_note:
        print(f"Length: {fit_note}")
    print(f"Post as: @{login}")
    print(f"Verdict: {verdict.group(0) if verdict else '(no Recommendation line)'}")
    if "--update" in sys.argv:  # the Update's verdict list: its own blockers and the earlier ones still open
        m = re.search(r"^### ⚖️ &nbsp; Verdict\n(.*?)(?=^#{2,3} |\Z)", body, re.M | re.S)
        before = [l for l in (m.group(1).splitlines() if m else []) if l.startswith("- ")]
        print("Before merge:" + ("\n" + "\n".join("  " + l for l in before) if before else " none"))
    print(f"Reviewed: {reviewed.group(0).strip('_') if reviewed else '(no Reviewed line — older report)'}")
    print(f"Findings: {counts['CR']} Required Changes, {counts['P']} Process, {counts['I']} Improvements")
    print("Sections: " + " | ".join(re.findall(r"^#{2,3} +(.+)$", body, re.M)))
    print("Links:\n" + ("\n".join("  " + l for l in links) if links else "  none"))
    if hits:
        print("SAFETY HITS — posting is blocked until the user decides:\n" + "\n".join(hits))
    else:
        print("Safety scan: clean — secrets, local paths, internal hosts, private IPs, e-mails, env data")
    if md is None:
        print("Markdown: check skipped — .claude/hooks/check_report_md.py not installed (not blocking)")
    elif md:
        print("MARKDOWN PROBLEMS — fix the report and re-run:\n" + "\n".join("  " + p for p in md))
    else:
        print("Markdown: OK")
    return 1 if hits or md else 0

if __name__ == "__main__":
    sys.exit(main())
