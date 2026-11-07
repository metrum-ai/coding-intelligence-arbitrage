#!/usr/bin/env python3
# Copyright (c) 2026 Metrum AI, Inc. All rights reserved.
# Metrum AI — Intelligence Arbitrage snapshot builder for pi coding agents.
#
# Turns a frozen copy of the Coding Intelligence Arbitrage tracker into:
#   data/tracker.json                         raw rows (only when --html is given)
#   data/policy.json                          tiered preference order read by the pi extension
#   skills/intelligence-arbitrage/SKILL.md    on-demand skill for the agent
#   skills/intelligence-arbitrage/reference.md  every model, every route
#   settings.snippet.json                     enabledModels/defaultModel for ~/.pi/agent/settings.json
#
# Nothing here touches the network. Refresh = save the artifact page, rerun with --html.
#
#   python3 scripts/build_snapshot.py                       # rebuild from data/tracker.json
#   python3 scripts/build_snapshot.py --html saved.html     # re-extract from a saved artifact page
#   python3 scripts/build_snapshot.py --blend 1:1 --floor 42 --cheap-floor 30
#
# Metrum AI: ranking math mirrors the tracker page exactly:
#   blended = (a*in + b*out)/(a+b); arbitrage = cheapest_route_blended / coding_score (lower wins)

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = "Copyright (c) 2026 Metrum AI, Inc. All rights reserved."


def extract_from_html(html_path: Path) -> dict:
    """Metrum AI: pull `const DATA = {...};` out of the saved tracker page."""
    src = html_path.read_text(encoding="utf-8")
    m = re.search(r"const DATA = (\{.*?\});\n", src, re.S)
    if not m:
        sys.exit(f"Metrum AI: no `const DATA = ...` block found in {html_path}")
    return json.loads(m.group(1))


def blended(route: dict, a: int, b: int) -> float:
    return (a * route["in"] + b * route["out"]) / (a + b)


def rank(rows: list, a: int, b: int) -> list:
    """Metrum AI: one entry per model with a score and at least one priced route."""
    out = []
    for m in rows:
        if m.get("score") is None or not m.get("routes"):
            continue
        routes = sorted(m["routes"], key=lambda r: (blended(r, a, b), not bool(r.get("model_id"))))
        best = routes[0]
        bl = blended(best, a, b)
        out.append({
            "model": m["model"],
            "vendor": m["vendor"],
            "open_weights": m["open_weights"],
            "effort": m.get("variant"),
            "score": m["score"],
            "terminal_bench": m.get("tb4"),
            "agent_index": m.get("agent_idx"),
            "aa_cost_task": m.get("aa_cost_task"),
            "route": best["route"],
            "route_kind": best["kind"],
            "model_id": best.get("model_id"),
            "in": best["in"], "out": best["out"], "cached": best.get("cached"),
            "blended": round(bl, 4),
            "usd_per_point": round(bl / m["score"], 5),
            "direct_ids": [r["model_id"] for r in m["routes"] if r["kind"] == "direct" and r.get("model_id")],
            "all_routes": [{**r, "blended": round(blended(r, a, b), 4)} for r in routes],
        })
    return sorted(out, key=lambda x: (x["usd_per_point"], -x["score"]))


def pi_pattern(e: dict) -> str:
    """Metrum AI: pi model pattern for the cheapest route (OpenRouter slug, or the direct provider id)."""
    if e["route_kind"] == "openrouter" and e["model_id"]:
        return "openrouter/" + e["model_id"]
    model_id = e["model_id"] or (e["direct_ids"] or [e["model"]])[0]
    providers = {
        "OpenAI": "openai", "Anthropic": "anthropic", "Fireworks": "fireworks",
        "Google Gemini API": "google", "Groq": "groq", "xAI": "xai",
        "MiniMax": "minimax",
    }
    provider = providers.get(e["route"])
    return f"{provider}/{model_id}" if provider else model_id


