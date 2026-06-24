---
name: conow-device
description: Conow + Tuya generic device end-user skill. Single CLI auto-routes between Tuya generic device endpoints (`devices/all`, home device list, `detail` / `model` / `shadow issue`) and Conow energy-device endpoints (`topo` / `protocol` / `model` / `properties` / `alarms` / `indicators` / `issue`) using the `topo` and `protocol` probes. Use this skill when the user asks how many devices they have, wants to list devices in an account/home, names a specific device (e.g. "is my EV charger / inverter / heat pump / socket OK / online / alarming / charging?"), provides a `devId`, or wants device status, Thing Model, properties, alarms, indicators, or to control that device. Do NOT use it for home-level energy aggregation (use `conow-energy`) or AI dispatch plan/status/disable (use `conow-dispatch`): battery state-of-charge / charge-discharge / import-export questions WITHOUT a named device or `devId` are home-level — use `conow-energy`. Requires CONOW_API_KEY.
metadata: { "openclaw": { "version": "1.0.0", "emoji": "🔌", "requires": { "env": ["CONOW_API_KEY"], "pip": [] }, "primaryEnv": "CONOW_API_KEY" } }
---

# Conow Device Skill (Generic + Energy)

This skill exposes per-device end-user APIs through a single CLI. The same `sk-` Bearer token can address both Tuya generic devices and Conow energy devices; the CLI internally calls `GET /v1.0/end-user/energy/devices/topo` and `GET /v1.0/end-user/energy/devices/protocol` to decide which branch to use, so callers do not need to make that decision themselves.

## Basic Information

- **Authentication**: Via Header `Authorization: Bearer {Api-key}`
- **Credentials**: Read from environment variable `CONOW_API_KEY`. Base URL is auto-detected from the API key prefix. Override with `CONOW_BASE_URL` if needed.
- **API Reference**: See `references/device_routing.md`
- **Energy device control (confirm gate)**: See `references/device_control_confirm.md`
- **Python CLI**: See `scripts/conow_device_cli.py`

## Environment Variable Configuration

```bash
export CONOW_API_KEY="your-conow-api-key"
# CONOW_BASE_URL is optional — auto-detected from the sk- key prefix.
# Set it only if your deployment provides a dedicated gateway URL, e.g.:
# export CONOW_BASE_URL="https://openapi.tuyaeu.com"
```

| Env var          | Flag          | Purpose                                            |
|------------------|---------------|----------------------------------------------------|
| `CONOW_API_KEY`   | `--api-key`   | Required. Bearer token starting with `sk-`.                             |
| `CONOW_BASE_URL`  | `--base-url`  | Override gateway URL.                                                    |
| `CONOW_DEVICE_ID` | `--dev-id`    | Optional. Default devId for device commands (overridden by `--dev-id`).  |

The skill will not load if `CONOW_API_KEY` is missing. Never echo the raw key back to the user.

## Routing Boundaries

| Scope | Handling |
|-------|----------|
| Account/home device inventory, single device status, control, Thing Model, topology, protocol, alarms, device indicators | Use this skill |
| Home-level consumption, generation, indicator aggregate/trend, tariff, forecast, or AI dispatch schedule | Out of scope for this device skill |

Device-vs-home routing rules for ambiguous prompts:

| Prompt example | Default handling |
|----------------|------------------|
| "How much battery do I have left?" / "Is the battery charging or discharging?" (no `devId`) | Treat as home-level energy state and out of scope unless the user identifies a specific device. |
| "Is the EV charger working?" / "How much is the heat pump using?" (specific device or `devId` available) | Route here via `device-overview`. Without a `devId`, ask the user to identify the device, or downgrade to home-level aggregation. |
| "Does the inverter have any alarms?" / "Are there alarms on this device?" | Route here once a `devId` is available; query `energy-alarms` / `device-overview`. |
| "Are all my devices OK?" | The CLI CAN list/count the inventory (Workflow 0: `list-devices`), but it cannot fetch per-device health for every device in a single call. Enumerate the inventory first, then offer to check specific devices one at a time via `device-overview` — do not imply a one-shot full audit. |

