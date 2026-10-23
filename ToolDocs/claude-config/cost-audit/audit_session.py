#!/usr/bin/env python3
"""Cost audit of one Claude Code session log (+ its subagents).

Usage: python3 audit_session.py <session.jsonl> [<session dir with subagents/>]
Prints: totals from cost-state, the main session per request, every subagent,
tool calls of the main session, errors. Provider-agnostic: a share of the
cost is estimated from tokens weighted input 1 / cache write 1.25 /
cache read 0.1 / output 5 within each model.
"""
import json, sys, collections
from pathlib import Path

W = {"in": 1.0, "cw": 1.25, "cr": 0.1, "out": 5.0}

def rows(p):
    for line in open(p, encoding="utf-8"):
        try:
            yield json.loads(line)
        except ValueError:
            pass

def usage(p):
    """Per request (deduped by requestId/message id): model, tokens, time."""
    reqs = collections.OrderedDict()
    for d in rows(p):
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        u = m.get("usage") or {}
        key = d.get("requestId") or m.get("id")
        reqs[key] = {"model": m.get("model"), "ts": d.get("timestamp"),
                     "in": u.get("input_tokens", 0), "cw": u.get("cache_creation_input_tokens", 0),
                     "cr": u.get("cache_read_input_tokens", 0), "out": u.get("output_tokens", 0)}
    return list(reqs.values())

def weight(r):
    return sum(r[k] * W[k] for k in W)

def summ(reqs):
    s = collections.Counter()
    for r in reqs:
        for k in W:
            s[k] += r[k]
    return s

def fmt(s):
    return f"in {s['in']:,} · cache write {s['cw']:,} · cache read {s['cr']:,} · out {s['out']:,}"

def tools(all_rows):
    """Tool calls and failed tool results of one log."""
    calls, errors = [], []
    for d in all_rows:
        m = d.get("message") or {}
        if d.get("type") == "assistant":
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    calls.append(b)
        if d.get("type") == "user" and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    t = b.get("content")
                    t = t if isinstance(t, str) else json.dumps(t)
                    errors.append(t[:200].replace("\n", " "))
    return calls, errors


def main(jsonl, sdir=None):
    jsonl = Path(jsonl)
    sdir = Path(sdir) if sdir else jsonl.with_suffix("")
    all_rows = list(rows(jsonl))
    ver = next((d.get("version") for d in all_rows if d.get("version")), "?")
    cost = [d for d in all_rows if d.get("type") == "cost-state"]
    print(f"# Session {jsonl.name} · Claude Code {ver}")
    if cost:
        c = cost[-1]
        print(f"Total (cost-state): ${c.get('totalCostUSD', 0):.2f} · API time {c.get('totalAPIDuration', 0)/60000:.1f} min"
              f" · wall {c.get('totalDuration', 0)/60000:.1f} min")
        for model, mu in (c.get("modelUsage") or {}).items():
            print(f"  {model}: ${mu.get('costUSD', 0):.2f} · in {mu.get('inputTokens',0):,} · cache write "
                  f"{mu.get('cacheCreationInputTokens',0):,} · cache read {mu.get('cacheReadInputTokens',0):,} · out {mu.get('outputTokens',0):,}")
    else:
        print("No cost-state in the log — use /cost output and the token counts below.")
    efforts = collections.Counter(d.get("effort") for d in all_rows if d.get("type") == "assistant")
    req_models = collections.Counter(d.get("requestedModel") for d in all_rows if d.get("type") == "assistant")
    print(f"Requested models (main): {dict(req_models)} · effort: {dict(efforts)}")

    main_reqs = usage(jsonl)
    groups = [("MAIN", "orchestrator", main_reqs)]
    sub = sdir / "subagents"
    if sub.is_dir():
        for f in sorted(sub.glob("*.jsonl")):
            meta = {}
            mf = f.with_suffix(".meta.json")
            if mf.exists():
                meta = json.loads(mf.read_text(encoding="utf-8"))
            groups.append((meta.get("agentType", "?"), meta.get("description", f.stem), usage(f)))
    # weighted share of each model's cost
    per_model_w = collections.Counter()
    for _, _, reqs in groups:
        for r in reqs:
            per_model_w[r["model"]] += weight(r)
    model_cost = {m: mu.get("costUSD", 0) for m, mu in ((cost[-1].get("modelUsage") or {}).items() if cost else [])}
    print("\n## Per agent (cost = estimated share of its model's cost)")
    print(f"{'agent':<22} {'description':<34} {'model':<20} {'req':>4} {'max ctx':>8} {'est $':>7}  tokens")
    for typ, desc, reqs in groups:
        if not reqs:
            print(f"{typ:<22} {desc[:34]:<34} (no requests)"); continue
        models = collections.Counter(r["model"] for r in reqs)
        est = sum(weight(r) / per_model_w[r["model"]] * model_cost.get(r["model"], 0) for r in reqs if per_model_w[r["model"]])
        mctx = max(r["in"] + r["cw"] + r["cr"] for r in reqs)
        print(f"{typ:<22} {desc[:34]:<34} {','.join(models)[:20]:<20} {len(reqs):>4} {mctx:>8,} {est:>7.2f}  {fmt(summ(reqs))}")

    if sub.is_dir():
        print("\n## Per agent: tool calls and errors")
        for f in sorted(sub.glob("*.jsonl")):
            mf = f.with_suffix(".meta.json")
            desc = json.loads(mf.read_text(encoding="utf-8")).get("description", f.stem) if mf.exists() else f.stem
            calls, errs = tools(list(rows(f)))
            print(f"  {desc[:40]:<40} {dict(collections.Counter(b['name'] for b in calls))} · errors {len(errs)}")
            for e in errs[:5]:
                print(f"      ! {e}")

    print("\n## Main session: context per request")
    for i, r in enumerate(main_reqs, 1):
        print(f"  {i:>3} {r['ts'][11:19] if r['ts'] else ''} {r['model']}: ctx {r['in']+r['cw']+r['cr']:,} (write {r['cw']:,}) out {r['out']:,}")

    print("\n## Main session: tool calls")
    calls, errors = tools(all_rows)
    print(dict(collections.Counter(b["name"] for b in calls)))
    for b in calls:
        i = b.get("input") or {}
        if b["name"] == "Bash":
            print(f"  Bash: {i.get('command', '')[:160]!r}")
        elif b["name"] in ("Agent", "Task"):
            print(f"  {b['name']}: type={i.get('subagent_type')} model={i.get('model')} bg={i.get('run_in_background')} · {i.get('description', '')[:50]}")
        elif b["name"] in ("Read", "Write", "Edit"):
            print(f"  {b['name']}: {i.get('file_path', '')}")
        else:
            print(f"  {b['name']}: {json.dumps(i)[:120]}")
    print(f"\n## Tool errors in the main session: {len(errors)}")
    for e in errors:
        print(f"  - {e}")

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__); sys.exit(2)
    main(*sys.argv[1:])
