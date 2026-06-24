# Energy Device Control: No-Card Confirm Flow (control-plan / control-confirm)

This file describes the confirm contract for controlling an energy device in a
**no-card-rendering** context. Control here is scoped to **string inverters only** — all-in-one
(一体机) devices are intentionally not controllable (their codes are not in the allowlist, so
`control-plan` returns no controllable properties); their read-only queries remain available.
Generic (non-energy) devices use `public-control` / `device-control` and are out of scope here.

## Why two steps

Conow's in-app AI assistant uses a "confirm card" for structural confirmation (the front end
holds the execution path, so the agent cannot bypass the user's click). The end-user CLI context
has no card — the agent holds both the recitation and the call, so wording-only constraints are
unreliable. We reproduce the same confirmation strength with a **client-side two-step gate +
`plan_hash` binding + a re-validation on confirm**, all over published end-user endpoints:

| Mechanism | Role |
|-----------|------|
| `control-plan` (read-only) | Capability discovery + read current values + local validation; emits a structured intent and `plan_hash`. **Never issues.** |
| `control-confirm` (the only write) | Re-validates, checks `--plan-hash` matches the current parameters, then POSTs. On mismatch it returns `PLAN_HASH_MISMATCH` and refuses. |
| `plan_hash` = sha256(dev_id + resolved energy_dev_id + normalized settings) | Binds "the change the user consented to" to "the change about to execute." Changing any parameter — or pointing at a different sub-device via `--energy-dev-id` — invalidates it. |
| Re-validation on confirm | Because the underlying `energy-issue` does **no** validation, `control-confirm` runs the allowlist + range/enum check a second time before writing. |

> ⚠️ **`energy-issue` is an unvalidated raw pipe.** It accepts any `code` (a live issue of a
> non-existent code still returns `success:true`), and the `type=setting` thing model exposes a
> large number of items, including dangerous / installer parameters (`reset` factory reset,
> `grid_*_threshold` grid-safety thresholds, `afci`, `insulation_detection`). **The skill's
> built-in allowlist + local validation is therefore the only safety gate** — only an allowlisted
> code with a legal value is issued by `control-confirm`. To add a controllable item, register it
> in the CLI's `ENERGY_CONTROL_ALLOWLIST`; **do not** bypass the gate via the low-level
> `energy-issue`.

There is **no** backend `controllable` / `control/issue` route and no alternate dual-channel
control design — those paths return `1108` on this gateway and are not used. The capability
set comes from `GET /energy/devices/model?type=setting` intersected with the built-in allowlist;
the write goes to `POST /energy/devices/issue`, the only published write route.

## How discovery works (client-side)

`control-plan`:

1. Resolves `energy_dev_id` (explicit `--energy-dev-id`, else the single topo candidate / the
   `inverter` under `1 inverter + collection_stick`).
2. Reads the device thing model via `GET /energy/devices/model?type=setting`.
3. Intersects the requested codes with the built-in **minimal** `ENERGY_CONTROL_ALLOWLIST`
   (allowlisted-but-absent-from-model codes simply do not appear; not-allowlisted codes go to
   `errors` as `NOT_CONTROLLABLE`).
4. Reads current values and validates the requested target locally against the model's
   range / enum.
5. Emits `items`, `errors`, and a `plan_hash` bound to `dev_id` + resolved `energy_dev_id` +
   settings, plus a `ready` flag.

## Standard flow

1. Parse the user's intent into properties (e.g. "switch the inverter to mode 1" →
   `{"inverter_work_mode_setting":"1"}`). `inverter_work_mode_setting` is an enum; the exact
   allowed values for a given model come from `energy-controllable` / `control-plan`.
2. `control-plan --dev-id X --properties '{...}'` → returns `items`, `errors`, `plan_hash`,
   `ready`.
3. **Recite** each item to the user from `items` and ask for confirmation:
   > I will set [device name / devId] [inverter_work_mode_setting 2 → 1 (allowed values from
   > control-plan)]. Device control is reversible. Confirm?
4. After **explicit consent**, run `control-confirm --dev-id X --properties '{...}'`
   (identical to step 2) `--plan-hash <plan_hash>` (and the same `--energy-dev-id` if you passed
   one).
5. Check the result: `issued:true` (underlying `success:true`) → tell the user "issued" and
   suggest a re-read. `issue` is fire-and-forget — accepted ≠ effective — so re-read after a few
   seconds with `energy-properties --codes <code>`.

