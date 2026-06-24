---
name: conow-energy
description: >-
  Conow smart-home energy data via the openapi `sk-` gateway. Use this skill for home-level energy questions — real-time PV/battery/grid/load flow, indicator aggregate/trend/top (consumption SOL quartet, produce SOL quartet, storage charge/discharge), tariff query/label, hour-level forecast, optimization impact, or listing/resolving homes. Also use for home asset questions without a concrete `devId` (e.g. "battery state of charge", "is the home importing or exporting"). Do NOT use for per-device control or device model/topo/protocol/alarm queries (use `conow-device`), nor for AI dispatch plan/disable (use `conow-dispatch`). Requires CONOW_API_KEY.
metadata: { "openclaw": { "version": "1.0.0", "emoji": "⚡", "requires": { "env": ["CONOW_API_KEY"], "pip": [] }, "primaryEnv": "CONOW_API_KEY" } }
---

# Conow Smart Energy Skill

## Basic Information

- **Authentication**: Via Header `Authorization: Bearer {Api-key}`
- **Credentials**: Read from environment variable `CONOW_API_KEY`. Base URL is auto-detected from the API key prefix (see *Base URL Auto-detection* below). You can override by setting `CONOW_BASE_URL`.
- **API Reference**: See `references/api_reference.md`
- **Skill Manifest**: See `references/skill_manifest.md`
- **Python CLI**: See `scripts/conow_cli.py`

## Environment Variable Configuration

Set the following environment variable before use:

```bash
export CONOW_API_KEY="your-conow-api-key"
# CONOW_BASE_URL is optional — auto-detected from the sk- key prefix.
# Set it only if your deployment provides a dedicated gateway URL, e.g.:
# export CONOW_BASE_URL="https://openapi.tuyaeu.com"
```

Optional variables:

| Env var            | Flag           | Purpose                                              |
|--------------------|----------------|------------------------------------------------------|
| `CONOW_API_KEY`    | `--api-key`    | Required. Bearer token starting with `sk-`.          |
| `CONOW_BASE_URL`   | `--base-url`   | Override gateway URL.                                 |
| `CONOW_HOME_ID`    | `--home-id`    | Default `home_id` for queries.                       |
| `CONOW_HOMES_PATH` | `--homes-path` | Override list-homes path (default `/v1.0/end-user/homes/all`). |
| `CONOW_TIMEZONE`   | `--timezone`   | Force timezone; otherwise auto-derived from `home/station`. |

The skill will not load if `CONOW_API_KEY` is missing. Never echo the raw key back to the user.

### Base URL Auto-detection

When `CONOW_BASE_URL` is not set, the CLI selects a production data center by the `sk-` key prefix:

| Prefix    | Base URL                              |
|-----------|---------------------------------------|
| `sk-AY`   | `https://openapi.tuyacn.com`          |
| `sk-AZ`   | `https://openapi.tuyaus.com`          |
| `sk-EU`   | `https://openapi.tuyaeu.com`          |
| `sk-IN`   | `https://openapi.tuyain.com`          |
| `sk-UE`   | `https://openapi-ueaz.tuyaus.com`     |
| `sk-WE`   | `https://openapi-weaz.tuyaeu.com`     |
| `sk-SG`   | `https://openapi-sg.iotbing.com`      |

## Usage

**Always prefer Method 1 (Command Line)**. It handles authentication, URL resolution, JSON serialization, and error handling automatically.

### Method 1: Via Command Line (Recommended)

