# Conow End-User Energy API Reference

Gateway: the base URL is auto-derived from the sk- key prefix
(e.g. `sk-AY...` → `https://openapi.tuyacn.com`,
`sk-AZ...` → `https://openapi.tuyaus.com`; full table in
[`SKILL.md`](../SKILL.md#base-url-auto-detection)). Override with
`CONOW_BASE_URL` only if your deployment provides a dedicated gateway URL.
Auth: `Authorization: Bearer sk-...`

## Conventions

- **Request body**: snake_case.
- **Response casing depends on the endpoint, not just the field.**
  - **POST data / forecast** endpoints (`indicators/aggregate|trend|top`,
    `forecast`, `home/flow|impact|station`) return **snake_case** fields.
  - **GET `/indicators`** returns camelCase (`energyType` / `indicatorType`),
    and **`tariff/query`** returns a camelCase object (`result.tariffList[]`
    with `beginDate`/`endDate`/`currency`/`tariff`/`type`/`sourceFrom`, plus
    supplier metadata such as `supplierName`/`supplierCode`/`priceType`).
  - Indicator value objects are wrapped as `"value": {"Value": "..."}`
    (capital `V`); `indicators/trend` and `forecast` also wrap
    `"totalValue": {"Value": "..."}` per indicator. `home/power-curve` list
    items carry both `value` (string) and `value_origin` (numeric raw).
- **Numbers** are returned as strings to preserve precision (the bare
  `value_origin` on `home/power-curve` and a few `home/impact` fields are the
  exceptions — see those sections).
- **List fields are comma-separated strings, NOT JSON arrays.** The Java
  request classes declare `indicatorCodes` as `String` and split by `,`
  (max 20 entries). Sending `["a","b"]` returns `1109 param illegal`.
- **Enum casing matters.**
  - `time_aggr_type`, `device_aggr_type`: UPPERCASE (`SUM`/`AVG`/`MAX`/`MIN`).
    Lowercase → `1109 param illegal`.
  - `sort_type`: lowercase (`asc`/`desc`).
  - `date_type`: lowercase (`quarter`/`hour`/`day`/`month`/`year`). There is
    **no `week`** — the backend `DateType` enum does not include it. The
    bundled CLI rejects `week` **locally at argparse** (`choices` =
    quarter/hour/day/month/year, exit 2) before any HTTP call, so it never
    reaches the gateway. (Historically a raw-API `week` request returned
    `501 request fail with unkown error`; that observation predates the CLI's
    local guard.) For a weekly total, query `day` over the 7-day range with
    `time_aggr_type=SUM`; for finer-than-hour granularity use `quarter`.
    Uppercase values (e.g. `DAY`) trigger the downstream `501` at the gateway.
- **Date format** keyed off `date_type`:
  - `year` → `YYYY`; `month` → `YYYYMM`; `day` → `YYYYMMDD`;
    `hour` → `YYYYMMDDHH`; `quarter` → `YYYYMMDDHHmm` (12 digits, 15-minute
    buckets).
- **Timezone** should be included on statistics windows when known. Use
  `POST /v1.0/end-user/energy/home/station` and copy
  `result.time_zone_id` into the `timezone` request field. The bundled CLI
  does this automatically for `indicators/aggregate`, `indicators/trend`, and
  `indicators/top` unless an explicit `--timezone` / `CONOW_TIMEZONE` is set
  or `--no-auto-timezone` is passed.

Legend:
- ✅ Supported on the end-user gateway under typical deployments.
- ⚠️ Availability can vary by data center. If the gateway reports the
  capability unavailable, explain the limitation and avoid fabricating values.
- 📘 Backend-spec'd (fields / responses confirmed against the Conow backend
  spec; if not also marked ✅, on-gateway availability may vary).
- 🧩 Endpoint is a supporting source for aggregate AI skills.

---

## 1. ✅ `GET /v1.0/end-user/energy/indicators`

System-level indicator metadata. **No `home_id` required** (this endpoint only
accepts `energy_type` + `keyword`).

> **Casing note**: this GET endpoint returns **camelCase** keys
> (`energyType`, `indicatorType`) inside each `result[]` entry, unlike the
> snake_case POST data endpoints. Verified live.

**Query**

| key         | required | notes                                           |
|-------------|----------|-------------------------------------------------|
| energy_type | no       | `electricity` / `water` / `gas`; omit for all   |
| keyword     | no       | fuzzy match on `code` or `name` (max 64 chars)  |

**Response snippet**

```json
{
  "result": [
    { "code": "ele_usage", "name": "家庭用电量", "unit": "kWh",
      "energyType": "electricity", "indicatorType": "origin",
      "description": "家庭设备实际用电量,由电表或估算模型生成" },
    { "code": "ele_pv_produce", "name": "光伏发电量", "unit": "kWh",
      "energyType": "electricity", "indicatorType": "origin" }
  ],
  "success": true,
  "t": 1776740...,
  "tid": "..."
}
```

**Common electricity indicator codes**

| code                      | meaning                                       |
|---------------------------|-----------------------------------------------|
| ele_usage                 | 家庭设备实际用电量                            |
| ele_consumption           | 家庭总能耗（光储并入后视为净消耗）            |
| ele_purchase              | 购电量                                        |
| ele_produce               | 本地发电量总和                                |
| ele_pv_produce            | 光伏发电量                                    |
| ele_produce_gridcn        | 上网电量                                      |
| ele_store_discharge       | 储能放电量                                    |
| ele_produce_store         | 储能充电量 (from PV)                          |
| ele_store_percent         | 电池 SOC (%)                                  |
| ele_*_cost                | 对应费用口径 (unit=currency)                  |
| ele_forecast_produce      | 预测发电量 (forecast endpoint)                |
| ele_forecast_consumption  | 预测用电量 (forecast endpoint)                |

### SOL 家庭用电分项 — consumption side (`ele_consumption_*_sol`)

These codes describe **household electricity consumption (kWh)** under a
**source-of-load** accounting split (how much consumed energy was attributed
to PV vs battery vs grid). **Default bundle** for home-level “家庭用电量” /
总用电 questions: query all four together. Also use when the user asks only
for 分项（太阳 / 电池 / 电网） or product copy names these fields.

| code | Typical Chinese label | Meaning |
|------|------------------------|---------|
| `ele_consumption_sol` | 家庭总用电量 | Total home consumption (SOL basis) |
| `ele_consumption_from_pv_sol` | 光伏的用电量 / 太阳 | Consumption attributed to solar (PV) |
| `ele_consumption_from_battery_sol` | 电池的用电量 / 电池 | Consumption attributed to battery discharge path |
| `ele_consumption_from_grid_sol` | 电网的用电量 / 电网 | Consumption attributed to grid import |

**Not the same as**

- `ele_usage` — “家庭设备实际用电量” (meter / model **device** layer). Prefer for
  `indicators-top` / per-device usage. For **家庭总用电量** product口径, use
  `ele_consumption_sol` + the three `ele_consumption_from_*_sol` codes instead
  of substituting `ele_usage`.
- `ele_consumption` — complex “家庭能耗 / 光储并入后净消耗”; different naming and
  semantics from `ele_consumption_sol`; verify per gateway in `indicators-list`.

### SOL 家庭发电分项 — produce side (`ele_produce_to_*_sol`)

The mirror of the consumption SOL quartet, viewed from the **generator's
side**. Use as the **default bundle** for home-level “家庭发电量 / 今天发了
多少电 / 发的电去哪儿了” questions. All values are kWh.

| code | Typical Chinese label | Meaning |
|------|------------------------|---------|
| `ele_produce` | 家庭发电量 | Total local generation (光储系统发电总和) |
| `ele_produce_to_consumption_sol` | 家庭负载 | Generation allocated to household load |
| `ele_produce_to_charge_sol` | 电池 | Generation allocated to battery charging |
| `ele_produce_to_gridcn_sol` | 公共电网 | Generation exported to the grid |

Accounting identity (± rounding):
`ele_produce ≈ ele_produce_to_consumption_sol + ele_produce_to_charge_sol + ele_produce_to_gridcn_sol`.

**Dual-side match with the consumption quartet**: the same kWh flow is
recorded from both perspectives — on the same home / same window, these
two values should match up to rounding:

- `ele_consumption_from_pv_sol` == `ele_produce_to_consumption_sol`
  (负载侧"光伏来的电" == 发电侧"流向负载的发电")

**ele_produce vs ele_pv_produce** (both exist in the system dictionary)

| code | semantic | populated on the gateway? |
|------|----------|-----|
| `ele_produce` | Local generation total (PV + storage combined) | **Yes, including simulation homes** — prefer this as the default |
| `ele_pv_produce` | PV-panel generation only (strictly PV-only) | Sparsely; many homes return `0.00` |

For pure PV+battery homes these two are numerically equal in the common
case (batteries store, they don't produce). Use `ele_pv_produce` only when
the user explicitly needs a PV-panel-only slice on a home you have
confirmed writes this code.

**Deployment note**

- Indicator dictionaries vary by gateway revision. `indicators-list
  --keyword sol` typically returns **empty** on this gateway even though
  both SOL quartets answer correctly via `aggregate`/`trend`. Treat the
  dictionary as advisory; probe the live aggregate call on the resolved
  home rather than refusing because a code is "missing".
- If a resolved home returns `ele_produce > 0` but all three
  `ele_produce_to_*_sol` are `0`, the produce SOL breakdown isn't wired
  on that home — report `ele_produce` alone and note the split isn't
  available. Do not imply all generation went to one of the three buckets.

---

## 2. ✅ `POST /v1.0/end-user/energy/indicators/aggregate`

Aggregate one or more indicators over a time window.

**Body**

```json
{
  "home_id": "100200300",
  "indicator_codes": "ele_consumption_sol,ele_consumption_from_pv_sol,ele_consumption_from_battery_sol,ele_consumption_from_grid_sol,ele_produce,ele_produce_to_consumption_sol,ele_produce_to_charge_sol,ele_produce_to_gridcn_sol",
  "date_type": "day",
  "begin_date": "20260420",
  "end_date": "20260420",
  "time_aggr_type": "SUM",
  "timezone": "Asia/Shanghai",
  "options": "{\"scale\":2}"
}
```

> This example packs **both** SOL quartets (consumption + produce, 8 codes)
> into a single request — well under the 20-code cap. On the same home/
> window, `ele_consumption_from_pv_sol` should numerically match
> `ele_produce_to_consumption_sol` up to rounding.

| field             | required | notes                                                 |
|-------------------|----------|-------------------------------------------------------|
| home_id           | yes      | numeric string                                        |
| indicator_codes   | yes      | **comma-separated string**, max 20                    |
| date_type         | yes      | `quarter` / `hour` / `day` / `month` / `year` (lowercase; no `week`) |
| begin_date        | yes      | format matches `date_type`                            |
| end_date          | yes      | inclusive                                             |
| time_aggr_type    | no       | `SUM` / `AVG` / `MAX` / `MIN` (UPPERCASE)             |
| device_aggr_type  | no       | same set as above                                     |
| include_children  | no       | boolean; include child dimensions                     |
| ext_condition     | no       | JSON string for device/space filtering                |
| timezone          | no       | IANA tz; supply `home/station.time_zone_id` when known |
| options           | no       | JSON string; only `scale` (non-negative int) is read  |

**Response snippet** (home `100200300`, day `20260421`)

```json
{
  "result": [
    { "indicator": "ele_consumption_sol",            "unit": "kWh", "value": {"Value": "4.90"} },
    { "indicator": "ele_consumption_from_pv_sol",    "unit": "kWh", "value": {"Value": "4.40"} },
    { "indicator": "ele_consumption_from_battery_sol","unit": "kWh", "value": {"Value": "0.50"} },
    { "indicator": "ele_consumption_from_grid_sol",  "unit": "kWh", "value": {"Value": "0.00"} },
    { "indicator": "ele_produce",                    "unit": "kWh", "value": {"Value": "4.42"} },
    { "indicator": "ele_produce_to_consumption_sol", "unit": "kWh", "value": {"Value": "4.40"} },
    { "indicator": "ele_produce_to_charge_sol",      "unit": "kWh", "value": {"Value": "0.02"} },
    { "indicator": "ele_produce_to_gridcn_sol",      "unit": "kWh", "value": {"Value": "0.00"} }
  ],
  "success": true,
  "t": 1776823509, "tid": "..."
}
```

Note the cross-side identity: `ele_consumption_from_pv_sol == ele_produce_to_consumption_sol == 4.40`.
The produce splits sum to `ele_produce` (4.40 + 0.02 + 0.00 = 4.42). Result
order is not stable — route by the `indicator` field, not by index.

**Typical error codes**

| code | meaning                                                              |
|------|----------------------------------------------------------------------|
| 1106 | `group permission deny` — home_id not visible to this key            |
| 1109 | `param illegal` — field missing, array where string expected, wrong casing |
| 1110 | `illegal param` — legacy variant; check required fields              |

**Timezone note**: the API can default to the home timezone, but callers
should still pass `timezone` when they already know it so day/month/year
boundaries are explicit. The CLI auto-fetches it from `home/station` when
omitted.

---

## 3. ✅ `POST /v1.0/end-user/energy/indicators/trend`

Same request body as `aggregate`, including the `timezone` enrichment rule.
Response returns a time series:

```json
{
  "result": [
    { "indicator": "ele_consumption_sol",
      "list": [
        { "date": "20260414", "value": {"Value": "0"} },
        { "date": "20260415", "value": {"Value": "0"} }
      ],
      "totalValue": {"Value": "0"},
      "unit": "kWh"
    }
  ],
  "success": true
}
```

Each `result[]` entry includes a per-indicator `totalValue: {"Value": "..."}`
(the window sum) alongside the per-bucket `list[]` — verified live.

---

## 4. ✅ `POST /v1.0/end-user/energy/indicators/top`

TopN by grouping dimension. Body shape **differs** from aggregate/trend.

| field            | required | notes                                                  |
|------------------|----------|--------------------------------------------------------|
| home_id          | yes      |                                                        |
| indicator_code   | yes      | **singular** string; multi-indicator is not supported  |
| group_by         | yes      | e.g. `device`, `space`, `usage` (≤64 chars)            |
| number           | yes      | integer in [1, 50]                                     |
| date_type        | yes      | same values as aggregate                               |
| begin_date       | yes      |                                                        |
| end_date         | yes      |                                                        |
| sort_type        | no       | `asc` / `desc` (lowercase); default `desc`             |
| time_aggr_type   | no       | uppercase enum                                         |
| device_aggr_type | no       | uppercase enum                                         |
| include_children | no       | boolean                                                |
| ext_condition    | no       | JSON string                                            |
| timezone         | no       | IANA tz; supply `home/station.time_zone_id` when known |
| options          | no       | JSON string, e.g. `{"scale":2}`                        |

Empty group returns `{"result": [], "success": true}` — not an error.

---

## 5. ✅ `POST /v1.0/end-user/energy/forecast`

Hourly produce + consumption forecast for the next ≤48 hours. Replaces the
legacy `GET /v1.0/end-user/energy/forecast/indicator`, which returns
`1108 uri path invalid` on the end-user gateway and should not be used.

**Body**

| field            | required | notes                                                              |
|------------------|----------|--------------------------------------------------------------------|
| home_id          | yes      | numeric string                                                     |
| indicator_codes  | yes      | **comma-separated string**; up to **2** codes. Whitelist: `ele_forecast_produce`, `ele_forecast_consumption`. Anything else → `1109 暂不支持的预测指标：xxx`. Sending more than 2 → `1109 indicator_codes 最多支持 2 个`. |
| begin_date       | yes      | `YYYYMMDDHH` (10 digits, hour granularity). Other lengths → `1109 begin_date 必须为 yyyyMMddHH 格式`. |
| end_date         | yes      | `YYYYMMDDHH`, inclusive. Window `(end_date - begin_date)` must be ≤48 h; longer windows do **not** error — the gateway returns `success=true` with an empty `list` and `totalValue=0`. |
| timezone         | no       | IANA tz; falls back to home default                                |
| use_cache        | no       | boolean. Default `true`. Pass `false` to request fresh forecast data when supported. |
| options          | no       | JSON string; the only field read today is `scale` (decimal places, server default 4). |

```json
{
  "home_id": "100200301",
  "indicator_codes": "ele_forecast_produce,ele_forecast_consumption",
  "begin_date": "2026042710",
  "end_date": "2026042809",
  "timezone": "Asia/Shanghai",
  "use_cache": true,
  "options": "{\"scale\":2}"
}
```

**Response shape** — one entry per requested indicator (`IndicatorDateDataItem`),
each with a per-hour `list[]`, an aggregate `totalValue`, and a `unit`:

```json
{
  "success": true,
  "result": [
    {
      "indicator": "ele_forecast_produce",
      "totalValue": { "Value": "12.34" },
      "unit": "kWh",
      "list": [
        { "date": "2026042710", "unit": "kWh",
          "value": { "Value": "0.00" } },
        { "date": "2026042711", "unit": "kWh",
          "value": { "Value": "0.00" } }
      ]
    },
    {
      "indicator": "ele_forecast_consumption",
      "totalValue": { "Value": "8.10" },
      "unit": "kWh",
      "list": [ /* one item per requested hour */ ]
    }
  ]
}
```

Field notes:

- Each `result[].list[].date` is `YYYYMMDDHH`. The `value` wrapper follows
  the same `{"Value": "..."}` pattern as the indicators family (capital
  `V`); cast cautiously to preserve precision.
- Result order is **not** guaranteed — route by the `indicator` field, not
  by index, the same way the rest of the family behaves.
- `totalValue` is the sum across the requested window for that indicator.

**Quirks worth knowing**

- **Windows entirely in the past return an empty list** with `success=true`
  and `totalValue=0`. The gateway silently drops past hours rather than
  returning an error. Anchor `begin_date` at the current hour or later in
  the home's local timezone.
- **`>48h` windows also return an empty list silently.** Treat 48h as a
  hard cap and split longer horizons into multiple calls.
- **Indicator-code whitelist is enforced server-side.** `ele_forecast_*`
  codes outside `produce` / `consumption` (e.g. `ele_forecast_xyz`) are
  rejected with `1109`. The CLI mirrors this whitelist locally.

**Typical error codes**

| code | message                                                              | usual cause |
|------|----------------------------------------------------------------------|-------------|
| 1106 | `group permission deny`                                              | `home_id` not visible to the API key |
| 1109 | `begin_date 必须为 yyyyMMddHH 格式` / `end_date ...`                  | wrong date length or non-digit |
| 1109 | `暂不支持的预测指标：<code>`                                          | indicator outside the whitelist |
| 1109 | `indicator_codes 最多支持 2 个`                                       | >2 codes in `indicator_codes` |
| 1108 | `uri path invalid`                                                   | legacy GET path or unavailable capability — use this POST endpoint when forecasting |

---

## 6. ✅ `POST /v1.0/end-user/energy/tariff/query`

| key        | required | notes                                   |
|------------|----------|-----------------------------------------|
| home_id    | yes      |                                         |
| date_type  | yes      | usually `hour`                          |
| begin_date | yes      |                                         |
| end_date   | yes      |                                         |
| direction  | no       | `IMPORT` / `EXPORT` on the wire; CLI accepts lowercase |
| timezone   | no       |                                         |

**Casing note** (verified live): unlike the snake_case data endpoints,
`tariff/query` returns a **camelCase object**. `result` carries supplier
metadata (`supplierName`, `supplierCode`, `priceType`, `connectionType`,
`tariffConfigId`, `direction`) and a `result.tariffList[]` array whose items
are `{ beginDate, endDate, currency, tariff, type, sourceFrom }`:

```json
{
  "result": {
    "supplierName": "OctopusEnergy",
    "priceType": 5,
    "direction": "IMPORT",
    "tariffList": [
      { "beginDate": "2026-04-21T00:00:00-06:00",
        "endDate": "2026-04-21T00:15:00-06:00",
        "currency": "EUR", "tariff": "0.15114",
        "type": "medium", "sourceFrom": "thirdParty" }
    ]
  },
  "success": true
}
```

`type` is the per-slot label (`high` / `medium` / `low`); `sourceFrom` marks
the data origin (e.g. `thirdParty`, `flatpeak`) for dynamic tariffs.
`beginDate` / `endDate` are ISO-8601 with the home's UTC offset.

---

## 7. ✅ `POST /v1.0/end-user/energy/tariff/label`

Returns the tariff thresholds for the home's current tariff schema. On the
current gateway probe, the response includes `highPriceLabelValue` and
`lowPriceLabelValue`; the per-slot `type` still comes from `tariff/query`.

| key       | required | notes                          |
|-----------|----------|--------------------------------|
| home_id   | yes      |                                |
| direction | no       | `IMPORT` / `EXPORT` on the wire |
| timezone  | no       | accepted by the current deployment |

---

## 8. ✅ 📘 🧩 `POST /v1.0/end-user/energy/home/flow`

Real-time home-level snapshot of PV / battery / grid / load / EVSE / heat
pump power plus SOC and device-level breakdowns.

Verified live on the end-user gateway.

> Path note: the Conow V1 plan doc called this `/conow/home/flow`, but the
> backend spec — and the real response bodies captured against live homes —
> expose it as `/home/flow` (no `/conow/` prefix). The CLI uses the latter.

**Body**

| field      | required | notes                                                 |
|------------|----------|-------------------------------------------------------|
| home_id    | yes      | numeric string                                        |
| scale      | no       | decimal places for power values (server default 4)    |
| last_mins  | no       | only use data points from the last N minutes         |

```json
{ "home_id": "100200302" }
```

**Response shape** (abridged example payload)

```jsonc
{
  "success": true,
  "result": {
    "grid_status": "off_grid",      // off_grid / grid_sale / grid_purchase
    "has_grid": true,               // grid-metering hardware present?
    "soc_count": 2,                 // how many batteries in this home
    "indicators": [
      {
        "indicator": "home_total_load_power",
        "total_value": "200",
        "value_item_list": [
          {
            "dev_id": "...",
            "dev_name": "CBE2000 Pro 3",
            "icon": "https://images.tuyacn.com/smart/icon/xxx.png",
            "target_indicator_code": "total_photovoltaic_power",
            "unit": "kW",
            "value": "901"
          }
        ]
      },
      { "indicator": "home_total_stack_power",       "total_value": "-1602", "value_item_list": [ /* ... */ ] },
      { "indicator": "home_total_grid_port_power",   "total_value": "0",     "value_item_list": [ /* ... */ ] },
      {
        "indicator": "soc",
        "total_value": "20.5",
        "value_item_list": [
          { "dev_id": "...", "target_indicator_code": "heap_soc", "unit": "%", "value": "41" }
        ]
      }
    ]
  }
}
```

Field semantics:

- `indicators[]` order is **not fixed** — route by the `indicator` field, not by index.
- `value_item_list[]` may be empty while `total_value` has a (calculated) value.
- `target_indicator_code` is the device-level raw indicator (no `home_total_` prefix).
- `soc` is its own entry (`indicator="soc"`); `total_value` is the multi-battery
  average in 0-100, individual items have `target_indicator_code="heap_soc"` and
  `unit="%"`.
- `soc_count` at the top level exists mainly to make multi-battery UIs simpler.

**Indicator codes in the `indicators[]` array**

| code                             | meaning                           | sign convention |
|----------------------------------|-----------------------------------|------------------|
| `home_total_photovoltaic_power`  | PV production power                | `+` = producing |
| `home_total_stack_power`         | battery pack power                 | `+` = discharging, `−` = charging |
| `home_total_grid_port_power`     | grid-tie power                     | `+` = importing (buy), `−` = exporting (sell) |
| `home_total_load_power`          | household consumption power        | `+` = consuming |
| `home_total_evse_power`          | EVSE (charger) power               | `+` = charging |
| `home_total_pump_power`          | heat pump power                    | `+` = running |
| `soc`                            | battery SOC (0-100, %)             | — |

When `grid_status="off_grid"`, `home_total_grid_port_power` is typically `0`.

**Telemetry-gated shape** (verified live): the rich fields above
(`grid_status`, `has_grid`, the `indicators[]` array) are present **only when
the home has live device telemetry**. A home with no reporting devices
returns just `{"soc_count": 0}` with `success=true` — no `indicators[]`, no
`grid_status`. When the snapshot is empty, fall back to a same-day
`indicators/aggregate` and label the answer as an aggregate, not real-time
power.

---

## 9. ✅ 📘 🧩 `POST /v1.0/end-user/energy/home/power-curve`

Home-level indicator time series. Richer request surface than
`indicators/trend`: supports sub-hour bucketing via `query_step`, a separate
`auto` fill-in mode, and a forecast toggle in `options`.

Verified live on the end-user gateway.

**Body**

| field             | required | notes                                                     |
|-------------------|----------|-----------------------------------------------------------|
| home_id           | yes      | numeric string                                            |
| indicator_codes   | yes      | **comma-separated string**, max 20 codes                  |
| begin_date        | yes      | format matches `date_type`                                 |
| end_date          | yes      | inclusive                                                 |
| date_type         | yes\*    | `quarter` / `hour` / `day` / `month` / `year`; bucketing granularity |
| timezone          | no       | IANA tz; defaults to home timezone                        |
| query_type        | no       | granularity helper (rarely needed)                        |
| query_step        | no       | data point step, e.g. `15m` / `1h` / `1d`                 |
| time_aggr_type    | no       | `SUM`/`AVG`/`MAX`/`MIN` (UPPERCASE)                       |
| device_aggr_type  | no       | same enum; e.g. `AVG` for SOC averaging across batteries  |
| auto              | no       | fill-in mode; server default `"3"`, business uses `"2"`   |
| options           | no       | JSON string; supports `{"scale":2,"queryPredict":1}`      |
| ext_condition     | no       | extension filter JSON                                     |

\* Optional in the raw API (omit → no bucketing), but the bundled CLI requires it.

Date format follows the same `date_type` table as the indicators family,
with one addition: **`hour` → `YYYYMMDDHH`** (only power-curve accepts it for
home-level data).

**Body example — SOC curve, 15-minute buckets, single day**

```jsonc
{
  "home_id": "100200302",
  "indicator_codes": "soc",
  "begin_date": "2026042100",
  "end_date": "2026042123",
  "date_type": "hour",
  "query_step": "15m",
  "device_aggr_type": "AVG",
  "auto": "2",
  "options": "{\"scale\":2}"
}
```

**Response shape**

```json
{
  "success": true,
  "result": [
    {
      "indicator": "soc",
      "list": [
        { "time": 1776700800000, "time_str": "202604210000", "date": "202604210000", "value": "27", "value_origin": 27, "type": "real" },
        { "time": 1776701700000, "time_str": "202604210015", "date": "202604210015", "value": "27", "value_origin": 27, "type": "real" }
      ]
    }
  ]
}
```

- `result[]` has one element per indicator in the request.
- `list[].type` is `real` or `forecast`. To get `forecast` points, pass
  `options` with `{"queryPredict":1}`.
- `value` is a **string**; each item also carries `value_origin`, the same
  number in **bare numeric** form (verified live). Prefer `value` for display
  precision and `value_origin` for arithmetic.
- A home with no telemetry for the window returns `"list": []` with
  `success=true` — not an error.

---

## 10. ✅ 📘 🧩 `POST /v1.0/end-user/energy/home/impact`

Economic + environmental aggregates for the home — revenue, production,
carbon reduction, tree equivalents, self-sufficiency split.

Verified live on the end-user gateway.

**Body**

| field       | required | notes                                                          |
|-------------|----------|----------------------------------------------------------------|
| home_id     | yes      | numeric string                                                 |
| phone_code  | **yes**  | **ISO 3166 alpha-2 country code** (e.g. `DE`, `US`, `CN`, `SE`, `JP`). Drives the carbon-reduction factor. This is **NOT** a phone dial code like `"86"`. It is **NOT validated** — a numeric dial code (e.g. `86`) is silently accepted (no `1109`) and quietly changes the carbon figure, so always pass the alpha-2 country code. |
| date_type   | yes      | `day` / `month` / `year`                                       |
| begin_date  | yes      | `YYYYMMDD` / `YYYYMM` / `YYYY`, no hyphens                      |
| end_date    | yes      | inclusive, same format                                         |
| timezone    | no       | IANA tz                                                        |
| options     | no       | JSON string; supports `{"scale":2}` for revenue precision      |

```json
{
  "home_id": "100200302",
  "phone_code": "DE",
  "date_type": "day",
  "begin_date": "20260421",
  "end_date": "20260421"
}
```

**Response shape** (example payload, Swedish home, `day` query)

```json
{
  "success": true,
  "result": {
    "revenue": {
      "total_ele_produce_cost": "0.03",
      "cost_unit": "SEK"
    },
    "energy_production": {
      "total_ele_produce": "2772",
      "ele_unit": "W"
    },
    "environmental_impact": {
      "carbon_reduction": "1552.3000000",
      "carbon_unit": "g",
      "sum_of_trees": 0
    },
    "self_sufficiency": {
      "self_suff_percent": "100",
      "pv_percent": "12",
      "grid_percent": "0",
      "battery_percent": "88"
    }
  }
}
```

Field notes:

- **Read both wrapped and bare forms** (the value wrapping is not uniform —
  verified live): `revenue.total_ele_produce_cost` and
  `environmental_impact.carbon_reduction` may come back **wrapped** as
  `{"Value": "..."}` (e.g. `"carbon_reduction": {"Value": ""}`,
  `"total_ele_produce_cost": {"Value": "0.00"}`) on some homes, but **bare
  strings** on others (`"carbon_reduction": "1552.3000000"`). Always handle
  both shapes. `energy_production.total_ele_produce` is a **bare number**
  (e.g. `0`), not wrapped.
- `revenue.cost_unit` is home-local (SEK / EUR / CNY / …).
- `energy_production.ele_unit` is **mislabeled `"W"`**, but
  `total_ele_produce` is an energy **total in Wh** (not power in watts).
  Divide by 1000 for **kWh** and report it as energy. Do not quote the raw
  number as watts just because `ele_unit` says `W`.
- `environmental_impact.carbon_reduction` is in **g**; divide by 1000 for kg.
  An empty `{"Value": ""}` means no carbon data for the window — do not coerce
  it to `0`.
- `sum_of_trees` is floor-rounded; short windows with low production may be `0`.
- `self_sufficiency` **may be returned empty (`{}`)** when the home has no
  self-sufficiency breakdown for the window. When it is populated,
  `pv_percent + battery_percent + grid_percent` and
  `self_suff_percent = pv_percent + battery_percent` are the intended
  relationships — but **do not assume the percents sum to 100** (rounding /
  partial data can break it), and skip the breakdown entirely when
  `self_sufficiency` is empty.
- The endpoint returns a single granularity per call — for multi-granularity
  reports (e.g. today + this-month), call it twice.

This is the data source for the V1 "省钱近似值" used by
`get_optimization_report`. Note that `total_ele_produce_cost` is *revenue from
PV*, NOT "saved money" — do not present it to end users as "you saved X".

---

## 11. ✅ 📘 🧩 `POST /v1.0/end-user/energy/home/indicators`

Home-scoped indicator dictionary. Returns the list of `{code, name}` you can
feed into the `indicator_codes` of `home/power-curve`.

Verified live on the end-user gateway.

**Body**: empty (no `home_id`, no params). Returns the same dictionary for
every caller.

```json
{}
```

**Response shape** (currently 7 entries on production)

```json
{
  "success": true,
  "result": [
    { "code": "home_total_photovoltaic_power", "name": "光伏发电功率" },
    { "code": "home_total_stack_power",        "name": "电池堆充放电功率" },
    { "code": "home_total_grid_port_power",    "name": "电网端口功率" },
    { "code": "home_total_load_power",         "name": "负载功率" },
    { "code": "soc",                           "name": "电池SOC" },
    { "code": "home_total_evse_power",         "name": "充电桩功率" },
    { "code": "home_total_pump_power",         "name": "热泵功率" }
  ]
}
```

Difference from the generic system dictionary:

- `GET /v1.0/end-user/energy/indicators` returns the cross-cutting code set
  (e.g. `ele_consumption_sol`, `ele_pv_produce`, …) used by the
  `indicators/*` family — mostly `ele_*` kWh / currency codes.
- `POST /v1.0/end-user/energy/home/indicators` returns the **home layer**
  codes (`home_total_*_power` plus `soc`) that plug into `home/power-curve`.
- The two dictionaries intentionally do not overlap; do not cross-feed codes
  (an `ele_consumption_sol` sent to `home/power-curve` is meaningless).

The home-level dictionary is effectively static on the server side
(constructed at startup), so it is safe to cache for the lifetime of a
session without worrying about per-home variance.

---

## 12. ✅ 📘 `POST /v1.0/end-user/energy/home/station`

Home station metadata: home name, location, country, timezone, capacity, owner
and service-provider fields. Use this endpoint as the source of truth for
timezone enrichment before statistics, curve, or impact calls.

**Body**

| field    | required | notes                                                        |
|----------|----------|--------------------------------------------------------------|
| home_id  | yes      | numeric string                                               |
| biz_data | no       | JSON string used by backend for image CDN domain replacement |

```json
{
  "home_id": "100200302"
}
```

**Response shape** (abridged)

```json
{
  "success": true,
  "result": {
    "group_id": "100200302",
    "group_name": "我的家",
    "station_name": "我的家",
    "lon": 18.0,
    "lat": 59.0,
    "country_code": "SE",
    "installed_capacity": "5.000",
    "energy_capacity": "10.000",
    "time_zone_id": "Europe/Stockholm",
    "time_zone_lang_name": "斯德哥尔摩 (UTC+02:00)",
    "country_code_lang_name": "瑞典"
  }
}
```

Field notes:

- `time_zone_id` is an IANA timezone. Copy it to `timezone` on
  `indicators/*`, `home/power-curve`, and `home/impact` calls when available.
- `time_zone_lang_name` includes the current UTC offset and DST status. Use it
  for display only; do not cache it as a fixed offset.
- `country_code` casing is **not guaranteed alpha-2** — live homes have
  returned **alpha-3** (e.g. `CHN`, verified live) as well as alpha-2 (`SE`).
  `home/impact --phone-code` requires ISO 3166 **alpha-2** (e.g. `CN`, `SE`),
  so **do not copy `country_code` verbatim** into `phone_code`; map / confirm
  it to alpha-2 first (e.g. `CHN` → `CN`).
- If the home has not created a station yet, the backend can still return
  fallback home info including `group_name`, coordinates, `country_code`, and
  `time_zone_id`.

---

## 13. `list_homes`

The default path `GET /v1.0/end-user/homes/all` is the **verified working
path** on the end-user gateway (returned 9 homes live). The CLI uses it by
default, so `list-homes` / auto-discovery work out of the box — callers do
**not** need to supply `home_id` explicitly under a standard deployment.

The CLI still accepts `--homes-path` / `CONOW_HOMES_PATH` for non-standard
deployments. If the default path ever returns `1108 uri path invalid` on a
custom gateway, set `CONOW_HOMES_PATH` (or `--homes-path`) to the list-homes
path your deployment provides.

Supplying `home_id` via `--home-id` or `CONOW_HOME_ID` remains a valid
shortcut to skip the lookup, but is optional on a standard gateway.