## Plan output shape

Illustrative `control-plan --dev-id <INVERTER_DEV_ID> --properties '{"inverter_work_mode_setting":"2"}'`
(enum range / current value come from the live model — values below are placeholders):

```json
{
  "phase": "plan",
  "dev_id": "<INVERTER_DEV_ID>",
  "energy_dev_id": "<INVERTER_DEV_ID>",
  "items": [
    {
      "code": "inverter_work_mode_setting",
      "name": "工作模式",
      "channel": "energy",
      "from": "2",
      "to": "2",
      "unit": null,
      "enum": ["<from live model>"],
      "min": null,
      "max": null,
      "validation": null
    }
  ],
  "errors": [],
  "plan_hash": "720184…",
  "idempotency_key": "720184…",
  "ready": true,
  "next": "Recite each item (name / from→to / unit) and obtain explicit consent, then call control-confirm --plan-hash <plan_hash> with identical parameters (and the same --energy-dev-id)."
}
```

Field notes:

- `items[]`: one entry per requested allowlisted code. `from` = current value, `to` = requested
  value (both strings on the energy branch). `unit` / `enum` / `min` / `max` come from the model;
  `validation` is `null` when the value passes (otherwise a local validation error string).
- `errors[]`: requested codes that are not controllable (`NOT_CONTROLLABLE`) — e.g. not in the
  allowlist. Allowlisted-but-not-in-model codes simply do not appear in `items`.
- `idempotency_key` equals `plan_hash`.
- `ready` is `true` only when `errors` is empty and every `validation` passes.

> **`ready=false` → `plan_hash` is `null` and `control-plan` exits 1**, with a "fix and re-run"
> `next` message. Do **not** proceed to `control-confirm`: report the `errors` / `validation` to
> the user, correct the intent, and re-run `control-plan`. `ready=true` returns a `plan_hash` and
> exits 0.

## Error-code phrasing map (control-confirm result)

| code | meaning | what to tell the user |
|------|---------|------------------------|
| `DEVICE_OFFLINE` | device offline | The device is offline right now; can't issue — try later or check the network. |
| `DP_NOT_SUPPORTED` / `NOT_CONTROLLABLE` | property not controllable / not in allowlist | This property isn't available for AI control. |
| `PARAM_ILLEGAL` | out of range / illegal enum / missing param | The value is outside the allowed range — please re-pick. |
| `PERMISSION_ERROR` | unauthorized / not logged in | You don't have permission to operate this device. |
| `PLAN_HASH_MISMATCH` (CLI-local) | confirm params (or `--energy-dev-id`) differ from the plan | Parameters changed — re-confirm (re-run `control-plan` and recite). |
| `DUPLICATE_IGNORED` | idempotency hit (repeat issue) | This command was already submitted; no need to repeat. |
| `UPSTREAM_ERROR` | downstream issue failed | Issue failed — please retry shortly. |

> **Which codes come from where**: only `NOT_CONTROLLABLE`, `PLAN_HASH_MISMATCH` (CLI-local),
> `DP_NOT_SUPPORTED`, and `PARAM_ILLEGAL` are emitted by the client gate. `DEVICE_OFFLINE`,
> `PERMISSION_ERROR`, `DUPLICATE_IGNORED`, and `UPSTREAM_ERROR` are downstream signals that only
> appear inside `control-confirm`'s raw `response` payload — the CLI does **not** pre-check online
> state, so an offline device's issue is still accepted (`success:true`) and silently ineffective;
> always re-read with `energy-properties` after issuing (see SKILL.md Workflow 4 hard-rule 4).

## Hard rules (must follow)

- **No one-step write**: energy-device control must be `control-plan` → recite → user consent →
  `control-confirm`. Never call the low-level `energy-issue` (no validation, bypasses the
  allowlist).
- **Don't claim success falsely**: do not say "issued" before `control-confirm` returns
  `issued:true`.
- **Capabilities come from the plan, not your memory**: controllable codes / ranges / enums come
  from `control-plan` (model ∩ allowlist). Don't invent controllable items or hardcode DP lists.
  To extend control, register the code in `ENERGY_CONTROL_ALLOWLIST`.
- **`plan_hash` binds the sub-device too**: pass the same `--energy-dev-id` to `control-confirm`
  that you used in `control-plan`, or it trips `PLAN_HASH_MISMATCH`.
- Generic devices use `public-control`, but still confirm the target device and action with the
  user first.