The same routing applies regardless of language. Reply in the user's language; do not translate `devId`, `energyDevId`, codes, or error codes.

## Usage

**Always prefer Method 1 (Command Line)**. The CLI handles routing, authentication, and JSON serialization automatically.

### Method 1: Via Command Line (Recommended)

```bash
python3 {baseDir}/scripts/conow_device_cli.py <command> [params...]
# Examples:
python3 {baseDir}/scripts/conow_device_cli.py detect --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py device-overview --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py device-control --dev-id <DEV_ID> [params...]
python3 {baseDir}/scripts/conow_device_cli.py list-homes
python3 {baseDir}/scripts/conow_device_cli.py resolve-home --home-name "My Home"
python3 {baseDir}/scripts/conow_device_cli.py list-devices --summary-only
python3 {baseDir}/scripts/conow_device_cli.py list-devices --home-id <HOME_ID> --summary-only

# Force a branch (override auto-detection)
python3 {baseDir}/scripts/conow_device_cli.py device-overview --dev-id <DEV_ID> --force-route energy
python3 {baseDir}/scripts/conow_device_cli.py device-overview --dev-id <DEV_ID> --force-route public

# Generic Tuya device endpoints (always public branch)
python3 {baseDir}/scripts/conow_device_cli.py public-detail --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py public-model  --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py public-control --dev-id <DEV_ID> \
  --properties '{"switch_led": true}'

# Energy device endpoints (always energy branch)
python3 {baseDir}/scripts/conow_device_cli.py energy-topo       --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-protocol   --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-model      --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-properties --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-alarms     --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-indicators --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-issue \
  --dev-id <DEV_ID> --energy-dev-id <ENERGY_DEV_ID> --setting '{"...": "..."}'

# Energy device control — inverter only, two-step confirm gate (see Workflow 4)
python3 {baseDir}/scripts/conow_device_cli.py energy-controllable --dev-id <DEV_ID>
# inverter_work_mode_setting is an enum; the exact range for a given model comes from
# energy-controllable. Use the controllable codes/values it returns in your own runs.
python3 {baseDir}/scripts/conow_device_cli.py control-plan \
  --dev-id <DEV_ID> --properties '{"inverter_work_mode_setting":"1"}'
python3 {baseDir}/scripts/conow_device_cli.py control-confirm \
  --dev-id <DEV_ID> --properties '{"inverter_work_mode_setting":"1"}' --plan-hash <PLAN_HASH>
```

Use `python3 {baseDir}/scripts/conow_device_cli.py --help` for the full command list.

## Feature Overview

| Module | Capabilities | Endpoints |
|--------|-------------|-----------|
| Auto-routing detection | Probe `topo` + `protocol` to classify a device as energy or generic | `/v1.0/end-user/energy/devices/topo`, `/v1.0/end-user/energy/devices/protocol` |
| Home discovery | List homes and resolve a numeric `home_id` by name | `/v1.0/end-user/homes/all` |
| Generic device — list | Account-level all devices, home-level devices | `/v1.0/end-user/devices/all`, `/v1.0/end-user/homes/{home_id}/devices` |
| Generic device — query | Device detail (online state, current properties), Thing Model | `/v1.0/end-user/devices/{device_id}/detail`, `/v1.0/end-user/devices/{device_id}/model` |
| Generic device — control | Issue properties via shadow | `POST /v1.0/end-user/devices/{device_id}/shadow/properties/issue` |
| Energy device — query | Topology, protocol, model, current properties, alarms, indicators (latest + time series) | `/v1.0/end-user/energy/devices/topo|protocol|model|properties|alarms|indicators|indicators/sdata` |
| Energy device — control (low-level) | Raw setting issuance — **no validation**, not for user-driven control | `POST /v1.0/end-user/energy/devices/issue` |
| Energy device — AI control (two-step gate, **inverter only**) | Client-side controllable discovery + local validation + confirm issue | `GET /energy/devices/model?type=setting` (∩ skill allowlist) → `POST /energy/devices/issue` |

