---
name: conow-dispatch
description: Conow home-level AI energy dispatch (savings mode) end-user skill. Use this when the user asks about home dispatch status, the AI schedule plan, savings-mode coverage / `savePercent`, which homes are running dispatch, optimization plan preview, or wants to disable dispatch on a home. Read access is via `query` / `list`; the only supported write operation is `disable`. This skill intentionally does not surface enabling/save — direct users to enable dispatch from the Conow App. Do NOT use this skill for home-level energy aggregation (use `conow-energy`) or per-device control (use `conow-device`). Requires CONOW_API_KEY.
metadata: { "openclaw": { "version": "1.0.0", "emoji": "🤖", "requires": { "env": ["CONOW_API_KEY"], "pip": [] }, "primaryEnv": "CONOW_API_KEY" } }
---

# Conow Home AI Dispatch Skill

This skill exposes the home-level AI energy-dispatch end-user APIs (HEMS savings mode). It supports:

- Reading the dispatch status / schedule for one home or all visible homes.
- Disabling dispatch on a specific home.

### Dispatch status is three-state

A home is not just on/off. The `list` / `query` commands classify each home into one of three states — **report them distinctly, and never describe an idle home as actively saving:**

| State | Meaning | How it is detected |
|-------|---------|--------------------|
| **enabled** | Dispatch is on **and** actively acting — at least one device is currently dispatching and the home is not `allDeviceUnable`. This is the only state that is genuinely saving right now. |  `deviceDispatchList` has ≥1 dispatched device AND `allDeviceUnable=false` |
| **idle** | Dispatch is configured/on but **not currently acting** — `allDeviceUnable=true`, or 0 devices are dispatched. The home is **NOT actively saving**; do not quote it as if it were. Common causes: all devices unable, or a command conflict knocked devices out of the plan. | `allDeviceUnable=true`, or 0 dispatched devices |
| **disabled** | Dispatch is off. | not configured / disabled |

This skill **intentionally does not surface enabling** dispatch. A save/enable endpoint *does* exist on the backend, but enabling is a deliberate out-of-scope policy choice here — not an API gap. If the user asks to turn dispatch on, direct them to the Conow App's AI Dispatch / Savings Mode toggle on that home.

## Basic Information

- **Authentication**: Via Header `Authorization: Bearer {Api-key}`
- **Credentials**: Read from environment variable `CONOW_API_KEY`. Base URL is auto-detected from the API key prefix (same mapping as `conow-energy`). Override with `CONOW_BASE_URL` if needed.
- **API Reference**: See `references/dispatch_reference.md`
- **Python CLI**: See `scripts/conow_dispatch_cli.py`

## Environment Variable Configuration

```bash
export CONOW_API_KEY="your-conow-api-key"
# CONOW_BASE_URL is optional — auto-detected from the sk- key prefix.
# Set it only if your deployment provides a dedicated gateway URL, e.g.:
# export CONOW_BASE_URL="https://openapi.tuyaeu.com"
```

| Env var          | Flag          | Purpose                                               |
|------------------|---------------|-------------------------------------------------------|
| `CONOW_API_KEY`  | `--api-key`   | Required. Bearer token starting with `sk-`.           |
| `CONOW_BASE_URL` | `--base-url`  | Override gateway URL.                                 |
| `CONOW_HOME_ID`  | `--home-id`   | Optional default `home_id` for single-home commands.  |

The skill will not load if `CONOW_API_KEY` is missing. Never echo the raw key back to the user.

## Routing Boundaries

| Scope | Skill |
|-------|-------|
| Home consumption / generation, indicator aggregate / trend | `conow-energy` |
| Single device control or model query | `conow-device` |
| Home AI dispatch: schedule, status, disable | `conow-dispatch` (this skill) |

Optimization-effect prompts often look similar. Use these rules:

- "How is AI dispatch doing this month?" / "Is savings mode working?" / "Walk me through today's plan" → use `list` / `query` here. Quote `savePercent`, the per-device plan, and reasons.
- "How much did optimization save me this week (in money)?" / "What would I have spent without optimization?" → money / unoptimized baseline belongs to `conow-energy`'s impact reporting. Do not pretend `savePercent` equals saved money.
- "Why is this month's bill so high?" / "Which device used the most power?" → energy analysis, use `conow-energy`.