```bash
python3 {baseDir}/scripts/conow_cli.py <command> [params...]
# Examples:
python3 {baseDir}/scripts/conow_cli.py list-homes
python3 {baseDir}/scripts/conow_cli.py resolve-home --home-name "My Home"
python3 {baseDir}/scripts/conow_cli.py indicators-list --energy-type electricity
python3 {baseDir}/scripts/conow_cli.py indicators-aggregate \
  --home-id <HOME> --date-type day \
  --begin-date 20260420 --end-date 20260420 \
  --indicator-code ele_consumption_sol --time-aggr-type sum
python3 {baseDir}/scripts/conow_cli.py indicators-trend --home-id <HOME> ...
python3 {baseDir}/scripts/conow_cli.py indicators-top --home-id <HOME> ...
python3 {baseDir}/scripts/conow_cli.py forecast --home-id <HOME> \
  --begin-date <yyyyMMddHH, current hour or later> --end-date <same window, up to +48h>
python3 {baseDir}/scripts/conow_cli.py tariff-query --home-id <HOME> ...
python3 {baseDir}/scripts/conow_cli.py tariff-label --home-id <HOME> ...
python3 {baseDir}/scripts/conow_cli.py conow-flow --home-id <HOME>
python3 {baseDir}/scripts/conow_cli.py conow-power-curve --home-id <HOME> ...
python3 {baseDir}/scripts/conow_cli.py conow-impact --home-id <HOME> ...
python3 {baseDir}/scripts/conow_cli.py conow-indicators
python3 {baseDir}/scripts/conow_cli.py conow-station --home-id <HOME>
```

Use `python3 {baseDir}/scripts/conow_cli.py --help` for the full command list.

## Feature Overview

| Module | Capabilities | Endpoints |
|--------|-------------|-----------|
| Home Discovery | List homes, fuzzy-resolve home by name | `/v1.0/end-user/homes/all` |
| Indicator Metadata | Platform indicator dictionary, filter by energy type / keyword | `/v1.0/end-user/energy/indicators` |
| Aggregate / Trend / Top | Sum, average, time-series and ranking on indicator codes | `/v1.0/end-user/energy/indicators/aggregate|trend|top` |
| Forecast | Hour-granular next-N-hour predictions (≤ 48h, ≤ 2 codes) | `/v1.0/end-user/energy/forecast` |
| Tariff | Tariff price and high/medium/low labels | `/v1.0/end-user/energy/tariff/query|label` |
| Home Real-time / Curve / Impact | Real-time flow, power curve, optimization impact, home indicator dict, station metadata | `/v1.0/end-user/energy/home/flow|power-curve|impact|indicators|station` |

## Routing Cheatsheet

| User intent | Default command | Notes |
|-------------|-----------------|-------|
| "What is my home using right now?" / "Am I importing or exporting?" | `conow-flow`; if unsupported, fall back to same-day `indicators-aggregate` | The fallback is kWh aggregation, not real-time power. |
| "How much did I use today / this month?" | `indicators-aggregate` | Use the consumption SOL quartet for home totals. |
| "How much solar did I generate?" | `indicators-aggregate` | Use the produce SOL quartet for home totals. |
| "Battery SOC?" / "Is the battery charging or discharging?" with no `devId` | `indicators-aggregate` / `trend` with `ele_store_percent`, or `conow-flow` | Home-asset overview without a device. |
| "Which device used the most this week?" | `indicators-top` | `--group-by device --indicator-code ele_usage`. |
| "Is the current tariff high or low?" / "Tariff for tomorrow?" | `tariff-query` + `tariff-label` | Provide window and `direction` (import/export). |
| "How much will my solar produce in the next day?" | `forecast` | Hour-only, ≤ 48h window, anchor `--begin-date` at the current hour or later. |
| "When is electricity cheapest?" | `tariff-query` plus optional `forecast` | Rule-based advice; do not claim exact savings unless an endpoint returns it. |
| "How much did optimization save me?" | `conow-impact` | If unavailable, explain the missing baseline; do not fabricate. |

When the user's query is in English, Chinese, or mixed language, the same routing applies. Reply in the user's language; keep `home_id`, `devId`, indicator codes, and gateway error codes unchanged.

## Core Workflows

### Workflow 1: Resolve a Home

`home_id` is required by every energy endpoint, but **never ask the user for `home_id` as the first move** — talk in terms of home names.

1. If the user already provided a `home_id`, or `CONOW_HOME_ID` is set, use it silently.
2. Otherwise call `resolve-home` (or `list-homes`):
   - If exactly one home is returned, auto-select it and tell the user which one.
   - If several are returned, ask the user **by name**. Show `home_id` only if the user requests it or if names collide.
   - Pass partial names via `--home-name`; the CLI fuzzy-matches.
