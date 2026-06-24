# Conow Energy Skill Manifest

This package publishes **three** end-user skills: `conow-energy` (home-level
energy data — the focus of this manifest), `conow-device` (per-device
overview / model / control), and `conow-dispatch` (AI savings-mode dispatch
query / disable). This manifest is the implementation guide for the
**`conow-energy`** skill: it maps each home-energy intent to a concrete
endpoint (or an orchestration of CLI subcommands), and encodes the mandatory
**preflight** flow for `home_id` resolution shared across all three.

Use this file as a compact implementation guide for mapping user intent to
the bundled `conow-energy` CLI commands. For device and dispatch intents, see
the sibling skills (§1.1).

---

## 0. Preflight (must run before any energy skill)

```
用户说话
  ↓
是否涉及家庭数据? ── 否 ─→ 直接回答(静态问题,如"平台能查哪些指标")
  │
  是
  ↓
context.home_id 是否已有?
  ├─ 有  ─→ 直接调用对应能源 skill
  └─ 无  ─→ 调用公版 list_homes
            ├─ 1 个家庭  ─→ 自动选中,写入 context.home_id
            ├─ 多个家庭  ─→ 向用户追问"您问的是【家庭 A】还是【家庭 B】"
            └─ 0 个家庭  ─→ 返回"当前 API Key 未关联任何家庭,请检查授权"
```

For statistics-style requests, also carry `context.timezone` when known. If
the caller does not already have it, use `home/station.time_zone_id` after
resolving `home_id`; this keeps date windows aligned to the home rather than
the agent runtime locale.

Each skill `description` must embed the sentence:

> *Requires `home_id`. If not known, call `list_homes` first; auto-select when
> only one home exists, otherwise ask the user to disambiguate.*

Error code `1106 group permission deny` should be surfaced to the user as
something like:

> 当前 home_id 无法访问。可能是您已退出该家庭或尚未开通能源能力，
> 建议重新执行 `list_homes` 并选择正确的家庭。

---

## 1. conow-energy intent map

These are the internal **intent groups** the `conow-energy` skill answers (not
separate published packages — the package ships just three skills: energy /
device / dispatch). Each row maps a home-energy intent to its backing
endpoint(s) and CLI subcommand(s):

| # | intent_code              | 覆盖需求 | 实现来源               | 状态                       |
|---|--------------------------|----------|------------------------|----------------------------|
| 0 | `list_homes`             | 前置流程 | Tuya 公版              | 复用,不在本仓实现          |
| 1 | `get_energy_overview`    | S0-1     | `/home/flow` + `/home/power-curve` | Live on the end-user gateway |
| 2 | `get_energy_indicators`  | S0-4,S0-2部分 | `indicators/*` (4 个) | Live                       |
| 3 | `get_energy_forecast`    | S0-3     | `POST /forecast` (≤48h, hourly) | Live on the end-user gateway |
| 4 | `get_energy_tariff`      | S0-1,3,5 | `tariff/query` + `tariff/label` | Live on the gateway via POST JSON |
| 5 | `get_energy_advice`      | S0-5     | 规则编排                | 当前 API 不直接提供建议接口 |
| 6 | `get_optimization_report`| S0-6     | `/home/impact`          | 支持收益 / 自给率 / 碳减排；未优化基线暂不支持 |

S0-2 完整版(设备清单 + 告警)、S2/S3 均不在 V1。"电池 SOC / 光伏功率"这
类问题 V1 通过 `get_energy_indicators`(ele_store_percent)或 `get_energy_overview`
的 flow 节回答。

### 1.1 兄弟技能（本 manifest 不替代）

家庭 **能源指标** 仍由本目录 `conow-energy` + 本 manifest 描述；以下能力在独立 Cursor skill 中维护，避免与 `home_id` 查询语义混淆：

| 能力 | Skill 目录 | 说明 |
|------|------------|------|
| 单设备总览、公版物模型/控制、能源 `topo`/`protocol`/告警/设备层指标 | [`conow-device`](../../conow-device/SKILL.md) | 统一 CLI 自动识别是否能源设备 |
| 家庭 AI 节能调度 query/list/disable | [`conow-dispatch`](../../conow-dispatch/SKILL.md) | 以 `home_id` 为维度，写操作需确认 |

---

## 2. Per-skill manifest

### 2.1 `list_homes`

