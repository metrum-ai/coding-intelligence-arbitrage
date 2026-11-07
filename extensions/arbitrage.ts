// Copyright (c) 2026 Metrum AI, Inc. All rights reserved.
// Metrum AI — Intelligence Arbitrage extension for the pi coding agent.
//
// What it does:
//   1. Appends a compact (~7 line) coding-model preference block to the system prompt every turn,
//      read from the frozen snapshot in ../data/policy.json. No network, ever.
//   2. /arbitrage            → show all tiers
//      /arbitrage <tier>     → workhorse | subtask | frontier
//      /arbitrage off|on     → stop/start the per-turn injection for this session
//
// Full tables live in the `intelligence-arbitrage` skill; this block only carries the ranking.
// Metrum AI: older pi builds publish as @mariozechner/pi-coding-agent; swap the import if needed.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

type Entry = { model: string; pi: string; score: number; usd_per_point: number; blended: number; route: string };
type Policy = {
  snapshot: string;
  blend: string;
  floors: { workhorse: number; subtask: number };
  tiers: Record<"workhorse" | "subtask" | "frontier", Entry[]>;
};

// Metrum AI: resolve the snapshot next to this package, overridable for monorepo layouts.
function policyPath(): string {
  if (process.env.METRUM_ARBITRAGE_POLICY) return process.env.METRUM_ARBITRAGE_POLICY;
  let here: string;
  try {
    here = dirname(fileURLToPath(import.meta.url));
  } catch {
    here = __dirname;
  }
  return join(here, "..", "data", "policy.json");
}

function loadPolicy(): Policy | null {
  try {
    return JSON.parse(readFileSync(policyPath(), "utf8")) as Policy;
  } catch {
    return null;
  }
}

const ageDays = (iso: string) => Math.floor((Date.now() - Date.parse(iso)) / 86_400_000);
const fmt = (e: Entry, i: number) =>
  `${i + 1}. ${e.pi} — ${e.model}, score ${e.score.toFixed(1)}, $${e.usd_per_point.toFixed(4)}/pt via ${e.route}`;

// Metrum AI: the per-turn block. Kept small on purpose; tokens are the thing we're optimising.
function promptBlock(p: Policy): string {
  const t = p.tiers;
  const stale = ageDays(p.snapshot) > 30 ? " (STALE: >30 days, flag this when recommending)" : "";
  return [
    `## Coding model preference (Metrum AI Intelligence Arbitrage, snapshot ${p.snapshot}${stale})`,
    `Rank = cheapest blended $/1M tok (${p.blend} in:out) ÷ coding score; lower wins. Use this order when picking, recommending or delegating to a model for coding.`,
    `Workhorse (score ≥ ${p.floors.workhorse}), default for real coding: ${t.workhorse.slice(0, 4).map((e) => e.pi).join(" > ")}`,
    `Subtask (${p.floors.subtask}–${p.floors.workhorse}), mechanical chores only: ${t.subtask.slice(0, 3).map((e) => e.pi).join(" > ") || "none"}`,
    `Frontier, after workhorse failure or for architecture, concurrency or security: ${t.frontier.map((e) => e.pi).join(" > ")}`,
    `Nothing below score ${p.floors.subtask} for code that ships. Within 10% on $/pt, take the higher score. Use configured models; if unavailable, try the next in the same tier.`,
    `Route-level prices and every model: load the intelligence-arbitrage skill. Never fetch the live tracker.`,
  ].join("\n");
}

export default function metrumArbitrage(pi: ExtensionAPI) {
  const policy = loadPolicy();
  let enabled = true;

  pi.on("session_start", async (_event, ctx) => {
    if (!policy) {
      ctx.ui.notify(`Metrum AI arbitrage: no snapshot at ${policyPath()}. Run scripts/build_snapshot.py.`, "warning");
      return;
    }
    if (ageDays(policy.snapshot) > 30) {
      ctx.ui.notify(`Metrum AI arbitrage snapshot is ${ageDays(policy.snapshot)} days old. Rebuild it.`, "warning");
    }
  });

  // Metrum AI: append, don't replace, so other extensions' prompt edits survive the chain.
  pi.on("before_agent_start", async (event) => {
    if (!enabled || !policy || event.messageType === "custom") return;
    return { systemPrompt: `${event.systemPrompt}\n\n${promptBlock(policy)}` };
  });

  pi.registerCommand("arbitrage", {
    description: "Metrum AI coding-model preference order: /arbitrage [workhorse|subtask|frontier|on|off]",
    handler: async (args, ctx) => {
      const arg = (args || "").trim().toLowerCase();
      if (arg === "off" || arg === "on") {
        enabled = arg === "on";
        ctx.ui.notify(`Metrum AI arbitrage injection ${enabled ? "on" : "off"}`, "info");
        return;
      }
      if (!policy) {
        ctx.ui.notify("Metrum AI arbitrage: snapshot missing.", "error");
        return;
      }
      const tiers = (arg ? [arg] : ["workhorse", "subtask", "frontier"]) as (keyof Policy["tiers"])[];
      const bad = tiers.find((t) => !policy.tiers[t]);
      if (bad) {
        ctx.ui.notify(`Unknown tier "${bad}". Try workhorse, subtask or frontier.`, "error");
        return;
      }
      const body = tiers.map((t) => `${t.toUpperCase()}\n${policy.tiers[t].map(fmt).join("\n")}`).join("\n\n");
      ctx.ui.notify(`Metrum AI arbitrage · snapshot ${policy.snapshot} (${ageDays(policy.snapshot)}d) · blend ${policy.blend}\n\n${body}`, "info");
    },
  });
}