3. If `list-homes` fails, ask the user for a `home_id` directly and tell them where to find it (e.g. App settings / admin console).

```bash
python3 {baseDir}/scripts/conow_cli.py resolve-home
python3 {baseDir}/scripts/conow_cli.py resolve-home --home-name "My Home"
python3 {baseDir}/scripts/conow_cli.py list-homes
```

`resolve-home` returns:
- `{"success": true, "home_id": "..."}` — safe to proceed.
- `{"success": false, "error": "...", "candidates": [...]}` — a **normal "ask which home" outcome, not a gateway error**. The CLI **exits 0** here (no stderr "gateway returned success=false"). Present `candidates[].name` to the user and let them pick. On an ambiguous name match, `candidates` lists only the **matched subset**; on a genuine not-found or a multi-home account with no `--home-name`, `candidates` lists all homes.

`home_id` is a numeric string (e.g. `"100200300"`). Pass it verbatim to downstream endpoints. Non-numeric strings are rejected with `1109`.

> `--home-name` wins over a `CONOW_HOME_ID` default — if you pass `--home-name`, the CLI resolves the name even when `CONOW_HOME_ID` is set. `CONOW_HOME_ID` is only used as the default when no `--home-name` is given.

### Workflow 2: Resolve Home Timezone

For statistics windows, prefer the **home's** timezone over the agent or machine timezone. The CLI applies it automatically — but **only for `indicators-aggregate`, `indicators-trend`, and `indicators-top`**:

- These three first use `--timezone` / `CONOW_TIMEZONE` if set.
- Otherwise they call `POST /v1.0/end-user/energy/home/station` to read `time_zone_id` and inject `timezone` into the body. When this auto-fill happens, the CLI prints a one-line **stderr** note naming the station timezone, e.g. `[conow] using home station timezone Europe/Berlin for date windows`.
- If station lookup fails or omits `time_zone_id`, the request continues without `timezone`; do not fail the user-facing query.
- **`forecast`, `tariff-query`, `tariff-label`, `conow-flow`, and `conow-power-curve` do NOT auto-fill** the timezone — they use `--timezone` / `CONOW_TIMEZONE` **verbatim** (or the home default server-side). For these, pass `--timezone` yourself when the window boundary matters.

Watch the stderr note: a home's **station** timezone can differ from its **physical** location (e.g. a CN home configured as `Europe/Berlin`). When the named station tz looks wrong for the user's locale, caveat relative windows like "today" / "this month", or pass an explicit `--timezone`.

```bash
python3 {baseDir}/scripts/conow_cli.py conow-station --home-id <HOME>
```

### Workflow 3: Aggregate / Trend / Top

```bash
python3 {baseDir}/scripts/conow_cli.py indicators-aggregate \
  --home-id <HOME> \
  --date-type day --begin-date 20260420 --end-date 20260420 \
  --indicator-code ele_consumption_sol,ele_produce \
  --time-aggr-type sum

python3 {baseDir}/scripts/conow_cli.py indicators-trend \
  --home-id <HOME> \
  --date-type day --begin-date 20260414 --end-date 20260420 \
  --indicator-code ele_consumption_sol

python3 {baseDir}/scripts/conow_cli.py indicators-top \
  --home-id <HOME> \
  --date-type month --begin-date 202604 --end-date 202604 \
  --indicator-code ele_usage \
  --group-by device --number 5
```

Wire-format rules (the CLI normalizes input):

- `--indicator-code` accepts repeated flags **or** a comma-separated list. The CLI joins to a single `"a,b,c"` string. **Max 20 codes per request.**
- `--time-aggr-type` / `--device-aggr-type` are UPPERCASE on the wire (`SUM`/`AVG`/`MAX`/`MIN`).
- `--date-type` is lowercase on the wire. Valid values are `quarter`/`hour`/`day`/`month`/`year` only — there is **no `week`**. The CLI rejects `week` **locally at argparse** (`choices=quarter/hour/day/month/year`, exit 2) before any HTTP call, so it never reaches the gateway. (Historically the raw API returned `501` for `week`; that observation no longer applies via the CLI.) For a weekly **total**, use `--date-type day` over the 7-day range with `--time-aggr-type sum`; for finer-than-hour granularity use `quarter` (15-minute buckets, `yyyyMMddHHmm`).
- `indicators-top` requires a singular `--indicator-code`, plus `--group-by` (`device` / `space` / `usage`) and `--number` in `[1, 50]`. Optional `--sort-type` is `asc`/`desc` (default `desc`).
- Use `--ext-condition '{"deviceIds":["..."]}'` for documented dimension or device filters.