The same routing applies regardless of language. Reply in the user's language; do not translate `home_id`, `savePercent`, `deviceDispatchList` field names, or error codes.

## Usage

**Always prefer Method 1 (Command Line)**.

### Method 1: Via Command Line (Recommended)

```bash
python3 {baseDir}/scripts/conow_dispatch_cli.py <command> [params...]
# Examples:
python3 {baseDir}/scripts/conow_dispatch_cli.py list
python3 {baseDir}/scripts/conow_dispatch_cli.py list --name "My Home" --output json
python3 {baseDir}/scripts/conow_dispatch_cli.py query --home-id <HOME>
python3 {baseDir}/scripts/conow_dispatch_cli.py disable --home-id <HOME>
```

Use `python3 {baseDir}/scripts/conow_dispatch_cli.py --help` for the full command list.

## Feature Overview

| Capability | Command | Endpoint | Mode |
|------------|---------|----------|------|
| Scan all visible homes for dispatch status | `list` (aliases `batch` / `summary`) | `/v1.0/end-user/energy/homes/dispatch` (per home) | Read |
| Full dispatch payload for one home | `query` (alias `status`) | `/v1.0/end-user/energy/homes/dispatch` | Read |
| Disable AI dispatch on a home | `disable` | `/v1.0/end-user/energy/homes/dispatch/disable` | **Write** |

> **Aliases:** `list`, `batch`, and `summary` are the same command; `query` and `status` are the same command. `query` also accepts (and ignores) `--output` for symmetry with `list`.

> **Enabling dispatch (`save`) is intentionally out of scope for this skill.** The API declares a save endpoint, but this skill deliberately does not surface it. Direct the user to the Conow App's AI Dispatch / Savings Mode toggle on that home. Do not call any "save" endpoint from this skill.

## Core Workflows

### Workflow 1: Default — "How is dispatch looking?"

When the user asks about dispatch status without specifying a home (e.g. "Which homes are in dispatch?", "Is savings mode working?", "Show today's AI schedule"), the first action is `list`, which scans every home visible to the key:

```bash
python3 {baseDir}/scripts/conow_dispatch_cli.py list
```

Example output (live shape; home_ids genericized):

```
Scanned 9 homes: 1 enabled, 1 idle, 7 disabled, 0 errors.

Enabled (actively dispatching):
   <HOME_ID>  Home A   savePercent=5  devices=3 (1 dispatched)

Idle (1) — dispatch on but not currently acting:
   <HOME_ID>  Home B   savePercent=0  devices=1 (0 dispatched)  [ALL DEVICES UNABLE, 1 cmd conflict(s)]

Disabled (7):
   <HOME_ID>  Home C
   <HOME_ID>  Home D
   ...
```

The summary line is always `N enabled, N idle, N disabled, N errors`, and the JSON output (`--output json`) carries matching `enabled` / `idle` / `disabled` / `errors` counts plus a per-home `state` of `enabled` / `idle` / `disabled` / `error`. The **Idle** section annotates each home with the reason it is not acting, e.g. `[ALL DEVICES UNABLE, n cmd conflict(s)]`.

When summarizing for the user:
- List the **enabled** homes (the ones actually saving) by name with `savePercent` and dispatched-device counts.
- Report **idle** homes separately and explicitly as "dispatch on but not currently saving" — do NOT lump them in with enabled, and do NOT quote their `savePercent` as realized savings.
- For disabled homes, show the count plus a few representative names — not all of them.
- Do not paste raw `home_id`s unless the user asks for them or you need to disambiguate.

Do not ask the user to pre-select a home, and do not require `CONOW_HOME_ID`. Move to single-home commands only when the user names a specific home or you can resolve it from context.

### Workflow 2: Inspect a Single Home

```bash
python3 {baseDir}/scripts/conow_dispatch_cli.py query --home-id <HOME>
```

Key fields in `result`:

- **State signals (prefer the explicit flags over the `savePercent` heuristic):** these are what map a home onto the three-state model (enabled / idle / disabled — see top of this file).
  - `allDeviceUnable` — `true` when no device can currently be dispatched. A configured home with `allDeviceUnable=true` is **idle**, not enabled — it is not currently saving.
  - `predictable` — whether the home has enough data for the AI to predict/plan.
  - A non-empty `deviceDispatchList[]` with ≥1 dispatched device (and `allDeviceUnable=false`) is the strongest **enabled** signal; configured-but-0-dispatched is **idle**. `savePercent` alone is unreliable: both a genuinely-disabled home and a freshly-enabled home can report `"0"` (see Important Notes about home membership).
