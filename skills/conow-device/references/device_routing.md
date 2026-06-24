# 设备路由与能源设备识别

## 目标

在 **同一把 `sk-`（`CONOW_API_KEY`）与同一网关** 上，对任意设备 `device_id`（CLI 参数仍用 `--dev-id`）：

- 能走 **能源设备增强** 的，就开放 `topo`、`protocol`、子设备物模型、告警、设备层指标等能力；
- 否则回退到 **涂鸦公版 end-user 设备** 的 `detail` / `model` / `shadow issue`。

AI 不手写分支逻辑，统一用 `conow_device_cli.py` 的 `detect` / `device-overview` / `device-control`。

## 启发式规则（脚本实现）

1. 请求 `GET /v1.0/end-user/energy/devices/topo?device_id=...`  
   - 若 `success: true` 且 `result` 非空（如子设备 map / list 有数据），记为**能源设备信号 +**。

2. 请求 `GET /v1.0/end-user/energy/devices/protocol?device_id=...`  
   - 若 `success: true` 且 `result` 内出现协议/厂商/能源类型等字段，记为**能源设备信号 +**。

3. 若 1 或 2 任一为真，则 `is_energy_device = true`，高层命令走能源分支。

4. 若两条均不满足（含能力不可用、或 `success: false`），则 `is_energy_device = false`，走公版 `.../devices/{id}/detail` 等。

5. 用户可用 `--force-route energy|public` 覆盖自动结果（已知设备类型时）。

## 公版控制载荷

`public-control` / `device-control` 公版分支将 `--properties` JSON 对象展开为：

```json
{
  "properties": [
    {"code": "switch_led", "value": true}
  ]
}
```

与 [tuya-openclaw tuya-smart-control](https://raw.githubusercontent.com/tuya/tuya-openclaw-skills/master/README_zh.md) 的语义一致。复杂类型、门锁、视频流等限制以公版文档为准。

## 能源 `properties` / `issue` 载荷

`properties` 与 `issue` 均使用：

- `device_id`：设备 id
- `energy_dev_id`：能源子设备 id

CLI 会优先使用显式 `--energy-dev-id`；若未提供，则先查 topo：

- 只有 1 个候选时自动补全；
- 若 topo 恰好是「1 个 `inverter` + 若干 `collection_stick`」，自动优先选择该 `inverter`；
- 多个候选时返回候选列表，要求显式选择，避免误打到错误子设备。

## 能源 `issue` 载荷

`energy-issue` / `device-control` 能源分支发送：

- `device_id`：设备 id  
- `energy_dev_id`：子设备/能源设备 id  
- `setting`：物模型层 setting 的 JSON 对象或数组（CLI 会归一化为 `{code,value}` 列表）

## 响应大小写 / 数据形状 / 分页的不对称（实测，务必注意）

同一把 `sk-` 在不同分支上的请求/响应约定并不一致，解析时不要假设统一：

1. **大小写不对称（能源分支）。** 能源 GET 的**请求参数**是 snake_case（`device_id`、`energy_dev_id`、`page_num`、`page_size`、`start_time`、`end_time`），但**响应字段**是 camelCase（`devId`、`energyDevId`、`protocolCode`、`pageNum`、`pageSize`、`hasNext`、`total`）。公版/通用分支的响应则是 snake_case（`device_id`、`page_no`、`product_name`、`firmware_version`）。读能源响应时按 camelCase 取键，读公版响应时按 snake_case 取键。

2. **`properties` 形状不对称。**
   - **公版**（`detail` / `device-overview` 公版分支）：`result.properties` 是一个 **对象 map** `code → value`，且是**原生类型**（实测 `{"switch_1": false, "relay_status": "off", "cur_power": 0}`）。直接按 code 取值。
   - **能源**（`energy-properties` / `device-overview` 能源分支）：`result` 是一个 **数组**，元素为 `{"code","time","value"}`，且 `value` 一律是 **String**（实测 `{"code":"battery_capacity","time":...,"value":"0.8"}`、布尔为 `"false"`）。需要自行把字符串转成数字/布尔。

3. **分页参数不对称。** 家庭设备清单 `list-devices --home-id` 用 `page_no`/`page_size`；能源告警 `energy-alarms` 用 `page_num`/`page_size`。CLI 已分别用 `--page-no` 和 `--page-num` 暴露，调用时别混用。

4. **`energy-alarms --weight` 语义。** 默认 `0`。实测 `weight=0` 返回正常 `{data,total,hasNext,pageNum,pageSize}` 信封且未被后端拒绝，可视为「不限严重度（全部）」而非某一严重度档位；不会因默认值悄悄收窄告警范围。需要特定严重度时显式传非零 `--weight`。

5. **`device-overview` 能源分支不含告警。** 它聚合 `topo + protocol + indicators + properties`（当前值），不含 alarms；告警单独用 `energy-alarms` 查询。

## 与家庭 ID 的关系

公版与能源单设备接口均以设备 id 为主键；账号/家庭设备清单走公版枚举接口：

- 账号级：`GET /v1.0/end-user/devices/all`
- 家庭级：`GET /v1.0/end-user/homes/{home_id}/devices`

CLI 封装为：

```bash
python3 {baseDir}/scripts/conow_device_cli.py list-homes
python3 {baseDir}/scripts/conow_device_cli.py resolve-home --home-name "My Home"
python3 {baseDir}/scripts/conow_device_cli.py list-devices --summary-only
python3 {baseDir}/scripts/conow_device_cli.py list-devices --home-id <HOME_ID> --summary-only
```

如果用户只给家庭名，先用 `resolve-home --home-name ...` 解析对应的数字 `home_id`；如果返回多个候选，让用户按名称选择，再调用家庭级设备清单。不要把 `/v1.0/end-user/devices` 或 `/v1.0/end-user/devices/list` 当作枚举接口；在当前网关上这些路径会返回 `1108 uri path invalid`。