### Workflow 4: Forecast

`POST /v1.0/end-user/energy/forecast` constraints:

- **Hour granularity only.** Both `begin_date` and `end_date` must be `yyyyMMddHH` (10 digits).
- **Maximum 48-hour window** (inclusive). Longer windows silently return an empty list.
- **Past-only windows return an empty list** (no error). Anchor `--begin-date` at the current hour or later.
- **Up to 2 indicator codes per request**, drawn from `ele_forecast_produce` and `ele_forecast_consumption`. The CLI defaults to both when `--indicator-code` is omitted.

```bash
python3 {baseDir}/scripts/conow_cli.py forecast \
  --home-id <HOME> \
  --begin-date <yyyyMMddHH, current hour or later> --end-date <same window, up to +48h>

# Single indicator
python3 {baseDir}/scripts/conow_cli.py forecast \
  --home-id <HOME> \
  --indicator-code ele_forecast_produce \
  --begin-date <yyyyMMddHH, current hour or later> --end-date <same window, up to +48h>

# Bypass forecast cache for fresh predictions
python3 {baseDir}/scripts/conow_cli.py forecast \
  --home-id <HOME> \
  --begin-date <yyyyMMddHH, current hour or later> --end-date <same window, up to +48h> \
  --use-cache false
```

Response shape (one entry per requested indicator):

```jsonc
{
  "success": true,
  "result": [
    {
      "indicator": "ele_forecast_produce",
      "totalValue": { "Value": "12.34" },
      "unit": "kWh",
      "list": [
        { "date": "2026042710", "unit": "kWh", "value": { "Value": "0.00" } }
      ]
    }
  ]
}
```

### Workflow 5: Tariff

`tariff-query` and `tariff-label` are POST JSON.

```bash
python3 {baseDir}/scripts/conow_cli.py tariff-query \
  --home-id <HOME> \
  --date-type hour --begin-date 2026042100 --end-date 2026042200 \
  --direction import

python3 {baseDir}/scripts/conow_cli.py tariff-label --home-id <HOME> --direction import
```

### Workflow 6: Home Real-time / Curve / Impact

```bash
python3 {baseDir}/scripts/conow_cli.py conow-flow --home-id <HOME>

python3 {baseDir}/scripts/conow_cli.py conow-power-curve --home-id <HOME> \
  --date-type day --begin-date 20260420 --end-date 20260420 \
  --indicator-code home_total_load_power,home_total_grid_port_power

# Weekly impact: use date-type day across the 7-day range (there is no `week`).
python3 {baseDir}/scripts/conow_cli.py conow-impact --home-id <HOME> \
  --date-type day --begin-date 20260414 --end-date 20260420 \
  --phone-code CN

python3 {baseDir}/scripts/conow_cli.py conow-indicators
python3 {baseDir}/scripts/conow_cli.py conow-station --home-id <HOME>
```

`conow-flow` and `conow-power-curve` return power values with their own payload units (typically `W` in `power-curve`). Do not convert or relabel units unless you have verified the payload.

Live response-shape notes (do not assume the richer shapes are always present):

