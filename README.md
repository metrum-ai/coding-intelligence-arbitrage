<!-- Copyright (c) 2026 Metrum AI, Inc. All rights reserved. -->
# Metrum AI · Coding Intelligence Arbitrage

A frozen coding-model preference package for pi, built by Metrum AI.

Frozen copy of the Metrum AI Coding Intelligence Arbitrage tracker, wired into pi so loaded agents receive coding-model preferences by capability per dollar. Built by Metrum AI. No runtime network calls.

```
metrum-arbitrage/
├── package.json                      # pi package manifest (Metrum AI)
├── data/tracker.json                 # raw snapshot, 44 models, 2026-11-07T22:24:47Z
├── data/policy.json                  # tiers the extension reads
├── extensions/arbitrage.ts           # per-turn prompt block + /arbitrage command
├── skills/intelligence-arbitrage/
│   ├── SKILL.md                      # ranked tiers + routing rules (loaded on demand)
│   └── reference.md                  # every model, every route
├── scripts/build_snapshot.py         # regenerate everything from a saved page
└── settings.snippet.json             # defaultModel + enabledModels in rank order
```

## Install

```bash
pi install git:github.com/metrum-ai/coding-intelligence-arbitrage@v2026.11.7
pi install ./coding-intelligence-arbitrage                # local clone instead
```

Optional: merge `settings.snippet.json` into `~/.pi/agent/settings.json` so the default model and Ctrl+P cycle follow the ranking. Check the ids against `pi --list-models`; provider prefixes depend on which providers you've configured.

Project-only instead of global: run `pi install -l git:github.com/metrum-ai/coding-intelligence-arbitrage@v2026.11.7 --approve` in a trusted project. The pinned Git tag installs without npm publication.

Git installs work directly; pi's documented gallery discovery uses npm packages carrying the `pi-package` keyword, so this Git-only release does not claim a gallery listing. See [pi packages documentation](https://pi.dev/docs/latest/packages).

## Use

```
/arbitrage              # all tiers
/arbitrage workhorse    # one tier
/arbitrage off          # stop injecting the block this session
/skill:intelligence-arbitrage
```

Want the skill only (no per-turn preference block)? Filter the package. Skill metadata still appears in pi's skill catalog:

```json
{ "packages": [{ "source": "git:github.com/metrum-ai/coding-intelligence-arbitrage@v2026.11.7", "extensions": [] }] }
```

## Refresh the snapshot

A published version is frozen at its snapshot date. Metrum AI republishes as the tracker updates; to roll your own:

Save the artifact page (browser → Save As, HTML only), then:

```bash
python3 scripts/build_snapshot.py --html ~/Downloads/coding-intelligence-arbitrage.html
python3 scripts/build_snapshot.py --blend 1:1 --floor 42 --cheap-floor 30   # retune tiers
```

The extension warns once the snapshot passes 30 days. Raising `--floor` moves models from Workhorse into Subtask: the workhorse tier shrinks and the subtask tier can grow.

## Routing and provider availability

The preference block and skill use the same rule: start with Workhorse for ordinary coding, use Subtask for mechanical chores, and use Frontier after a failed workhorse attempt or directly for architecture, concurrency or security work. A lock-free ring buffer qualifies for Frontier.

This package advises model selection; it does not switch models, create provider credentials, or pin inference backends. Select only models available through your configured providers. If the preferred model is unavailable, use the next available model in the same tier; report when no suitable model is available.

Generated selectors qualify the provider so a direct Anthropic preference cannot silently resolve to Bedrock. OpenRouter ids retain `:nitro`, the routing mode used for the snapshot. Nitro follows throughput and can change backend; the named host and its snapshot prices are historical observations, not a price or backend guarantee. If a selector is absent from `pi --list-models`, register it in `~/.pi/agent/models.json` before merging the settings snippet, for example:

```json
{
  "providers": {
    "openrouter": {
      "models": [
        { "id": "moonshotai/kimi-k3.1-pro:nitro" },
        { "id": "tencent/hy4:nitro" }
      ]
    }
  }
}
```

Authenticate OpenRouter separately using pi's supported credential setup. These entries use pi's built-in provider; they contain no credentials.

## Subagents

A one-off parent load (`pi -e ./metrum-arbitrage`) can influence the parent's child-model choice without propagating its prompt block into a fresh child. Configure this package in each child runtime's package settings, or pass it explicitly through your subagent runner's extension configuration. Verify the child receives it; package loading and provider authentication depend on the runner. Skill-only mode intentionally omits the preference block.

For `pi-subagents`, this tested project setting loads the preference extension in fresh children while preserving ambient discovery (replace the path with your installed package path):

```json
{
  "subagents": {
    "defaultSubagentOnlyExtensions": [
      "/absolute/path/metrum-arbitrage/extensions/arbitrage.ts"
    ]
  }
}
```

Put it in the trusted project's `.pi/settings.json`. Project settings must be approved in pi; use `--approve` for a trusted project in an automated test. A child-specific extension list can override this default, so inspect that agent's configuration too.

If `pi-background-tasks` rejects a valid Anthropic API key with an attribution/OAuth error, its ambient attribution feature is enabled. Its documented process-local `PI_BG_FEATURES=process,delegate,fusion,attested` setting disables that ambient feature for API-key testing. This is separate from this package; no global setting needs to change.

## Older pi builds

pi moved from `@mariozechner/pi-coding-agent` to `@earendil-works/pi-coding-agent`. On the old name, change the one import in `extensions/arbitrage.ts`.

---
Copyright (c) 2026 Metrum AI, Inc. All rights reserved.