> ✅ **AI control is implemented client-side over published end-user endpoints — no new backend interface, and is scoped to string inverters only.** `control-plan`/`control-confirm`/`energy-controllable` discover capabilities from `energy-model (type=setting)` intersected with the skill's built-in **minimal allowlist** (inverter codes only — `inverter_work_mode_setting` / `backup_enable` / `forced_off_grid` / `anti_reflux` / `inverter_switch`), validate values locally, and write via the published `energy-issue`. The unpublished `controllable` / `control/issue` routes (which return `1108` on this gateway) are **not** used. See Workflow 4 for the safety rationale (`energy-issue` is an unvalidated pipe; the skill is the gate). All-in-one (一体机) devices are intentionally **not** controllable here — `control-plan` returns no controllable properties for them — though their read-only queries (status/alarms/indicators) remain available.

If a device capability is unavailable on the current gateway, use `device-overview` to return the supported branch and explain the limitation to the user.

## Core Workflows

### Workflow 0: Count or List Devices

For "how many devices do I have?", "list my devices", or "devices in this home", use `list-devices` before falling back to per-device APIs.

```bash
# Account-level inventory
python3 {baseDir}/scripts/conow_device_cli.py list-devices --summary-only

# Home-level inventory by home name
python3 {baseDir}/scripts/conow_device_cli.py resolve-home --home-name "My Home"
python3 {baseDir}/scripts/conow_device_cli.py list-devices --home-id <HOME_ID> --summary-only
```

Notes:

- Account-level inventory uses `/v1.0/end-user/devices/all`.
- Home-level inventory uses `/v1.0/end-user/homes/{home_id}/devices`.
- If the user gives a home name instead of `home_id`, run `resolve-home --home-name ...` first. If several candidates are returned, ask the user to choose by name.
- Do not use `/v1.0/end-user/devices` or `/v1.0/end-user/devices/list` for inventory on this gateway; they may return `1108 uri path invalid`.
- For totals across homes, prefer account-level `list-devices --summary-only`, then optionally cross-check by summing home-level unique device IDs if the answer is surprising.

### Workflow 1: Identify the Device

1. Confirm the user has provided a `devId`, or that one can be resolved from context. If neither is available, ask the user for the device ID or name.
2. Run `detect` to inspect the auto-classification:

```bash
python3 {baseDir}/scripts/conow_device_cli.py detect --dev-id <DEV_ID>
```

`detect` returns `is_energy_device` plus the relevant routing signals.

### Workflow 2: Device Overview

`device-overview` automatically branches based on detection:

- Energy branch — combines `topo` + `protocol` + `indicators` + `properties` (current values). It does **not** include alarms; use `energy-alarms` separately for those.
- Generic branch — returns `device_detail`.

```bash
python3 {baseDir}/scripts/conow_device_cli.py device-overview --dev-id <DEV_ID>
```

Mind the response-shape asymmetry between branches (verified live):

- **Generic** `device_detail.result.properties` is an **object map** `code → value` in **native types** (e.g. `{"switch_1": false, "relay_status": "off", "cur_power": 0}`). Read a value directly by code.
- **Energy** `properties.result` is a **list** of `{"code", "time", "value"}` and every `value` is a **String** (e.g. `{"code":"heap_soc","time":...,"value":"55"}` — coerce `"true"/"false"` and numbers yourself). Latest value per code; `time` is the sample timestamp.

For generic devices, use the `properties` map to answer questions like "Is the light on?" or "What is the AC set to?". If `online` is `false`, tell the user the device is offline and stop.

> Note: the generic `device-overview` route may echo the raw category code in `category_name` (e.g. `znrb`). The human-readable name (e.g. `Smart Heat Pump`) comes from `list-devices` — prefer that when naming the device to the user.

