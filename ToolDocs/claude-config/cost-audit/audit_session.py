#!/usr/bin/env python3
"""Cost audit of one Claude Code session log (+ its subagents).

Usage:
  python3 audit_session.py <session.jsonl> [<session dir>]                 overview
  python3 audit_session.py <session.jsonl> [<session dir>] --agent "finder d"   one agent step by step
  (--agent main = the orchestrator; the name matches the agent's description, case-insensitive)

Overview: totals from cost-state next to a recount at list prices, a sanity
check that the log holds one run, one row per agent (model, effort, requests,
context, thinking, estimated cost), the orchestrator's context per request,
its tool calls, each agent's tool calls and errors. The per-agent cost is
the agent's share of its model's cost-state total, weighted input 1 /
cache write 1.25 / cache read 0.1 / output 5.
"""
import json, re, sys, collections
from pathlib import Path

W = {"in": 1.0, "cw": 1.25, "cr": 0.1, "out": 5.0}
# $ per million tokens: (input, output, long-context input, long-context output) — Anthropic list prices.
# Cache write = 1.25 x input, cache read = 0.1 x input. Long context applies to requests over 200k input.
PRICES = [
    (r"opus.*4[.-]?[56]|opus-4-5|4\.5-opus|4\.6-opus", (5, 25, None, None), "Opus 4.5/4.6"),
    (r"opus.*4([.-]?[01])?\b|4(\.1)?-opus", (15, 75, None, None), "Opus 4/4.1"),
    (r"sonnet.*4[.-]?[56]|4\.5-sonnet|4\.6-sonnet|sonnet-4-5", (3, 15, 6, 22.5), "Sonnet 4.5/4.6"),
    (r"sonnet.*4\b|sonnet-4|4-sonnet", (3, 15, 6, 22.5), "Sonnet 4"),
    (r"haiku.*4[.-]?5|4\.5-haiku", (1, 5, None, None), "Haiku 4.5"),
    (r"haiku.*3[.-]?5|3\.5-haiku", (0.8, 4, None, None), "Haiku 3.5"),
]
LONG = 200_000


def rows(p):
    for line in open(p, encoding="utf-8"):
        try:
            yield json.loads(line)
        except ValueError:
            pass