- `savePercent` — expected savings percentage (string).
- `deviceDispatchList[]` — per device: `deviceId / deviceName / deviceType / online / hasDispatch / scheduleList / statusList`, plus:
  - `cmdConflict` — `1` means the device exited dispatch due to a command conflict (e.g. a manual override). Surface this when present.
  - `energyDeviceProtocol` — the device's energy protocol.
- `scheduleList[].actionList[]` — upcoming actions, e.g. `{"code": "switch", "value": "true"}` at a specific time.
- `reasonList[]` — human-readable dispatch reasons (e.g. `PRICE_MODERATE_GRID_PURCHASE`).
- `loadPowerList` / `pvPowerList` / `socList` / `importTariffList` / `homeBaseLoadPowerList` — time series (`homeBaseLoadPowerList` is the home's base/background load).

### Workflow 3: Disable Dispatch (Write)

`disable` is the only write operation in this skill. Before calling it:

1. Confirm the target home with the user by name **and** `home_id`.
2. Ask the user to confirm the action.

```bash
python3 {baseDir}/scripts/conow_dispatch_cli.py disable --home-id <HOME>
```

If the user wants to **enable** dispatch, do **not** attempt any "save" endpoint. A save endpoint exists, but this skill intentionally does not surface enabling. Direct the user to the AI Dispatch / Savings Mode toggle in the Conow App for that home. Optionally provide the `home_id` so they can locate it quickly.

### Workflow 4: Disambiguation

Stop and ask the user for confirmation only when:

1. The user named a specific home but it collides with another home of the same name — list both with their `home_id`s and ask the user to pick.
2. The user asked to **disable** dispatch — confirm the home before calling `disable`.
3. The user asked to **enable** dispatch — this skill intentionally does not surface enabling; direct them to the Conow App as above.
4. The `list` call itself fails (network, authentication, gateway change) — surface the error and stop.

## Mapping to Product Skills

If you are wiring this skill into a product-level surface:

- `preview_optimization_plan` → `query` (use `scheduleList` / `reasonList` / `loadPowerList` from `/dispatch`).
- `get_optimization_report`'s "is AI dispatch helping?" question → `query` / `list` (show `savePercent`, dispatched devices, plan, reasons). Money / unoptimized baseline goes to `conow-energy`; do not synthesize savings amounts here.
- `manage_optimization` → `disable` + `query` for status. Enabling is intentionally not in scope for this skill (a save endpoint exists, but is not surfaced here); route the user to the Conow App.

## Important Notes

1. **`save` (enable)** is intentionally not surfaced by this skill (the endpoint exists, but enabling is out of scope here). Always direct the user to the Conow App for enabling dispatch.
2. Status comes from the explicit `allDeviceUnable` / `predictable` flags and `deviceDispatchList` in the `query` payload — prefer those over the `savePercent` heuristic.
3. **`query` validates the `home_id` against `/homes/all` first.** An unknown or unauthorized `home_id` returns the same shape as a genuinely-disabled home (`success:true`, `savePercent:"0"`), so the CLI errors with "Home <id> not found under this account" (non-zero exit) instead of mislabeling it "disabled". Run `list` to see valid homes.
4. Never echo the raw `CONOW_API_KEY` in output or logs. (`CONOW_VERBOSE=1` prints a redacted request summary to stderr.)
5. For home-level energy aggregation use `conow-energy`. For per-device control use `conow-device`.

## Data Egress Statement

**This skill sends data to the Conow / Tuya Open Platform**:

| Data Type | Sent To | Purpose | Required |
|-----------|---------|---------|----------|
| Api-key | User-configured base_url (auto-detected from `sk-` prefix) | API authentication | Required |
| `home_id` | User-configured base_url | Dispatch status query and disable | Required |
| Disable command | User-configured base_url | Turn off AI dispatch on a specific home | Required for `disable` |

This skill performs a **write operation** when `disable` is invoked. Confirm the target home (by name and `home_id`) with the user before calling `disable`. Set `CONOW_BASE_URL` if you need to override the auto-detected gateway.