- **`conow-flow`**: the rich fields (`grid_status`, `has_grid`, the `indicators[]` array with per-device breakdowns and `soc`) appear **only** when the home has live device telemetry. Otherwise the gateway returns just `{"soc_count": 0}` with `success=true`. When the flow snapshot is empty, fall back to a same-day `indicators-aggregate` and tell the user it's an aggregate, not real-time power.
- **`conow-flow` implausible-value flags**: the CLI annotates suspect power readings. A reading equal to a 32-bit sentinel (e.g. `2863311530` W = `0xAAAAAAAA` uninitialized/NaN, or `0xFFFFFFFF`) or above a 100 MW cap gets a `"_suspect"` field on that item, and the payload gains a top-level `"_warnings"` list naming each flagged value. **Trust these flags: do NOT quote a flagged value as live power** — treat that device/indicator as unreported and prefer a same-day `indicators-aggregate` (kWh) instead, telling the user the live reading was unavailable.
- **`conow-impact`**: read both wrapped and bare forms — `carbon_reduction` and `total_ele_produce_cost` may be **wrapped** as `{"Value": "..."}`, while `total_ele_produce` is a **bare** number; `self_sufficiency` may come back empty (`{}`). Do **not** assume the percent splits sum to 100, and skip self-sufficiency reporting when it's unavailable.
  - **`energy_production.ele_unit` is mislabeled `"W"`** but the accompanying `total_ele_produce` is an energy **total in Wh** — divide by 1000 for kWh, not by any power-to-energy conversion. Report kWh; do not quote it as watts.
  - **`--phone-code` wants an ISO 3166 alpha-2 code** (`CN` / `SE` / `DE`), and it is **NOT validated** — a numeric dialing code like `86` is silently accepted and quietly changes the carbon-reduction factor (wrong figure, no error). Always pass the alpha-2 country code, never a dial code.
- **`conow-station`**: `time_zone_id` is an IANA timezone — use it as the `timezone` field in statistics calls. `country_code` may be alpha-3 (e.g. `CHN`), whereas `conow-impact --phone-code` wants ISO 3166 **alpha-2** (e.g. `CN`, `SE`). Map / confirm the code before passing it to impact; do not copy `country_code` verbatim.

## Indicator Reference

### Consumption SOL Quartet (家庭用电量, default for home totals)

For home-level questions about how much electricity was consumed and where it came from, treat these four indicators as one bundle (kWh, **same source-of-load accounting basis**):

| `indicator_code` | Meaning |
|------------------|---------|
| `ele_consumption_sol` | **Total home consumption** |
| `ele_consumption_from_pv_sol` | Consumption sourced from PV |
| `ele_consumption_from_battery_sol` | Consumption sourced from battery |
| `ele_consumption_from_grid_sol` | Consumption sourced from grid |

Default behavior: after `resolve-home`, run `indicators-aggregate` (or `trend`) with all four codes in one request.

```bash
python3 {baseDir}/scripts/conow_cli.py indicators-aggregate \
  --home-id <HOME> \
  --date-type day --begin-date 20260421 --end-date 20260421 \
  --indicator-code ele_consumption_sol,ele_consumption_from_pv_sol,ele_consumption_from_battery_sol,ele_consumption_from_grid_sol \
  --time-aggr-type sum
```

Distinguish from these similarly named codes:

- `ele_usage` — device-level / meter-side usage. Use for **device ranking** (`indicators-top`), not as a substitute for `ele_consumption_sol`.
- `ele_consumption` (no `_sol`) — net household energy with PV/storage netted in. **Not** equivalent to `ele_consumption_sol`. Do not assume equivalence without `indicators-list` confirmation.

### Produce SOL Quartet (家庭发电量, default for generation totals)