def usage(all_rows):
    """Per request (deduped by requestId/message id)."""
    reqs = collections.OrderedDict()
    for d in all_rows:
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        u = m.get("usage") or {}
        key = d.get("requestId") or m.get("id")
        reqs[key] = {"model": m.get("model"), "ts": d.get("timestamp"), "effort": d.get("effort"),
                     "in": u.get("input_tokens", 0), "cw": u.get("cache_creation_input_tokens", 0),
                     "cr": u.get("cache_read_input_tokens", 0), "out": u.get("output_tokens", 0),
                     "think": (u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0}
    return list(reqs.values())


def ctx(r):
    return r["in"] + r["cw"] + r["cr"]


def weight(r):
    return sum(r[k] * W[k] for k in W)


def summ(reqs):
    s = collections.Counter()
    for r in reqs:
        for k in list(W) + ["think"]:
            s[k] += r[k]
    return s


def fmt(s):
    return f"in {s['in']:,} · cache write {s['cw']:,} · cache read {s['cr']:,} · out {s['out']:,} (thinking {s['think']:,})"


def price_of(model):
    for pat, p, name in PRICES:
        if model and re.search(pat, model, re.I):
            return p, name
    return None, None


def list_cost(reqs, all_long=False):
    """$ at list prices; None if a model is unknown."""
    total = 0.0
    for r in reqs:
        p, _ = price_of(r["model"])
        if not p:
            return None
        long_ = (all_long or ctx(r) > LONG) and p[2]
        i, o = (p[2], p[3]) if long_ else (p[0], p[1])
        total += (r["in"] * i + r["cw"] * i * 1.25 + r["cr"] * i * 0.1 + r["out"] * o) / 1e6
    return total


def tools(all_rows):
    """[(tool_use block, result text, is_error, timestamp)] in order."""
    results = {}
    for d in all_rows:
        m = d.get("message") or {}
        if d.get("type") == "user" and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    t = b.get("content")
                    if isinstance(t, list):
                        t = "\n".join(x.get("text", "") for x in t if isinstance(x, dict))
                    results[b.get("tool_use_id")] = (t or "", bool(b.get("is_error")))
    out = []
    for d in all_rows:
        m = d.get("message") or {}
        if d.get("type") == "assistant":
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    t, e = results.get(b.get("id"), ("", False))
                    out.append((b, t, e, d.get("timestamp"), d.get("requestId") or m.get("id")))
    return out


def describe(b):
    i = b.get("input") or {}
    n = b["name"]
    if n == "Bash":
        return i.get("command", "")
    if n in ("Agent", "Task"):
        return f"type={i.get('subagent_type')} model={i.get('model')} bg={i.get('run_in_background')} · {i.get('description', '')}"
    if n in ("Read", "Write", "Edit"):
        extra = f" offset={i.get('offset')} limit={i.get('limit')}" if n == "Read" and (i.get("offset") or i.get("limit")) else ""
        return i.get("file_path", "") + extra
    return json.dumps(i)[:200]


def kind(b):
    if b["name"] != "Bash":
        return b["name"]
    full = (b.get("input") or {}).get("command", "")
    m = re.search(r"\b(save|collect|briefs|assemble|render|quotes|prepare_comment)\.py\b", full)
    if m:
        return m.group(0)
    c = ""
    for seg in re.split(r"\s*(?:;|&&|\|\||\n)\s*", (b.get("input") or {}).get("command", "")):
        seg = seg.strip()
        if seg and not re.match(r"^(\w+=\S*|cd\b|echo\b|export\b|set\b)", seg):
            c = seg
            break
    for pat, k in [(r"^git\s+(-C\s+\S+\s+)?(--no-pager\s+)?(\w[\w-]*)", None), (r"save\.py", "save.py"),
                   (r"(collect|briefs|assemble|render|quotes|prepare_comment)\.py", None), (r"^curl\b", "curl"),
                   (r"^gh\b", "gh"), (r"^(cat|head|tail|sed|awk)\b", "cat/sed/head"), (r"^(ls|find)\b", "ls/find"),
                   (r"^(grep|rg)\b", "grep"), (r"^python3?\b", "python")]:
        m = re.search(pat, c)
        if m:
            if k:
                return k
            return ("git " + m.group(3)) if pat.startswith("^git") else m.group(0)
    return "Bash other"


def load_agents(sdir):
    out = []
    sub = sdir / "subagents"
    if sub.is_dir():
        for f in sorted(sub.glob("*.jsonl")):
            mf = f.with_suffix(".meta.json")
            meta = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
            out.append((meta.get("agentType", "?"), meta.get("description", f.stem), list(rows(f))))
    return out


def sanity(all_rows, calls):
    notes = []
    starts = [c for c, *_ in calls if c["name"] == "Bash" and "collect.py" in (c.get("input") or {}).get("command", "")]
    if len(starts) > 2:
        notes.append(f"collect.py ran {len(starts)} times — more than one run in this session?")
    audit = [describe(c) for c, *_ in calls if re.search(r"cost-audit|audit_session|\.jsonl\b", describe(c))]
    if audit:
        notes.append(f"{len(audit)} tool call(s) touch the cost audit or session logs — this log mixes the review "
                     "with audit work; orchestrator numbers are inflated. First: " + audit[0][:120])
    prompts = [d for d in all_rows if d.get("type") == "user" and isinstance((d.get("message") or {}).get("content"), str)]
    if len(prompts) > 3:
        notes.append(f"{len(prompts)} typed user messages — check the session holds only the review")
    return notes


def overview(jsonl, sdir):
    all_rows = list(rows(jsonl))
    ver = next((d.get("version") for d in all_rows if d.get("version")), "?")
    cost = [d for d in all_rows if d.get("type") == "cost-state"]
    agents = load_agents(sdir)
    groups = [("MAIN", "orchestrator", usage(all_rows))] + [(t, d, usage(r)) for t, d, r in agents]
    every = [r for _, _, reqs in groups for r in reqs]
    print(f"# Session {jsonl.name} · Claude Code {ver}")
    model_cost = {}
    if cost:
        c = cost[-1]
        model_cost = {m: mu.get("costUSD", 0) for m, mu in (c.get("modelUsage") or {}).items()}
        print(f"Total (cost-state, Claude Code's own estimate): ${c.get('totalCostUSD', 0):.2f} · "
              f"API time {c.get('totalAPIDuration', 0)/60000:.1f} min · wall {c.get('totalDuration', 0)/60000:.1f} min"
              + (" · hasUnknownModelCost" if c.get("hasUnknownModelCost") else ""))
    else:
        print("No cost-state in the log — use /cost output and the recount below.")
    print("\n## Cost per model: cost-state vs recount at Anthropic list prices")
    print(f"{'model':<40} {'family':<15} {'cost-state':>10} {'list':>8} {'all long-ctx':>12}  tokens")
    by_model = collections.defaultdict(list)
    for r in every:
        by_model[r["model"]].append(r)
    for m, reqs in by_model.items():
        _, fam = price_of(m)
        lc, al = list_cost(reqs), list_cost(reqs, all_long=True)
        cs = model_cost.get(m)
        print(f"{str(m)[:40]:<40} {str(fam or 'unknown'):<15} {('$%.2f' % cs) if cs is not None else '—':>10} "
              f"{('$%.2f' % lc) if lc is not None else '—':>8} {('$%.2f' % al) if al is not None else '—':>12}  {fmt(summ(reqs))}")
    print("(list = 200k+ input requests at long-context rates; 'all long-ctx' = every request at those rates, "
          "e.g. a [1m] model billed as long context. Unknown family: compare with your provider's price list.)")
    main_calls = tools(all_rows)
    notes = sanity(all_rows, main_calls)
    print("\n## Sanity check: one run per log?")
    print("\n".join("- " + n for n in notes) if notes else "- looks like a single run")
    eff = collections.Counter(d.get("effort") for d in all_rows if d.get("type") == "assistant")
    print(f"\nOrchestrator effort: {dict(eff)}")
    per_model_w = collections.Counter()
    for r in every:
        per_model_w[r["model"]] += weight(r)
    print("\n## Per agent (est $ = share of its model's cost-state total)")
    print(f"{'agent':<20} {'description':<30} {'model':<28} {'effort':<8} {'req':>4} {'max ctx':>8} {'think':>7} {'est $':>7}")
    for typ, desc, reqs in groups:
        if not reqs:
            print(f"{typ:<20} {desc[:30]:<30} (no requests)")
            continue
        models = ",".join(collections.Counter(r["model"] for r in reqs))
        effs = ",".join(str(e) for e in collections.Counter(r["effort"] for r in reqs))
        est = sum(weight(r) / per_model_w[r["model"]] * model_cost.get(r["model"], 0)
                  for r in reqs if per_model_w[r["model"]])
        print(f"{typ:<20} {desc[:30]:<30} {models[:28]:<28} {effs[:8]:<8} {len(reqs):>4} "
              f"{max(ctx(r) for r in reqs):>8,} {summ(reqs)['think']:>7,} {est:>7.2f}")
    print("\n## Per agent: tool calls by kind, repeats, errors")
    for typ, desc, r in [("MAIN", "orchestrator", all_rows)] + agents:
        calls = tools(r)
        kinds = collections.Counter(kind(b) for b, *_ in calls)
        reps = [(c, n) for c, n in collections.Counter(describe(b) for b, *_ in calls).items() if n > 1]
        errs = [t for _, t, e, *_ in calls if e]
        nreq = len({rid for *_, rid in calls}) or 1
        print(f"  {desc[:36]:<36} {len(calls):>3} calls in {nreq} req ({len(calls)/nreq:.1f}/req) · "
              f"{dict(kinds.most_common())} · errors {len(errs)}"
              + (f" · repeated {sum(n - 1 for _, n in reps)}x" if reps else ""))
        for e in errs[:4]:
            print(f"      ! {' '.join(e.split())[:180]}")
    print("\n## Orchestrator: context per request")
    for i, r in enumerate(groups[0][2], 1):
        print(f"  {i:>3} {(r['ts'] or '')[11:19]} {r['model']}: ctx {ctx(r):,} (write {r['cw']:,}) out {r['out']:,}")
    print("\n## Orchestrator: tool calls")
    for b, t, e, ts, _ in main_calls:
        print(f"  {(ts or '')[11:19]} {b['name']}{' !ERR' if e else ''}: {' '.join(describe(b).split())[:170]}")


def detail(jsonl, sdir, name):
    if name.lower() in ("main", "orchestrator"):
        desc, r = "orchestrator", list(rows(jsonl))
    else:
        hits = [(d, rr) for _, d, rr in load_agents(sdir) if name.lower() in d.lower()]
        if len(hits) != 1:
            print(f"--agent {name!r} matches {len(hits)} agents: " + ", ".join(d for d, _ in hits) if hits
                  else f"--agent {name!r}: no agent with that description")
            return 2
        desc, r = hits[0]
    req_by_id = collections.OrderedDict()
    for d in r:
        if d.get("type") == "assistant":
            m = d.get("message") or {}
            req_by_id[d.get("requestId") or m.get("id")] = m.get("usage") or {}
    order = list(req_by_id)
    calls = tools(r)
    first = next((d for d in r if d.get("type") == "user"), {})
    prompt = (first.get("message") or {}).get("content")
    print(f"# {desc} — {len(order)} requests, {len(calls)} tool calls")
    print(f"Prompt: {prompt if isinstance(prompt, str) else json.dumps(prompt)[:300]}")
    s = summ(usage(r))
    print(f"Tokens: {fmt(s)} · effort {dict(collections.Counter(x['effort'] for x in usage(r)))}\n")
    print(f"{'#':>3} {'time':<8} {'req':>3} {'ctx after':>9} {'out chars':>9}  call")
    for i, (b, t, e, ts, rid) in enumerate(calls, 1):
        n = order.index(rid) + 1 if rid in order else 0
        nxt = req_by_id[order[n]] if n < len(order) else {}
        c_after = sum(nxt.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        print(f"{i:>3} {(ts or '')[11:19]:<8} {n:>3} {c_after:>9,} {len(t):>9,}  {b['name']}{' !ERR' if e else ''}: "
              f"{' '.join(describe(b).split())[:200]}")
        if e:
            print(f"{'':>36}! {' '.join(t.split())[:300]}")
    texts = []
    for d in r:
        if d.get("type") == "assistant":
            for b in (d.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip():
                    texts.append(" ".join(b["text"].split()))
    if texts:
        print("\nAgent's own text between calls (first 10):")
        for x in texts[:10]:
            print(f"  - {x[:240]}")
    return 0


def main(argv):
    agent = None
    if "--agent" in argv:
        i = argv.index("--agent")
        if i + 1 >= len(argv):
            print(__doc__); return 2
        agent = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) not in (1, 2):
        print(__doc__); return 2
    jsonl = Path(argv[0])
    sdir = Path(argv[1]) if len(argv) == 2 else jsonl.with_suffix("")
    if agent:
        return detail(jsonl, sdir, agent)
    overview(jsonl, sdir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