### Workflow 3: Generic Device Control

```bash
python3 {baseDir}/scripts/conow_device_cli.py device-control \
  --dev-id <DEV_ID> --properties '{"switch_led": true}'
```

The CLI translates `--properties` into the shadow-issue body. Steps to map a user request to a property command:

1. Get the current state via `device-overview` (or `public-detail`).
2. Get the Thing Model via `public-model`. `result.model` is a **JSON string** — parse it to `{"modelId", "services":[...]}`. Property definitions are nested per service, **not** directly under `model`: iterate `services[]` and collect each `services[].properties[]` (each entry has `code`, `accessMode` (`ro`/`wr`/`rw`), and `typeSpec`). Verified live on a socket (`<SOCKET_DEV_ID>`): the controllable DPs are `switch_1` (`bool`), `countdown_1` (`value`, min 0 / max 86400 / step 1 / unit s), and `relay_status` (`enum` range `[off, on, memory]`); read-only DPs like `cur_power`, `cur_voltage`, `fault` are not controllable.
3. Inspect each property's `accessMode`:
   - `ro` (read-only): cannot be controlled.
   - `wr` (write-only): controllable but current value is not readable.
   - `rw` (read-write): controllable and queryable.
4. Map the user intent to a property code (e.g. on/off → `switch_led`; brightness → `bright_value`; AC mode → enum property).
5. For relative adjustments ("a bit brighter", "lower by 2 degrees"):
   - Read the current value from `properties`.
   - Read `min`, `max`, `step` from the Thing Model `typeSpec`.
   - Vague delta → ± (max - min) × 10%; specific delta → ± user value.
   - Clamp the target to `[min, max]` and round to `step`.
6. Validate the value range, then issue the command.
7. Verify by re-reading `device-overview` after 1–2 seconds.

### Workflow 4: Energy Device Control (逆变器 / string inverter) — 两步确认门禁

> **范围**：本门禁仅对**逆变器（string inverter）**开放控制。一体机（all-in-one / `balcony_solar`）**不**对外提供控制——其控制项不在白名单内，`control-plan` 会判定"无可控属性"。一体机的**只读查询**（状态/告警/指标）不受影响，仍可正常使用。

能源逆变器设备的控制**必须**走 `control-plan` → `control-confirm` 两步，**禁止**一步直发。

**实现方式（全部 end-user 接口，零新增后端接口）**：能力发现与下发全部在本 CLI 客户端完成——
- **发现/校验**：`control-plan` 调已发布的 `GET /energy/devices/model?type=setting` 拿到该机型物模型设置项，与技能内置的**最小白名单**（`ENERGY_CONTROL_ALLOWLIST`）取交集，范围/枚举/当前值以设备实测为准，并在本地校验取值。
- **下发**：`control-confirm` 经已发布的 `POST /energy/devices/issue` 下发（唯一已发布写口）。
- **不依赖**网关上未发布的 `GET /controllable` 与 `POST /control/issue`（这俩在当前网关返回 `1108`）。

> ⚠️ **`energy-issue` 是无校验裸通道**：它对任何 `code` 都直接受理（实测下发不存在的 code 也返回 `success:true`），且物模型 `type=setting` 会暴露大量设置项，含 `reset`（工厂复位）、`grid_*_threshold`（电网安全阈值）、`afci`、`insulation_detection` 等危险/装机参数。**因此本技能的白名单 + 本地校验就是唯一安全闸门**——只有白名单内、且取值合法的属性才会被 `control-confirm` 下发。需要新增可控项时，在 CLI 的 `ENERGY_CONTROL_ALLOWLIST` 中登记，**不要**改用底层 `energy-issue` 绕过闸门。

当前最小白名单（仅逆变器；与机型物模型取交集后实际可用项才出现）：
- **逆变器**：`inverter_work_mode_setting` 工作模式、`backup_enable` 备电、`forced_off_grid` 强制离网、`anti_reflux` 防逆流、`inverter_switch` 逆变器开关。