- **来源**: 复用 [tuya-smart-control](https://github.com/tuya/tuya-openclaw-skills/blob/master/tuya-smart-control/SKILL.md)
  `homes` 能力。本仓**不实现**,避免重复。
- **description** (给下游 Agent):
  > List the homes associated with the current end-user. Always call this
  > before any other conow-energy skill when `home_id` is not known. Returns
  > a list of `{home_id, name, role, ...}`.
- **在线下 CLI 里的对应命令**:
  ```bash
  conow_cli.py list-homes
  ```
  内置默认路径 `/v1.0/end-user/homes/all`,可通过
  `CONOW_HOMES_PATH` 覆盖。

### 2.2 `get_energy_indicators`

这是一个 **family skill**:AI 面对它看到 4 个动作,按自然语言意图选一个。

- **动作**:
  | 意图                     | 子接口                              | CLI 子命令            |
  |--------------------------|-------------------------------------|------------------------|
  | 查"有哪些指标"            | `GET /indicators`                   | `indicators-list`     |
  | 查"总量/累计"             | `POST /indicators/aggregate`        | `indicators-aggregate`|
  | 查"趋势/曲线"             | `POST /indicators/trend`            | `indicators-trend`    |
  | 查"排行/TOP N"            | `POST /indicators/top`              | `indicators-top`      |
- **required**: `home_id`, `indicator_codes`(除 `indicators-list`外), `date_type`, `begin_date`, `end_date`
- **optional**: `time_aggr_type`(sum/avg/max/min), `group_by`(device/space/usage,仅 top), `number`(1..50,仅 top), `sort_type`(asc/desc,仅 top), `timezone`
- **description**:
  > Query energy indicators for the home. Choose aggregate / trend / top
  > based on whether the user asks for a total, a time series, or a ranking.
  > Requires `home_id`. If not known, call `list_homes` first.
- **timezone**: 对 `aggregate` / `trend` / `top`，如果已经有家庭时区，必须在请求中带
  `timezone`。若没有，先通过 `POST /v1.0/end-user/energy/home/station` 取
  `result.time_zone_id`；取不到时再让服务端走默认时区，不要因为时区兜底失败而放弃
  主查询。离线 CLI 已内置该逻辑（显式 `--timezone` / `CONOW_TIMEZONE` 优先）。
- **家庭用电量 (默认 CONSUMPTION SOL 四指标)**: 用户问「家庭用电量 / 总用电 /
  用了多少电」时,**默认**一次请求拉齐 `ele_consumption_sol`(家庭总用电量)、
  `ele_consumption_from_pv_sol`(光伏/太阳)、`ele_consumption_from_battery_sol`
  (电池)、`ele_consumption_from_grid_sol`(电网)。与 `ele_usage`(设备/电表层)
  及 `ele_consumption`(无 `_sol`) **非同义**,勿混用。
- **家庭发电量 (默认 PRODUCE SOL 四指标)**: 用户问「家庭发电量 / 今天发了多少
  电 / 发的电去哪儿了」时,**默认**一次请求拉齐 `ele_produce`(家庭发电量)、
  `ele_produce_to_consumption_sol`(家庭负载)、`ele_produce_to_charge_sol`
  (电池)、`ele_produce_to_gridcn_sol`(公共电网)。在本网关上 `ele_produce` 是
  发电量的默认 code,`ele_pv_produce` 仅在用户明确要"光伏板口径"且已确认该
  home 填入此码时才用(大多数 home 该码返 `0.00`)。
- **双侧交叉校验**: 若同一次请求同时包含两套 SOL 四指标,
  `ele_consumption_from_pv_sol` 应 ≈ `ele_produce_to_consumption_sol`;偏差大于
  四舍五入量级时直接如实上报差值,不要挑一个数当答案。

### 2.3 `get_energy_forecast`  (Live on gateway)

- **endpoint**: `POST /v1.0/end-user/energy/forecast`
- **required**: `home_id`, `indicator_codes`（逗号分隔 String，**最多 2 个**，
  仅支持 `ele_forecast_produce`、`ele_forecast_consumption`），
  `begin_date`、`end_date`（`yyyyMMddHH` 10 位小时粒度）
- **optional**: `timezone`、`use_cache`（默认 `true`，需要刷新预测时设 `false`）、
  `options`（JSON String，目前只读 `scale`）
- **窗口约束**: `(end_date − begin_date) ≤ 48h`。超过 48h 服务端不报错，
  会静默回 `success=true` + 空 `list` + `totalValue=0`，调用方需要自己拆段。
  纯过去窗口同样会静默返空（forecast 服务会丢弃已经过去的小时），
  调用前把 `begin_date` 锚到家庭本地时区当前整点或之后。
- **响应**: `result[]` 每个元素对应一个指标，含 `list[]`（每小时一项）、
  `totalValue`、`unit`；不要按下标取，按 `indicator` 字段路由。
- **CLI**:
  ```bash
  # 默认两码（产生 + 消耗），未来 24 小时
  conow_cli.py forecast --home-id <HOME> \
    --begin-date <yyyyMMddHH, current hour or later> --end-date <same window, up to +48h>

  # 只查发电量，并请求新预测
  conow_cli.py forecast --home-id <HOME> \
    --indicator-code ele_forecast_produce \
    --begin-date <yyyyMMddHH, current hour or later> --end-date <same window, up to +48h> \
    --use-cache false
  ```
  CLI 在客户端就拒绝错误的小时格式 / 不支持的指标 / >2 码 / >48h 窗口。

### 2.4 `get_energy_tariff`

- **endpoints**: `POST /tariff/query`, `POST /tariff/label`
- **required**: `home_id`, `date_type`, `begin_date`, `end_date` (对 query);
  `home_id` (对 label)
- **optional**: `direction`(CLI 可传 `import`/`export`，wire value 为大写),
  `timezone`
- **用途**: query 出具体时段电价,label 出该家庭的 high/medium/low 阈值 → 两
  者配合才能判断"当前是不是低谷"。

### 2.5 `get_energy_overview`

`/home/flow` 与 `/home/power-curve` 已在 end-user 网关上可用。V1 内部可并行:
1. `/home/flow` (实时功率 + SOC + 设备级明细)
2. `/tariff/query` (当前小时) + `/tariff/label`
3. `/indicators/aggregate` (当日 CONSUMPTION SOL 四指标 + PRODUCE SOL 四指标 +
   `ele_purchase` / `ele_produce_gridcn` 等)

若某个家庭或网关暂不支持实时接口，AI 应降级为手动编排
`get_energy_indicators`(aggregate/trend) 回答"今天已经用了多少电/发了多少电"
这类问题,并说明这是聚合/曲线降级,不是实时 flow。

### 2.6 `get_energy_advice`  (规则建议)

当前 API 不直接提供建议接口。V1 规则版可基于:
1. `forecast`（POST，单次 ≤48h，hourly，`ele_forecast_produce` + `ele_forecast_consumption` 一次拉齐）
2. `tariff/query` + `tariff/label`
3. 扫描连续 `type=low` 的低谷窗口 → `tariff_low_window`
4. 扫描 `pv - consumption` 正值窗口 → `pv_surplus_window`

在交付前,AI 可以口头给建议("明天 14:00 前光伏一般最强"),**不要**伪造具体
kWh/省钱金额。

### 2.7 `get_optimization_report`  (V1 降级)

`/home/impact` 已在 end-user 网关上可用。V1 可直接包一层
`/home/impact`,映射 `revenue.total_ele_produce_cost`
→ `income`、`self_sufficiency.self_suff_percent` → `self_sufficiency_rate`、
`environmental_impact.carbon_reduction` → `carbon_reduction_kg`。
`saved_money` / `baseline_cost` / `optimized_cost` 三个字段统一返回 null 或
`"not_supported"`,并在响应里加 `disclaimer` 字段:

> V1 版本暂以家庭光伏收益作为省钱近似值;未接入未优化基线对比。

AI 在回答时必须**明说是估算**,不要把 `income` 说成"省了多少钱"。`/home/impact`
的 `phone_code` 参数是 **ISO 3166 alpha-2 国家码**(`DE`/`US`/`CN`/`SE`/…),
不是电话区号,由它决定碳排放因子。

---

## 3. Conow 家庭接口(5 个,V1 **不直接**暴露)

为了降低 AI 编排出错概率,下列 5 个接口在 V1 的 manifest 里**不作为独立
skill**,只作为 `get_energy_overview` / `get_optimization_report` 内部编排的
依赖，或作为统计类请求的时区/国家信息前置查询。

完整字段、响应示例、指标编码语义见
`references/api_reference.md` §8-§12。

| 内部接口                                      | 用途                      |
|-----------------------------------------------|---------------------------|
| `POST /v1.0/end-user/energy/home/flow`        | 实时功率流向 + SOC + 设备级明细 |
| `POST /v1.0/end-user/energy/home/power-curve` | 功率曲线(home 层指标,支持 15m/1h/1d 粒度) |
| `POST /v1.0/end-user/energy/home/impact`      | 收益 / 自给率 / 碳减排 / 植树量 |
| `POST /v1.0/end-user/energy/home/indicators`  | 家庭维度指标字典(静态,7 项) |
| `POST /v1.0/end-user/energy/home/station`     | 家庭 / 电站基础信息、`time_zone_id`、`country_code` |

> 路径注意:早期 V1 设计稿写成了 `/conow/home/*`,后端实际上线路径是
> `/home/*`(没有 `/conow/` 前缀)。`flow` / `power-curve` / `impact` /
> `indicators` 与 `station` 按家庭电站接口文档提供指标、时区和国家信息。
> 若某项能力不可用，向用户说明限制并使用可用的聚合数据回答。

---

## 4. 错误码 → 话术

| code | 话术                                                                 |
|------|----------------------------------------------------------------------|
| 1010 | "当前登录状态不对,请重新授权。"                                      |
| 1106 | "当前 home_id 无访问权限;建议重新 list_homes 后重试。"               |
| 1108 | "当前网关暂不支持该能力,可先用聚合/趋势数据回答。" |
| 1110 | "请求参数不完整,请补充 `{field}` 后重试。"(field 从 msg 里提取)    |
| 其他 | 按 msg 透出,不要捏造。                                               |

---

## 5. V1 **不覆盖**(等 V2)

- S0-2 完整版:设备清单 + 告警 → 已由兄弟 skill `conow-device`（end-user 网关 + 统一 CLI）承接；本 manifest 中的 `get_energy_indicators` 仍可作为家庭层降级
- S0-6 真实 baseline:需要 HEMS 未优化成本口径
- S2 控制(储能写 / 并网写)→ 等写接口
- S3 调度(`manage_optimization` / `preview_optimization_plan`)→ 由兄弟 skill `conow-dispatch` 承接
- 建议算法服务(替换 V1 规则版)
- 路由 / 审计 / 限流 / 风险分级 / 两步确认 → 等公版 skill 平台
