# CONOW Developer Docs（简体中文）

**CONOW 户用储能与阳台光伏储能产品的开放协议参考与集成指南。**

语言 / Language / Sprache / Taal: [English](README.md) · **简体中文** · [Deutsch](README.de.md) · [Nederlands](README.nl.md)

---

## 更新日志

- **2026-11-20**
  - 新增 v2 固件寄存器表：一体机 Modbus TCP 直连、协议寄存器 9984–9986、10100–10190 完整控制区间与异常码自查表。
  - 新增其他语种：README 与两份寄存器表的中文、德语、荷兰语版本。

## 集成路径

根据你的部署场景选择路径：

| 方式 | 适用场景 | 连接 | 位置 |
|------|----------|------|------|
| **Modbus RTU / TCP** | 本地控制、不依赖云端、自定义 EMS | RS-485 / 以太网（一体机） | [`modbus/`](modbus/) — 本仓库 |
| **Home Assistant 本地集成** | 想在 Home Assistant 中获得本地 CONOW 能源实体与自动化、不依赖云端的用户 | RS-485 / Modbus RTU | [conow-labs/home-assistant-local](https://github.com/conow-labs/home-assistant-local) |
| **Home Assistant 云端集成** | 想要仪表盘、自动化与 CONOW 能源实体的智能家居用户 | 云端（Tuya） | [conow-labs/home-assistant](https://github.com/conow-labs/home-assistant) |
| **Agent Skills** | 读取与控制能源数据的 AI 智能体（例如 Claude） | 云端 | [conow-labs/agent-skills](https://github.com/conow-labs/agent-skills) |

> [!WARNING]
> 控制寄存器与指令会改变系统的充电、放电与向电网馈电行为。写入任何控制值之前，请先阅读产品安全说明。

## 仓库内容

| 目录 | 说明 |
|------|------|
| [`modbus/`](modbus/) | Modbus API 参考——按固件版本的寄存器表、数据类型与帧示例（RTU；v2 固件支持 TCP） |

## 支持产品

- **CBE 系列** — 一体式阳台光伏储能系统（CBE2000 Pro）
- **Lyra 系列** — 交流耦合储能系统（Lyra 2500 AC、Lyra 2500 Pro）
- **Atlas 系列** — 大容量储能系统（Atlas 6000 AC）

## 固件版本与寄存器文档（重要）

使用 Modbus 的前提：设备必须已在 **CONOW ECO App** 中完成调试并至少上线一次——出厂未激活、从未上线的设备，RS-485 接口不响应任何请求；在 App 的 *设备 → 你的设备 → 设置* 中开启 *启用 Modbus 服务*（旧版 App 无此开关时，改用 *设置 → 工作模式 → DIY 模式*）；同一时刻只由一个主站下发写指令。

Modbus 寄存器表自 **v2 固件**起分为两版，互相不兼容，先检查固件版本再使用：

| 文档 | 适用固件 | 寄存器范围 |
| --- | --- | --- |
| [balcony-solar-storage-v2.zh-CN.md](modbus/balcony-solar-storage-v2.zh-CN.md) | **达到 v2 最低版本及以上**（Lyra 1.01.16 · CBE2000 Pro 1.02.18 · Atlas 1.01.08） | 监控 10000–10081 · 控制 10100–10190 · 协议 9984–9986 |
| [balcony-solar-storage.zh-CN.md](modbus/balcony-solar-storage.zh-CN.md) | 低于 v2 最低版本（旧版） | 监控 10000–10036 · 控制 10100–10107 |

**版本检查**：用 FC 0x03 读取固件版本寄存器 10062–10063（起始 10062，0x274E，数量 2）。  
有应答——固件实现了该寄存器区间，达到 v2 最低版本，请使用 v2 协议文档；  
无应答、超时或返回异常——该寄存器区间未实现，固件低于 v2 最低版本，请使用 v1 协议文档。  

新固件还支持一体机**以太网口 Modbus TCP 直连**（端口 502）：连接后需将通过 CONOW App 设备详情页获取的 8 位十六进制动态验证码（每 120 秒刷新）按 uint32 写入寄存器 9985–9986 完成验证，方可读写；RS-485 上的 RTU（含经 RS-485 转以太网网关的 TCP）无需验证码。

## 贡献指南

发现错误，或希望新增集成指南？欢迎提交 [Issue](../../issues)。文档由 CONOW 文档团队维护，更新由维护者完成。规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 联系我们

有问题或反馈？欢迎发邮件联系 CONOW 文档团队：[support@conow.com](mailto:support@conow.com)。

## 许可证

文档采用 [CC BY 4.0](LICENSE-docs)（官方文本见 [creativecommons.org](https://creativecommons.org/licenses/by/4.0/)），代码采用 MIT（[LICENSE](LICENSE)）。