```bash
# 第1步：只读预览（客户端能力发现 energy-model∩白名单 + 当前值 + 本地校验），产出 plan_hash —— 绝不下发
python3 {baseDir}/scripts/conow_device_cli.py control-plan \
  --dev-id <DEV_ID> \
  --properties '{"inverter_work_mode_setting":"1"}'

# → 向用户复述 plan.items 的每一项（中文名 旧值→新值 + 单位 + 取值范围），取得明确同意

# 第2步：用户同意后才执行；参数须与 plan 完全一致，且回填 plan_hash（多候选时带同一 --energy-dev-id）
python3 {baseDir}/scripts/conow_device_cli.py control-confirm \
  --dev-id <DEV_ID> \
  --properties '{"inverter_work_mode_setting":"1"}' \
  --plan-hash <PLAN_HASH_FROM_STEP_1>
```

硬规则（不可绕过）：

1. **严禁一步写**：任何能源设备控制必须先 `control-plan`、再 `control-confirm`；不得直接调底层 `energy-issue`（它无校验、可越过白名单）。
2. **必须复述并取得同意**：用 `control-plan` 返回的 `items` 向用户复述「目标设备 / 每属性 旧值→新值+单位 / 取值范围」，得到用户**明确同意**后才 `control-confirm`。
3. **plan_hash 绑定**：`plan_hash = sha256(dev_id + 解析后的 energy_dev_id + 规范化 settings)`。`control-confirm` 参数必须与 `control-plan` 完全一致，**且要带同一个 `--energy-dev-id`**——传入不同的 `--energy-dev-id` 会改变 plan_hash、触发 `PLAN_HASH_MISMATCH` 并被拒绝（封堵多子设备误打的安全缺口）。`control-confirm` 还会**再做一次**白名单+取值校验（因为 `energy-issue` 不校验）。用户改了参数 → 重新 `control-plan` 再复述。
   - **`ready` 与退出码**：`control-plan` 仅在 `ready=true`（`errors` 为空且所有 `validation` 通过）时返回 `plan_hash` 并 **exit 0**；`ready=false` 时 `plan_hash` 为 `null`、附带「修正后重跑」的 `next` 提示并 **exit 1**。`ready=false` 时**不要**进入 `control-confirm`，先把 `errors`/`validation` 告诉用户、修正意图、重新 `control-plan`。
4. **不得谎称已执行**：只有 `control-confirm` 返回 `issued:true`（底层 `success:true`）才能说「已下发」。注意 `issue` 是 fire-and-forget——受理 ≠ 已生效，建议隔几秒用 `energy-properties --codes <code>` 复读确认。
5. **白名单外/机型不支持**：`control-plan` 把不在白名单的 code 归入 `errors`（`NOT_CONTROLLABLE`）、把白名单内但物模型没有的 code 直接不出现。若目标控制项不可用，如实告诉用户「该机型不支持此控制 / 暂未开放」，引导去 Conow App，不要臆造可控项，也不要走 `energy-issue` 硬下发。

> 普通（非能源）设备的控制不走本门禁，见 Workflow 3（`device-control` / `public-control`）；但同样**先与用户确认目标设备与动作**再下发。

### Workflow 5: Energy Device Diagnostics

```bash
python3 {baseDir}/scripts/conow_device_cli.py energy-topo       --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-protocol   --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-alarms     --dev-id <DEV_ID>
python3 {baseDir}/scripts/conow_device_cli.py energy-indicators --dev-id <DEV_ID>
```

Use `energy-alarms` for "Does this device have alarms?" prompts. Use `energy-indicators` for device-level metrics, and the `energy-sdata` subcommand for time series (it hits the `.../indicators/sdata` endpoint and requires `--indicator-code --start-time --end-time --query-step --query-type`).

