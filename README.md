# CONOW Developer Documentation

Open resources for developers and DIY users who want to monitor, control, and integrate CONOW energy storage products.

Language / 语言 / Sprache / Taal: **English** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [Nederlands](README.nl.md)

## Updates

- **2026-11-20**
  - Added the v2 firmware register map: Modbus TCP direct access, protocol registers 9984–9986, the full 10100–10190 control range, and exception-code tables.
  - Added more languages: Chinese, German, and Dutch editions of the README and both register maps.

## Integration paths

Pick the path that fits your setup:

| Path | Best for | Connection | Where |
|------|----------|------------|-------|
| **Modbus RTU / TCP** | Local control, no cloud dependency, custom EMS | RS-485 / Ethernet (on-device) | [`modbus/`](modbus/) — in this repo |
| **Home Assistant Local** | Home Assistant users who want local CONOW energy entities and automations without cloud dependency | RS-485 / Modbus RTU | [conow-labs/home-assistant-local](https://github.com/conow-labs/home-assistant-local) |
| **Home Assistant** | Smart-home users who want dashboards, automations, and CONOW energy entities | Cloud (Tuya) | [conow-labs/home-assistant](https://github.com/conow-labs/home-assistant) |
| **Agent Skills** | AI agents (for example Claude) reading and controlling energy data | Cloud | [conow-labs/agent-skills](https://github.com/conow-labs/agent-skills) |

> [!WARNING]
> Control registers and commands can change how your system charges, discharges, and feeds the grid. Read the product safety instructions before writing any control value.

## What's in this repo

| Directory | Description |
|-----------|-------------|
| [`modbus/`](modbus/) | Modbus API references — register maps per firmware version, data types, and frame examples (RTU; TCP on v2 firmware) |

## Products covered

- **CBE Series** — All-in-one balcony solar storage system (CBE2000 Pro)
- **Lyra Series** — AC-coupled storage system (Lyra 2500 AC, Lyra 2500 Pro)
- **Atlas Series** — High-capacity storage system (Atlas 6000 AC)

## Modbus register maps by firmware version

**Prerequisites for Modbus access:** the device must have been commissioned in the **CONOW ECO app** and have been online at least once — a factory-fresh, never-activated device does not respond to any request on the RS-485 interface; in the app, go to *Devices → your device → Settings* and turn on *Enable Modbus service* — on older app versions use *Settings → Operation Mode → DIY Mode* instead; keep writes to a single master at a time.

The Modbus register layout changed with the v2 firmware — the two maps below are **not interchangeable**. Check your firmware version first, then use the matching reference:

| Document | Firmware | Scope |
|----------|----------|-------|
| [balcony-solar-storage-v2.md](modbus/balcony-solar-storage-v2.md) | **at or above the v2 minimum** (Lyra 1.01.16 · CBE2000 Pro 1.02.17 · Atlas 1.01.08) | Monitoring 10000–10081 · Control 10100–10190 · Protocol 9984–9986 |
| [balcony-solar-storage.md](modbus/balcony-solar-storage.md) | below the v2 minimum (legacy) | Monitoring 10000–10036 · Control 10100–10107 |

**Version check:** read the firmware-version registers 10062–10063 (start 10062, 0x274E, quantity 2) with FC 0x03.  
If the device answers, the firmware implements this register range and is at or above the v2 minimum — use the v2 protocol document.  
If there is no reply, a timeout, or a Modbus exception, the register range is not implemented and the firmware is below the v2 minimum — use the v1 protocol document.  

New firmware also supports **direct Modbus TCP over the all-in-one unit's Ethernet port** (port 502): after connecting, write the 8-character hexadecimal dynamic verification code obtained from the CONOW App device details page (refreshed every 120 seconds) to registers 9985–9986 as a uint32 to complete verification; only then are reads and writes possible. RTU over RS-485 (including TCP through an RS-485-to-Ethernet gateway) needs no verification code.

## Contributing

Found an error or want to suggest an integration guide? Open an [Issue](../../issues). This documentation is maintained by the CONOW documentation team, and updates are made by the maintainers. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Contact

Questions or feedback? Reach the CONOW documentation team by email at [support@conow.com](mailto:support@conow.com).

## License

Documentation is licensed under [CC BY 4.0](LICENSE-docs) — canonical text at [creativecommons.org](https://creativecommons.org/licenses/by/4.0/).  
Code examples are licensed under MIT ([LICENSE](LICENSE)).
