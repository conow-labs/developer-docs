# CONOW Developer Documentation

Open resources for developers and DIY users who want to monitor, control, and integrate CONOW energy storage products.

## Integration paths

Pick the path that fits your setup:

| Path | Best for | Connection | Where |
|------|----------|------------|-------|
| **Modbus RTU** | Local control, no cloud dependency, custom EMS | RS-485 (on-device) | [`modbus/`](modbus/) — in this repo |
| **Home Assistant** | Smart-home users who want dashboards & automations | Cloud (Tuya) | *Coming soon — stay tuned* |
| **Agent Skills** | AI agents (e.g. Claude) reading and controlling energy data | Cloud | [conow-labs/agent-skills](https://github.com/conow-labs/agent-skills) |

> A local Modbus-based Home Assistant integration is planned. Until then, the Home Assistant path above uses the cloud (Tuya) connection.

> ⚠️ Control registers and commands can change how your system charges, discharges, and feeds the grid. Read the product safety instructions before writing any control value.

## What's in this repo

| Directory | Description |
|-----------|-------------|
| [`modbus/`](modbus/) | Modbus RTU API references — register maps, data types, and frame examples |
| [`examples/`](examples/) | Code examples in Python, Node.js, etc. *(coming soon)* |

## Products covered

- **CBE2000 Pro** — Balcony solar storage system (all-in-one inverter + battery)
- **Lyra Series** — AC-coupled storage system (Lyra 2500 AC, Lyra 2500 Pro)
- **Atlas Series** — High-capacity storage system (Atlas 6000 AC and variants)

## Contributing

Found an error or want to add an integration guide? Open an [Issue](../../issues) or submit a Pull Request — contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Documentation is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).  
Code examples are licensed under [MIT](LICENSE).