Mirror bundle for generation-side questions (kWh, same SOL basis from the generator's perspective):

| `indicator_code` | Meaning |
|------------------|---------|
| `ele_produce` | **Total home generation** |
| `ele_produce_to_consumption_sol` | Generation routed to load |
| `ele_produce_to_charge_sol` | Generation routed to battery charge |
| `ele_produce_to_gridcn_sol` | Generation exported to grid |

The three `_to_*_sol` splits should sum to `ele_produce` (± rounding). If they diverge, report the gap rather than smoothing it over.

Cross-side identity with the consumption quartet (same kWh flow, two perspectives):

| Consumption side (`_from_*_sol`) | Produce side (`_to_*_sol`) |
|----------------------------------|----------------------------|
| `ele_consumption_from_pv_sol`    | `ele_produce_to_consumption_sol` |

(Battery-charge and grid-export flows are tracked only on the produce side.)

```bash
python3 {baseDir}/scripts/conow_cli.py indicators-aggregate \
  --home-id <HOME> \
  --date-type day --begin-date 20260421 --end-date 20260421 \
  --indicator-code ele_produce,ele_produce_to_consumption_sol,ele_produce_to_charge_sol,ele_produce_to_gridcn_sol \
  --time-aggr-type sum
```

`ele_produce` vs `ele_pv_produce`:

- `ele_produce` — local generation total (PV + any other local generation). Default for generation totals on this gateway.
- `ele_pv_produce` — PV-panel-only. Semantically narrower, populated sparsely. Prefer only when the user explicitly asks for PV-only on a home you have confirmed populates it.

### Storage Charge / Discharge

For home-level battery questions:

| `indicator_code` | Meaning |
|------------------|---------|
| `ele_store_discharge` | **Storage discharge (kWh)** |
| `ele_produce_store` | **Storage charge (kWh)** |

Do **not** use `ele_store_charge` for charge totals — it is not the platform's documented storage-charge indicator and may return misleading zero-value responses. `ele_produce_to_charge_sol` is the SOL allocation of generation to battery, not the general "storage charge" answer.

```bash
python3 {baseDir}/scripts/conow_cli.py indicators-aggregate \
  --home-id <HOME> \
  --date-type month --begin-date 202604 --end-date 202604 \
  --indicator-code ele_store_discharge,ele_produce_store \
  --time-aggr-type sum
```

### Combined call (full picture in one request)

When the user wants total consumption, total generation, and both attribution splits in one window, pack both quartets into one call (8 codes):

```bash
python3 {baseDir}/scripts/conow_cli.py indicators-aggregate \
  --home-id <HOME> \
  --date-type day --begin-date 20260421 --end-date 20260421 \
  --indicator-code ele_consumption_sol,ele_consumption_from_pv_sol,ele_consumption_from_battery_sol,ele_consumption_from_grid_sol,ele_produce,ele_produce_to_consumption_sol,ele_produce_to_charge_sol,ele_produce_to_gridcn_sol \
  --time-aggr-type sum
```

Sanity check: `ele_consumption_from_pv_sol` should equal `ele_produce_to_consumption_sol`. If they diverge by more than a rounding error, report the gap.

### Indicator Metadata Probe

```bash
python3 {baseDir}/scripts/conow_cli.py indicators-list
python3 {baseDir}/scripts/conow_cli.py indicators-list --energy-type electricity
python3 {baseDir}/scripts/conow_cli.py indicators-list --keyword pv
```

`indicators-list` is the platform-wide dictionary (no `home_id`), filterable by `--energy-type` (`electricity` / `water` / `gas`) and `--keyword`. Treat the dictionary as **advisory**: an empty SOL listing does not prove the aggregate API rejects SOL codes — for an actual home-level usage question, resolve the home and try the SOL aggregate/trend call once before downgrading semantics.

## Name Matching Rules

`--home-name` is fuzzy-matched against the `list-homes` result, in priority order:

1. Case-insensitive **exact** name match wins outright.
2. Numeric query equal to a `home_id` is treated as exact (so a name or numeric id can be passed to the same flag).
3. **Forward substring** — `"Sun"` matches `"Sunset Home"`.
4. **Reverse substring** — `"Sunset Home Garage"` matches a home named `"Sunset Home"`. Reverse substring requires the home name to be at least 3 characters.

If no candidate matches, or multiple substring matches are found, the CLI returns the candidate list — it never silently picks a winner.

## Error Codes

| Code | Meaning | Recovery |
|------|---------|----------|
| 1010 | Token invalid | Path exists but the key has no access. |
| 1106 | Group permission deny | `home_id` syntax is fine but the key cannot see that home. Re-run `list-homes` or confirm `home_id`. |
| 1108 | URI path invalid | The requested capability is unavailable on the current gateway. |
| 1109 | Param illegal | Body violates gateway mapping. Common causes: sending `indicator_codes` as an array instead of comma-separated string; lowercase `time_aggr_type` (must be `SUM/AVG/MAX/MIN`); missing required field. |
| 1110 | Illegal param | Field-level validation failure (wrong format, out of range). |
| 501  | request fail with unknown error | Internal server error, historically observed on the raw API for an unsupported/invalid `date_type` (e.g. `week`, or wrong casing). Via the CLI `week` is now rejected locally at argparse (exit 2) and never reaches the gateway, so you should not see `501` for it here. |

When a `1108` is returned and the user's `home_id` is not yet verified, confirm a usable home before trying another home-level query.

`1109` (param illegal) and `1110` (illegal param) both mean a parameter/field problem — a missing or wrong-typed field, an array where a comma-separated string is expected, wrong enum casing, or an out-of-range value. The CLI now prints an actionable hint for these (and for `1010`); read the hint, compare field names and enum casing against `references/api_reference.md`, then retry with corrected parameters.

## Request / Response Conventions

- Request bodies and query params use **snake_case** (`home_id`, `date_type`, `indicator_codes`).
- List fields are serialized as **comma-separated strings**, not JSON arrays. `indicator_codes: "a,b,c"`, max 20.
- Enum casing on the wire:
  - `time_aggr_type` / `device_aggr_type` → UPPERCASE (`SUM`/`AVG`/`MAX`/`MIN`)
  - `sort_type` → lowercase (`asc`/`desc`)
  - `date_type` → lowercase (`quarter`/`hour`/`day`/`month`/`year`). There is **no `week`** — the CLI blocks it locally at argparse (exit 2) before any request, so it never reaches the gateway. For a weekly total, query `day` over the 7-day range with `time_aggr_type=SUM`.
- Response casing depends on the endpoint, not just the field:
  - **POST data / forecast** endpoints (`indicators/aggregate|trend|top`, `forecast`, `home/flow|impact|station`) return **snake_case** fields.
  - **GET `/indicators`** returns camelCase (`energyType` / `indicatorType`), and **`tariff/query`** returns a camelCase object (`result.tariffList[]` with `beginDate`/`endDate`/`currency`/`tariff`/`type`/`sourceFrom` plus supplier metadata like `supplierName`/`priceType`).
  - Indicator values are wrapped as `"value": {"Value": "0.00"}` (capital `V`); `indicators/trend` and `forecast` also wrap `"totalValue": {"Value": "..."}` per indicator. `home/power-curve` list items carry both `value` (string) and `value_origin` (numeric raw). Pass these keys back to the user verbatim when quoting values.
- Date formats follow `date_type`:
  - `year` → `YYYY`
  - `month` → `YYYYMM`
  - `day` → `YYYYMMDD`
  - `hour` → `YYYYMMDDHH`
  - `quarter` → `YYYYMMDDHHmm` (12 digits, 15-minute buckets)
- Numeric values (kWh, kW, prices, SOC) come back as strings to preserve precision. Cast cautiously.

## Important Notes

1. This skill is **read-only**. None of the endpoints listed mutate device or home state.
2. Always confirm the `home_id` you used (especially on multi-home accounts) when quoting numbers.
3. State time windows in the user's locale, not only in raw `YYYYMMDDHH`.
4. If the gateway returned `success=false`, never invent numbers from the partial payload — report the `code` and `msg`.
5. Never echo the raw `CONOW_API_KEY` in output or logs. (`CONOW_VERBOSE=1` prints a redacted request summary to stderr.)
6. For per-device control or device model/topo/protocol/alarm queries, use the `conow-device` skill. For AI dispatch plan/disable, use `conow-dispatch`.

## Data Egress Statement

**This skill sends data to the Conow / Tuya Open Platform**:

| Data Type | Sent To | Purpose | Required |
|-----------|---------|---------|----------|
| Api-key | User-configured base_url (auto-detected from `sk-` prefix) | API authentication | Required |
| `home_id` | User-configured base_url | Per-home energy queries | Required for all energy reads |
| Query parameters (date range, indicator codes, direction, group-by) | User-configured base_url | Indicator / forecast / tariff / home queries | Required |

This skill does not send any device control commands. Set `CONOW_BASE_URL` if you need to override the auto-detected gateway.