Notes on `energy-alarms` parameters (verified live):

- **`--start-time` and `--end-time` are REQUIRED** and are **millisecond** timestamps. There is no default time window; the call errors without them.
- **Paging param differs by endpoint.** `energy-alarms` pages with `--page-num` (sent as `page_num`); home `list-devices` pages with `--page-no` (sent as `page_no`). Do not mix them up.
- **`--weight` defaults to `0`.** A live read with `weight=0` returned `success:true` with the normal `{data, total, hasNext, pageNum, pageSize}` envelope and was not rejected, so `weight=0` behaves as "all severities" (no narrowing) rather than a specific severity bucket. If you need a particular severity, pass an explicit non-zero `--weight`; leaving it at `0` will not silently hide alarms.

## Important Notes

1. **Auto-routing** is heuristic. Use `--force-route energy` or `--force-route public` when you have stronger context (e.g. you already know the device's category).
2. **Generic device control** uses the shadow channel. The `properties` body must be a JSON object; the CLI handles double-serialization.
3. **Energy device control.** Control is scoped to **string inverters only** — all-in-one (一体机) devices are not controllable (their codes are not in the allowlist; `control-plan` returns no controllable properties). User-driven control of an inverter MUST go through the two-step gate — `control-plan` → (recite + user consent) → `control-confirm` with `--properties` + `--plan-hash` (Workflow 4). The low-level `energy-issue` / `--setting` path is **not** for user-driven control; it is a raw issuance primitive, not the user-facing control surface.
4. If `device-overview` reports `online: false`, do not issue control commands.
5. Never echo the raw `CONOW_API_KEY` in output or logs. (`CONOW_VERBOSE=1` prints a redacted request summary to stderr.)
6. Home-level energy aggregation and AI dispatch planning are intentionally out of scope for this device skill.

## Supported and Unsupported Operations

### Supported

- Device detection and routing
- Account-level and home-level device listing
- Device detail / Thing Model / energy model query
- Generic device property control (`bool`, `enum`, `value`, `string` types)
- Energy device AI control via the two-step gate (`control-plan` → `control-confirm`) — **string inverters only**; the user-facing control surface, implemented client-side (`energy-model` ∩ skill allowlist → `energy-issue`), restricted to the minimal inverter allowlist. All-in-one (一体机) control is intentionally not offered.
- Energy device setting issuance (`energy-issue`) — **low-level primitive only**; user-driven energy-device control MUST use the gate above, not this
- Device alarms, indicators, time-series indicator data

### Unsupported

The following operations are **not** available through this skill:

- **Lock control** — Smart lock unlock/lock operations are sensitive and not exposed.
- **Live video streaming** — Real-time camera streams.
- **Image push** — Pushing images to devices.
- **Complex Thing Model types** — Properties with `raw`, `bitmap`, `struct`, or `array` `typeSpec` are not supported for control.
- **Firmware / OTA** — Device firmware upgrades.
- **Device pairing/removal** — Adding or removing devices.

If the user requests one of these operations, explain that it is not available through this skill and suggest using the Tuya / Conow App directly.

## Data Egress Statement

**This skill sends data to the Conow / Tuya Open Platform**:

| Data Type | Sent To | Purpose | Required |
|-----------|---------|---------|----------|
| Api-key | User-configured base_url (auto-detected from `sk-` prefix) | API authentication | Required |
| Device ID (`dev_id`, `energy_dev_id`) | User-configured base_url | Per-device query and control | Required |
| Control properties / energy settings | User-configured base_url | Device property issuance | Required for control commands |

This skill performs **write operations** when `device-control`, `public-control`, `control-confirm`, or the low-level `energy-issue` is invoked. For energy devices, user-driven control MUST use the two-step gate (`control-confirm` after `control-plan`); `energy-issue` is a low-level primitive, not the user-facing control path. Confirm the target device with the user before issuing any control command. Set `CONOW_BASE_URL` if you need to override the auto-detected gateway.
