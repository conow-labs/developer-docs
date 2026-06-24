# Home AI Dispatch API Reference (end-user)

Gateway: the CLI auto-derives the base URL from the `sk-` key prefix
(`sk-AY` → `openapi.tuyacn.com`, `sk-AZ` → `openapi.tuyaus.com`, etc;
full table in [`conow-energy/SKILL.md`](../../conow-energy/SKILL.md)).
Set `CONOW_BASE_URL` only if your deployment provides a dedicated gateway URL.
Auth: `Authorization: Bearer <sk-...>`

## Endpoint contracts

The contracts below describe the user-facing end-user dispatch flow supported
by this skill. `conow-dispatch` **intentionally does not** surface enabling
dispatch; direct users to the Conow App's AI Dispatch / Savings Mode toggle.
Note: a save/enable endpoint *does* exist on the backend, but leaving it out is
a deliberate scope/policy choice, not an API gap.

| Capability | Status | Method + Path | Field | CLI |
|-----------|--------|---------------|-------|-----|
| Status + display payload (single reliable read entry) | Live | `GET /v1.0/end-user/energy/homes/dispatch?home_id=<HID>` | `home_id` | `query` / `list` |
| Enabled boolean check (lightweight) | Live | `GET /v1.0/end-user/energy/homes/dispatch/run-status` (`home_id` in body) | `home_id` | — |
| Disable | Live | `POST /v1.0/end-user/energy/homes/dispatch/disable` | `home_id` | `disable` |
| Enable / save | Live (out of scope) | — (intentionally not surfaced) | `home_id` | — (use Conow App) |

> **`run-status` is a distinct endpoint, not an alias.**
> `GET .../dispatch/run-status` (with `home_id` in the body) returns a single
> boolean enabled/disabled result in the standard gateway envelope
> (`success`/`result`/`code`) — a cheap on/off check. It was previously
> mis-described as "a legacy alias consolidated into /dispatch"; that is wrong.
> The full `/dispatch` read is the richer payload, but `run-status` is a cheaper
> primitive a future `list` scan could use when only the on/off flag is needed.

> **Naming note**: older documentation refers to the request field as
> `groupId`, but the end-user gateway uses **`home_id`** (snake_case) — that is
> the correct field; the older `groupId` naming is not accepted on the request
> side. Response payloads may still contain a `groupId` field; under the
> end-user contract `groupId == home_id` on the response side.

## Reading state from `/dispatch`

After a successful `GET /v1.0/end-user/energy/homes/dispatch?home_id=<HID>`,
inspect `result`:

Prefer the explicit top-level flags over the `savePercent` heuristic:

- `allDeviceUnable` — `true` ⇒ no device can be dispatched (treat as not running).
- `predictable` — whether the home has enough data for the AI to plan.

| Case | Fields |
|------|--------|
| **Disabled / not running** | no `deviceDispatchList` and `savePercent:"0"`. ⚠️ This shape (`{"savePercent":"0","predictable":true,"allDeviceUnable":false}`) is **also** what an unknown/unauthorized `home_id` returns — distinguish a real disabled home by checking `home_id` membership in `/homes/all`, not by `savePercent` alone. |
| **Idle (configured but not acting)** | Dispatch is on but `allDeviceUnable:true`, or `deviceDispatchList[]` present with 0 dispatched devices (e.g. all devices knocked out by `cmdConflict`). The `list` command labels this `idle` — it is **not** actively saving; report it distinctly from enabled. |
| **Enabled (actively dispatching)** | `deviceDispatchList[]` with ≥1 dispatched device and `allDeviceUnable:false` (per-device `hasDispatch` / `scheduleList` / `statusList`), `groupId`, plus optional `reasonList`, `loadPowerList`, `pvPowerList`, `socList`, `importTariffList`, `homeBaseLoadPowerList` time series. (Edge case: an empty `deviceDispatchList` with a positive `savePercent` is rare but the `list` command conservatively classifies it as enabled.) |

Typical `deviceDispatchList[i]` fields:

- `deviceId` / `deviceName` / `deviceType`
- `online` — whether the device is reachable (used for both display and dispatchability)
- `hasDispatch` — whether this device is covered by the current plan
- `cmdConflict` — `1` ⇒ the device exited dispatch due to a command conflict (e.g. a manual override). Surface this when present.
- `energyDeviceProtocol` — the device's energy protocol.
- `scheduleList[]` — upcoming actions (e.g. `switch=true` at a given time)
- `statusList[]` — current / scheduled status entries

### Wire casing (do not "fix" the parser)

The backend Java DTOs carry a field-name-convert annotation implying snake_case
responses, but **on this live gateway the annotation does NOT take effect**: the
gateway returns **camelCase** response fields (`savePercent`,
`deviceDispatchList`, `groupId`, `reasonList`, `homeBaseLoadPowerList`, ...),
confirmed live. The CLI's camelCase response parsing is therefore **correct** —
do not rewrite it to snake_case (request fields like `home_id` remain snake_case).

## Batch scan

The CLI's `list` subcommand (aliases `batch` / `summary`) wraps
"list all visible homes → query `/dispatch` in parallel" into a single
call, replacing the older "ask the user to pick a home first" flow.
Each home is summarized with `state`, `save_percent`, `devices`, and
`devices_dispatched`.

`state` is **three-valued** (plus `error`):

- `enabled` — dispatch on **and** acting: ≥1 dispatched device and `allDeviceUnable=false`. The only state genuinely saving right now.
- `idle` — dispatch configured but not acting: `allDeviceUnable=true` or 0 dispatched devices. **Not** actively saving — do not report it as enabled.
- `disabled` — dispatch off.
- `error` — the per-home `/dispatch` read failed.

The text summary line is `N enabled, N idle, N disabled, N errors`, and
the JSON summary carries matching `enabled` / `idle` / `disabled` / `errors`
counts. The text **Idle** section flags why a home is not acting, e.g.
`[ALL DEVICES UNABLE, n cmd conflict(s)]`. `query` / `status` are aliases,
as are `list` / `batch` / `summary`; `query` accepts and ignores `--output`.

## Error codes

These are **platform envelope codes (observed empirically), not part of the
dispatch contract** — the dispatch backend declares no error codes for these
paths, and no live probe triggered them. Treat the table as a best-effort guide
to the shared Tuya/Conow gateway envelope, not an authoritative dispatch spec.
A gateway business error arrives as HTTP 200 with `success:false` plus a numeric
`code`; the CLI exits non-zero in that case and prints the raw `code`/`msg`.

| Code | Meaning (envelope) | Typical cause |
|------|--------------------|---------------|
| `1106` | Permission | The current key has no access to that home or capability (check the home is bound to this account and the sk- key region matches its data center) |
| `1108` | URI path invalid | Capability unavailable on this gateway |
| `1109` | Param missing | Required field missing |
| `1110` | Illegal param | Field name/value rejected (the gateway expects `home_id`) |
