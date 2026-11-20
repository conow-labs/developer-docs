# Modbus API References (RTU and TCP)

Local communication guides for CONOW devices. For other integration paths (Home Assistant Local, Home Assistant, Agent Skills), see the [main README](../README.md#integration-paths).

| File | Product | Protocol | Firmware |
|------|---------|----------|----------|
| [balcony-solar-storage.md](balcony-solar-storage.md) | Balcony Solar Storage (CBE Series, Lyra Series, Atlas Series) | Modbus RTU | **below the per-model v2 minimum** (v1 register map) |
| [balcony-solar-storage-v2.md](balcony-solar-storage-v2.md) | Balcony Solar Storage (CBE Series, Lyra Series, Atlas Series) | Modbus RTU / TCP | **at or above the per-model v2 minimum** (v2 register map) |

> [!NOTE]
> Both guides are available in four languages — use the language links at the top of each guide:
> - v1: [简体中文](balcony-solar-storage.zh-CN.md) · [Deutsch](balcony-solar-storage.de.md) · [Nederlands](balcony-solar-storage.nl.md)
> - v2: [简体中文](balcony-solar-storage-v2.zh-CN.md) · [Deutsch](balcony-solar-storage-v2.de.md) · [Nederlands](balcony-solar-storage-v2.nl.md)

> [!NOTE]
> Each English guide also has a derived machine-readable register list next to it (`balcony-solar-storage-v2.registers.csv`, `balcony-solar-storage.registers.csv`) — regenerate them with `python3 scripts/gen_registers_csv.py` from the repo root after editing the register tables.

> [!WARNING]
> The v1 and v2 register maps are **not interchangeable**. The v2 minimum firmware version differs per model — **Lyra Series 1.01.16, CBE2000 Pro 1.02.18, Atlas 6000 AC 1.01.09**; firmware below these versions uses the v1 map. Run the firmware version check in [Quick Start](#quick-start) before reading or writing any register beyond the basic link check.

## Prerequisites

Before using the Modbus interface, ensure the following:

**1. Device is activated**

The device must have been commissioned in the **CONOW ECO App** and have been online at least once — a factory-fresh, never-activated device does not respond to any request on the RS-485 interface.

**2. The Modbus service is enabled in the App**

Depending on your App version, use one of the following:

- **Option A (older App versions):** In the **Devices** tab, enter the device panel → **Settings → Operation Mode** → select **DIY Mode**.
- **Option B (current App versions):** In the **Devices** tab, enter the device panel → **Settings** → toggle on **Enable Modbus service**.

The RS-485 interface will not respond to any Modbus commands until one of these is enabled.

**3. One master writes at a time**

Issue write commands from a single master at a time. On v2 firmware this is the RTU/TCP write-priority rule — see *Concurrent RTU and TCP (write priority)* in the v2 guide.

These prerequisites apply to both register maps. v2 firmware additionally offers Modbus TCP over the device's Ethernet port (default port 502, dynamic 8-character hexadecimal verification code — see the v2 document).

## Quick Start

Work through the steps in order: establish the link first, then check the firmware version.

1. **Confirm your model and access method** — see the table above. v2 firmware offers RS-485 (RTU) and Ethernet (TCP); v1 firmware supports RS-485 only.
2. **Enable the Modbus service in the App** — see [Prerequisites](#prerequisites).
3. **Connect**, following the path for your access method:

   - **RS-485 (RTU):** connect an RS-485 to USB adapter between your host and the device RS-485 port, then configure the serial parameters: **38400 baud, 8N1, device address 0xA0**.
   - **Ethernet (TCP, v2 firmware):** connect the device Ethernet port to your network, get the device IP address, and complete the TCP verification (default port 502, dynamic 8-character hexadecimal verification code — see the v2 document).

4. **Read a known status register** with FC 0x03 to confirm the link works — for example system SoC at 10003 (0x2713), which sits at the same address with the same meaning on both the v1 and v2 maps.
5. **Check the firmware version** — read the firmware-version registers 10062–10063 (start 10062, 0x274E, quantity 2) with FC 0x03. A valid response — any data, including `0x0000 0x0000` — means the firmware implements this register range, so it is at or above the per-model v2 minimum: continue with the v2 guide. No reply, a timeout, or a Modbus exception means the range is not implemented, so the firmware is below the v2 minimum: use the v1 guide instead.

See the product-specific guide for register maps and frame examples.