def money(v):
    return "—" if v is None else f"${v:g}"


def table(entries: list, start: int = 1) -> str:
    lines = ["| # | Model | Score | $/M blended | $/pt | Cheapest route | id |",
             "|---|---|---|---|---|---|---|"]
    for i, e in enumerate(entries, start):
        ow = " (open)" if e["open_weights"] else ""
        lines.append(f"| {i} | {e['model']}{ow} | {e['score']:.1f} | {e['blended']:.3f} | "
                     f"{e['usd_per_point']:.4f} | {e['route']} | `{pi_pattern(e)}` |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Metrum AI arbitrage snapshot builder")
    ap.add_argument("--html", type=Path, help="saved tracker page to re-extract from")
    ap.add_argument("--blend", default="3:1", help="input:output token blend (tracker default 3:1)")
    ap.add_argument("--floor", type=float, default=40.0, help="min coding score for the workhorse tier")
    ap.add_argument("--cheap-floor", type=float, default=30.0, help="min coding score for the subtask tier")
    args = ap.parse_args()

    data_path = ROOT / "data" / "tracker.json"
    if args.html:
        data = extract_from_html(args.html)
        data_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    else:
        data = json.loads(data_path.read_text(encoding="utf-8"))

    a, b = (int(x) for x in args.blend.split(":"))
    ranked = rank(data["rows"], a, b)
    workhorse = [e for e in ranked if e["score"] >= args.floor]
    subtask = [e for e in ranked if args.cheap_floor <= e["score"] < args.floor]
    frontier = sorted(workhorse, key=lambda e: -e["score"])[:3]
    unpriced = [m["model"] for m in data["rows"] if m.get("score") is not None and not m.get("routes")]
    snap = data["generated"]

    # Metrum AI: policy.json is the contract with extensions/arbitrage.ts
    policy = {
        "_copyright": HEADER,
        "source": "https://claude.ai/artifact/LyvGQHoze7Y4yex4FWWbEN",
        "snapshot": snap, "blend": args.blend,
        "floors": {"workhorse": args.floor, "subtask": args.cheap_floor},
        "tiers": {
            "workhorse": [{**e, "pi": pi_pattern(e)} for e in workhorse],
            "subtask": [{**e, "pi": pi_pattern(e)} for e in subtask],
            "frontier": [{**e, "pi": pi_pattern(e)} for e in frontier],
        },
        "unpriced": unpriced,
    }
    for tier in policy["tiers"].values():
        for e in tier:
            e.pop("all_routes", None)
    (ROOT / "data" / "policy.json").write_text(json.dumps(policy, indent=1), encoding="utf-8")

    w0, s0, f0 = workhorse[0], (subtask[0] if subtask else None), frontier[0]
    skill = f"""---
name: intelligence-arbitrage
description: Metrum AI coding-model preference order (capability per dollar). Use when choosing, recommending, routing or switching a model for coding work, delegating to subagents, configuring model settings, or estimating LLM cost for a coding task.
---
<!-- {HEADER} Generated by Metrum AI scripts/build_snapshot.py. Do not hand-edit. -->

# Intelligence Arbitrage (Metrum AI)

Frozen snapshot `{snap}` of the Metrum AI Coding Intelligence Arbitrage tracker.
Metric: cheapest blended $/1M tokens ({args.blend} input:output) divided by Artificial Analysis coding score. Lower is better.
Do not fetch the live tracker; this snapshot is the source of truth until it is rebuilt.

## Routing rules

1. Default coding model: the top of **Workhorse** (score ≥ {args.floor:g}). Right now `{pi_pattern(w0)}` ({w0['model']}, {w0['score']:.1f} pts, ${w0['usd_per_point']:.4f}/pt).
2. Mechanical subtasks (grep-and-summarise, renames, test scaffolds, commit messages, log triage): **Subtask** tier{f", starting with `{pi_pattern(s0)}` ({s0['model']})" if s0 else ""}.
3. Use **Frontier** after a workhorse attempt fails, or directly for architecture, concurrency or security work. Top pick: `{pi_pattern(f0)}` ({f0['model']}, {f0['score']:.1f}).
4. Never pick a model below {args.cheap_floor:g} for code that ships, however cheap.
5. When two picks sit within 10% on $/pt, prefer the higher score.
6. Prices move. Treat anything older than 30 days as stale and say so when recommending.
7. OpenRouter ids retain `:nitro` to request the routing mode used by this snapshot. Nitro selects by throughput; it does not pin the named backend or guarantee the snapshot price. Configure missing ids in pi before selecting them (see README.md).
8. Choose only available, configured models. If a preferred model is unavailable, try the next in the same tier; report if none are available.

## Workhorse (score ≥ {args.floor:g}), by $/pt

{table(workhorse)}

## Subtask ({args.cheap_floor:g} ≤ score < {args.floor:g}), by $/pt

{table(subtask) if subtask else "_none at this floor_"}

## Frontier (highest raw score)

{table(frontier)}

Scored but no priced route in the snapshot: {", ".join(unpriced) or "none"}.

Every model and every route (direct + OpenRouter :nitro, cached prices, notes): [reference.md](reference.md). Raw rows: `../../data/tracker.json`.
"""
    (ROOT / "skills" / "intelligence-arbitrage" / "SKILL.md").write_text(skill, encoding="utf-8")

    # Metrum AI: full reference, loaded only when the agent needs route-level detail
    ref = [f"<!-- {HEADER} Generated by Metrum AI scripts/build_snapshot.py. -->",
           f"# Full arbitrage table — snapshot {snap}, blend {args.blend}", "",
           table(ranked), "", "## Routes per model", ""]
    ref.extend(["The ranked table includes scored, priced models only. The sections below include every raw model and every route; unscored or unpriced models remain outside the routing tiers.", ""])
    for m in data["rows"]:
        score = "unscored" if m.get("score") is None else str(m["score"])
        ref.append(f"### {m['model']} — {m['vendor']}, score {score}, effort {m.get('variant') or 'default'}")
        routes = sorted(m.get("routes") or [], key=lambda r: blended(r, a, b))
        if routes:
            ref.append("| Route | id | in | out | cached | blended | notes |")
            ref.append("|---|---|---|---|---|---|---|")
            for r in routes:
                notes = (r.get("notes") or "").replace("|", "/")
                ref.append(f"| {r['route']} | `{r.get('model_id') or '—'}` | {money(r['in'])} | {money(r['out'])} | "
                           f"{money(r.get('cached'))} | {blended(r, a, b):.3f} | {notes} |")
        else:
            ref.append("No priced route in this snapshot.")
        for error in m.get("route_errors") or []:
            ref.append(f"Route lookup note: {error}")
        ref.append("")
    (ROOT / "skills" / "intelligence-arbitrage" / "reference.md").write_text("\n".join(ref), encoding="utf-8")

    # Metrum AI: settings snippet — merge by hand into ~/.pi/agent/settings.json
    provider = pi_pattern(w0).split("/", 1)[0]
    snippet = {
        "_comment": f"{HEADER} Metrum AI arbitrage order, snapshot {snap}. Merge into ~/.pi/agent/settings.json.",
        "defaultProvider": provider,
        "defaultModel": pi_pattern(w0),
        "enabledModels": [pi_pattern(e) for e in workhorse + subtask[:3]],
        "packages": ["git:github.com/metrum-ai/coding-intelligence-arbitrage@v2026.11.7"],
    }
    (ROOT / "settings.snippet.json").write_text(json.dumps(snippet, indent=2), encoding="utf-8")

    print(f"Metrum AI: snapshot {snap} | workhorse {len(workhorse)} | subtask {len(subtask)} | "
          f"default {pi_pattern(w0)}")


if __name__ == "__main__":
    main()
