# Modbus Integration Guide — Balcony Solar Storage (V2 Register Map)

> [!IMPORTANT]
> **Applies to:** devices whose firmware responds at the firmware-version
> register 10062–10063 (see [Firmware version check](#firmware-version-check)).
> These are the **v2 register addresses** (minimum firmware version per model:
> Lyra Series 1.01.16, CBE2000 Pro 1.02.18, Atlas 6000 AC 1.01.09). Devices on
> firmware below the versions above: use
> [balcony-solar-storage.md](balcony-solar-storage.md) (v1 register map).

Languages / 语言 / Sprachen / Talen: **English** · [简体中文](balcony-solar-storage-v2.zh-CN.md) · [Deutsch](balcony-solar-storage-v2.de.md) · [Nederlands](balcony-solar-storage-v2.nl.md)

---

## Contents

- [1 Overview](#1-overview)
  - [Firmware version check](#firmware-version-check)
  - [Migrating from v1](#migrating-from-v1)
  - [Transport and connection parameters](#transport-and-connection-parameters)
  - [Verification code (Modbus TCP direct, all-in-one machines)](#verification-code-modbus-tcp-direct-all-in-one-machines)
  - [Concurrent RTU and TCP (write priority)](#concurrent-rtu-and-tcp-write-priority)
  - [Hardware wiring](#hardware-wiring)
  - [Prerequisites](#prerequisites)
- [2 Data types](#2-data-types)
- [3 Register map](#3-register-map)
  - [3.1 Real-time monitoring (10000–10011)](#31-real-time-monitoring-1000010011)
  - [3.2 Detailed monitoring (10012–10043)](#32-detailed-monitoring-1001210043)
  - [3.3 Operating parameters and device info (10044–10063)](#33-operating-parameters-and-device-info-1004410063)
  - [3.4 Lifetime energy counters (10064–10081)](#34-lifetime-energy-counters-1006410081)
  - [3.5 Control — power and SoC settings (10100–10102)](#35-control--power-and-soc-settings-1010010102)
  - [3.6 Control — real-time force charge/discharge (10103–10106)](#36-control--real-time-force-chargedischarge-1010310106)
  - [3.7 Control — work strategy (10107–10114)](#37-control--work-strategy-1010710114)
  - [3.8 Control — generator and digital outputs (10115–10122)](#38-control--generator-and-digital-outputs-1011510122)
  - [3.9 Control — base load (10123–10148)](#39-control--base-load-1012310148)
  - [3.10 Control — manual charge/discharge (TOU) schedule (10149–10189)](#310-control--manual-chargedischarge-tou-schedule-1014910189)
  - [3.11 Control — time calibration (10190)](#311-control--time-calibration-10190)
  - [3.12 Protocol registers (9984–9986)](#312-protocol-registers-99849986)
- [4 Frame examples](#4-frame-examples)
  - [Modbus TCP framing (MBAP)](#modbus-tcp-framing-mbap)
  - [Quick test from the command line](#quick-test-from-the-command-line)
- [5 Important notes](#5-important-notes)
- [6 Troubleshooting](#6-troubleshooting)
  - [6.1 Modbus exception codes](#61-modbus-exception-codes)
  - [6.2 Device fault code (alarm bitmap, 10001–10002)](#62-device-fault-code-alarm-bitmap-1000110002)

---

## 1 Overview

This guide documents the **Modbus RTU / TCP interface of CONOW balcony solar
storage and all-in-one energy devices using the v2 register map** — CBE
Series (CBE2000 Pro), Lyra Series (Lyra 2500 AC, Lyra 2500 Pro) and Atlas Series
(Atlas 6000 AC).

Compared with the [v1 map](balcony-solar-storage.md), the v2 firmware brings:

- A monitoring area (10000–10081): CT/meter data, per-phase grid power,
  per-string PV voltage/current/energy, battery limits reported by the device,
  SOH, serial number, and firmware version.
- A control area (10100–10190): work strategies, work mode, reverse-power
  limiting, Modbus timeout, base-load schedule, a manual charge/discharge (TOU)
  schedule with up to 8 slots each, and a time-of-day calibration register.
- **Direct Modbus TCP** on all-in-one machines (port 502) protected by a
  **dynamic verification code**, with RTU and TCP usable at the same time under
  an RTU-priority write-arbitration rule.
- **Atomic group writes** — several control values must be written together in
  one FC 0x10 frame.

### Firmware version check

The two register maps are **mutually exclusive**: a device answers either the v1 addresses or the v2 addresses. The minimum firmware version that supports the v2 register map, per model:

| Model | Minimum firmware |
| --- | --- |
| Lyra Series | 1.01.16 |
| CBE2000 Pro | 1.02.18 |
| Atlas 6000 AC | 1.01.09 |

Firmware below the versions in the table uses the v1 register addresses by default. When you are not sure which register-address version to use, check as follows after connecting:

1. Read the firmware-version field **10062 (0x274E), quantity 2** (10062–10063) with FC 0x03.
2. Pick the guide by the response:

   - **The device answers** — the firmware already supports this register range: the firmware is at or above the version listed in the table and the device uses the v2 register map. Stay with this guide.
   - **No reply, a timeout, or a Modbus exception** — the firmware does not support this register range: the firmware is below the version listed in the table. Switch to [balcony-solar-storage.md](balcony-solar-storage.md).

Notes:

- The firmware-version field (10062–10063, U16[2] ASCII) **does not answer
  single-register reads** — request both registers in one frame.
- The serial-number field (10054–10061, U16[8] ASCII) has the same
  restriction: read all 8 registers in one request.

### Migrating from v1

Control addresses moved between the maps — re-map an existing v1 integration before writing:

| Function | v1 | v2 |
| --- | --- | --- |
| AC charge power limit | 10100 | 10100 — unchanged |
| Discharge power limit | 10101 | 10101 — unchanged |
| Backup SoC | 10102 | 10102 — unchanged |
| Charge/discharge direction | 10105 | 10103 |
| Target charge/discharge power | 10106 | 10104 |
| Charge/discharge cutoff SoC | 10107 | 10105 |

The v1 sequential write rule (10106 → 10105 → 10107 with FC 0x06) does **not** apply on v2: registers 10103–10106 are written as one atomic FC 0x10 group (only direction = 3 accepts a single-register write).

The v1 off-grid output switch (10103) and PV curtailment switch (10104) have no v2 counterpart at these addresses — 10103/10104 are the direction and power registers there; re-check the control tables before migrating those functions.

The monitoring registers were regrouped as well — verify every address against the v2 tables before polling.

Grid Active Power sign conventions also changed: on v1 the CBE2000 Pro reports positive as feed-in and negative as import while Lyra / Atlas report positive as import and negative as feed-in; on v2 all models report positive as importing from the grid and negative as feeding into it (10006, 10013).

### Transport and connection parameters

| Parameter | Value |
| --- | --- |
| Transport | RS-485 Modbus RTU, or Modbus TCP (all-in-one machines, TCP port **502**) |
| Serial parameters (RTU) | **38400** baud, 8 data bits, no parity, 1 stop bit (8N1) |
| Default slave / unit ID | **160 (0xA0)** |
| Unit-ID range | 128–176 (0x80–0xB0); the ID is readable and writable at register **9984 (0x2700)**; changing it does not require repeating the TCP verification |
| Function codes | 0x03 read · 0x06 write single · 0x10 write multiple |
| Read size limit | one FC 0x03 request serves at most **127** registers; a longer request gets no reply. The Modbus specification caps reads at 125 registers — design for 125 or fewer |

### Verification code (Modbus TCP direct, all-in-one machines)

**Modbus RTU needs no verification code; direct Modbus TCP requires the TCP
switch to be enabled in the App and verification to be completed.** After
connecting over TCP, write the 8-character hexadecimal verification code
(available on the device details page in the CONOW App) to the device:

- Write it as a **uint32** to holding registers **9985–9986 (0x2701–0x2702)**,
  high word first.
- The code is **dynamic and refreshes every 120 seconds** until
  verification succeeds; after that it stops refreshing. If the device rejects
  the code, read the new code from the App and write it again.
- **Verification lockout:** after 5 consecutive verification failures within
  5 minutes, TCP verification locks for 5 minutes — while locked, verification
  cannot complete and TCP reads and writes are answered with exception 0x02
  (reading the unit-ID register 9984 is the only exception); wait for the
  lockout to end, then read a fresh code from the App and write it again.
- Verification has to be repeated after the Modbus switch is re-enabled in the
  App, after the adapter's MAC address changes, or after a manual refresh.
- The device asks for verification by answering requests with a **Modbus
  exception** — a connected but unverified request gets a verification error,
  while an unconnected endpoint stays silent; do not mix up the two cases. Once
  a request is answered normally, the code is **not** sent again on every poll —
  write it only when challenged, and after a code change.

RTU over RS-485 (and Modbus TCP through an RS-485-to-Ethernet gateway) needs
no verification code.

### Concurrent RTU and TCP (write priority)

The App exposes **independent RTU and TCP switches**, and both channels may be
enabled at the same time. RTU reads (FC 0x03) work directly; TCP reads and
writes require the 9985–9986 verification first. Write frames (FC 0x06 /
0x10) follow a **single-writer rule with RTU priority**:

- While RTU holds write permission — any valid write frame inside the watchdog
  window at 10114 — verified TCP writes are rejected without acknowledgment and
  without execution. Verified TCP reads keep working.
- When the RTU link drops or the RTU side stays silent past the 10114
  timeout, write permission is released and verified TCP writes take effect. Any new RTU write frame
  immediately reclaims write permission; TCP has no path to preempt RTU.
- Verification (9985–9986) is a prerequisite for TCP reads and
  writes, not a way to acquire write permission — the two are independent.

Run only one writing master at a time. A TCP write answered with exception
0x86 (FC 0x06) or 0x90 (FC 0x10) is expected write-priority behavior, not a
link fault. Enable one control method, as your actual needs require.

### Hardware wiring

Wiring is identical to the v1 guide — see
[Hardware interface](balcony-solar-storage.md#12-hardware-interface) there for
the terminal pinouts and wiring diagrams.

### Prerequisites

The device must have been commissioned in the **CONOW ECO app** and have been
online at least once — a factory-fresh, never-activated device does not respond
to any request on the RS-485 interface.

1. In the app, go to *Devices → your device → Settings* and turn on *Enable
   Modbus service*; for direct TCP, also turn on the TCP switch. On older app
   versions the switch is absent — use *Settings → Operation Mode* and select
   *DIY Mode* instead.
2. Keep writes to a single master at a time — see
   [Concurrent RTU and TCP](#concurrent-rtu-and-tcp-write-priority).

---

## 2 Data types

| Type | Encoding |
| --- | --- |
| `uint16` | 1 register, unsigned |
| `int16` | 1 register, two's complement; sign per register description |
| `uint32` | 2 registers, **big-endian, high word first** — `value = (reg[n] << 16) \| reg[n+1]` |
| `string` | U16 array, 2 ASCII characters per register (high byte first), padded with 0x00 |
| `hhmm` time | 1 register: high byte = hour, low byte = minute (for example, `06:30` → `0x06 0x1E` → `0x061E` = 1566) |
| Scale | physical = raw × scale (scale 1 unless noted) |
| Enums / booleans | per-register value tables below |

---

## 3 Register map

Three areas, non-contiguous:

| Area | Registers | Access |
| --- | --- | --- |
| Monitoring | **10000–10081** (0x2710–0x2761) | read-only, FC 0x03 |
| Control | **10100–10190** (0x2774–0x27CE) | read FC 0x03 · write FC 0x06 / 0x10 — except 10103–10106: one atomic FC 0x10 group write only (direction = 3 also accepts FC 0x06) |
| Protocol | 9984 (unit ID, R/W) · 9985–9986 (verification code, WO) | see 3.12; workflow in the sections above |

Unlike v1 firmware (which silently drops single reads spanning 38 registers or more),
v2 firmware serves full-area reads — the reference Home Assistant integration
polls the whole monitoring area (82 registers) and the whole control area (91
registers) in one FC 0x03 request each. If your gateway or tool has trouble
with long frames, split reads at the group boundaries below.

### 3.1 Real-time monitoring (10000–10011)

| Register | Hex | Name | Type | Unit | Scale | Remarks |
| --- | --- | --- | --- | --- | --- | --- |
| 10000 | 0x2710 | System Status | uint16 | — | — | bit field — see the bit table below |
| 10001–10002 | 0x2711 | Device Fault Code | uint32 | — | — | [6.2 alarm bitmap](#62-device-fault-code-alarm-bitmap-1000110002); read 10001–10002 together |
| 10003 | 0x2713 | System SoC | uint16 | % | 1 | 0–100 |
| 10004 | 0x2714 | Meter Connection State | enum | — | — | 0 = paired and connected · 1 = unpaired and not connected · 2 = paired, not connected |
| 10005 | 0x2715 | Meter Total Power | int16 | W | 1 | Positive = importing from grid; negative = feeding into grid |
| 10006 | 0x2716 | Grid Active Power | int16 | W | 1 | Positive = importing from grid / battery charging; negative = feeding into grid / battery discharging |
| 10007 | 0x2717 | PV Total Power | uint16 | W | 1 | — |
| 10008 | 0x2718 | Battery Work State | enum | — | — | 0 = idle · 1 = charging · 2 = discharging; reports the actual state, not the command echo |
| 10009 | 0x2719 | Battery Power | int16 | W | 1 | Positive = charging; negative = discharging |
| 10010 | 0x271A | Bypass Switch State | enum | — | — | 0 = off · 1 = on |
| 10011 | 0x271B | Bypass Power | int16 | W | 1 | Positive = discharging to bypass; negative = charging from bypass |

**System status (10000) bit field** — this status reports the actual state of
the battery port, not an echo of the command:

| Bit | Meaning | Set (= 1) means |
| --- | --- | --- |
| 0 | Standby | battery port is in standby |
| 1 | Reserved | reserved |
| 2 | Fault | fault active — read the fault code at 10001–10002 ([6.2 alarm bitmap](#62-device-fault-code-alarm-bitmap-1000110002)) |
| 3 | Charging | battery is charging |
| 4 | Discharging | battery is discharging |
| 5–15 | Reserved | ignore |

Example: a read of 0x0008 (only bit 3 set) means the battery port is
charging; a read of 0x0001 (only bit 0 set) means it is in standby.

### 3.2 Detailed monitoring (10012–10043)

| Register | Hex | Name | Type | Unit | Scale | Remarks |
| --- | --- | --- | --- | --- | --- | --- |
| 10012 | 0x271C | Grid Voltage | uint16 | V | 0.1 | phase voltage; phase A on three-phase models |
| 10013 | 0x271D | Grid Current | int16 | A | 0.1 | Positive = importing from grid; negative = feeding into grid |
| 10014 | 0x271E | Grid Frequency | uint16 | Hz | 0.01 | — |
| 10015 | 0x271F | Phase A Power | int16 | W | 1 | three-phase models |
| 10016 | 0x2720 | Phase B Power | int16 | W | 1 | three-phase models |
| 10017 | 0x2721 | Phase C Power | int16 | W | 1 | three-phase models |
| 10018 | 0x2722 | PV String Count | uint16 | — | — | reads N = N strings supported; unsupported strings read 0 |
| 10019 | 0x2723 | PV1 Voltage | uint16 | V | 0.1 | — |
| 10020 | 0x2724 | PV1 Current | uint16 | A | 0.1 | — |
| 10021–10022 | 0x2725 | PV1 Energy | uint32 | kWh | 0.01 | high word first |
| 10023 | 0x2727 | PV2 Voltage | uint16 | V | 0.1 | — |
| 10024 | 0x2728 | PV2 Current | uint16 | A | 0.1 | — |
| 10025–10026 | 0x2729 | PV2 Energy | uint32 | kWh | 0.01 | high word first |
| 10027 | 0x272B | PV3 Voltage | uint16 | V | 0.1 | — |
| 10028 | 0x272C | PV3 Current | uint16 | A | 0.1 | — |
| 10029–10030 | 0x272D | PV3 Energy | uint32 | kWh | 0.01 | high word first |
| 10031 | 0x272F | PV4 Voltage | uint16 | V | 0.1 | — |
| 10032 | 0x2730 | PV4 Current | uint16 | A | 0.1 | — |
| 10033–10034 | 0x2731 | PV4 Energy | uint32 | kWh | 0.01 | high word first |
| 10035 | 0x2733 | Battery Voltage | uint16 | V | 0.01 | DC bus voltage |
| 10036 | 0x2734 | Battery Current | int16 | A | 0.1 | Positive = charging; negative = discharging |
| 10037 | 0x2735 | Cell Temp Max | **int16** | °C | 0.1 | signed — no offset encoding |
| 10038 | 0x2736 | Cell Temp Min | **int16** | °C | 0.1 | signed — no offset encoding |
| 10039 | 0x2737 | Battery Max Charge Power | uint16 | W | 1 | currently allowed charge power; may fall below the 10100 setting when derated by temperature / SoC |
| 10040 | 0x2738 | Battery Max Discharge Power | uint16 | W | 1 | currently allowed discharge power; may fall below the 10101 setting when derated by temperature / SoC |
| 10041 | 0x2739 | Bypass Voltage | uint16 | V | 0.1 | — |
| 10042 | 0x273A | Bypass Current | uint16 | A | 0.1 | — |
| 10043 | 0x273B | Bypass Frequency | uint16 | Hz | 0.01 | — |

### 3.3 Operating parameters and device info (10044–10063)

The serial-number and firmware-version fields do not answer single-register
reads. Read each field complete in one request — device serial 10054 (0x2746)
× 8, firmware version 10062 (0x274E) × 2.

| Register | Hex | Name | Type | Unit | Scale | Remarks |
| --- | --- | --- | --- | --- | --- | --- |
| 10044 | 0x273C | Design Capacity | uint16 | kWh | 0.01 | battery-pack nameplate capacity |
| 10045 | 0x273D | Remaining Capacity | uint16 | kWh | 0.01 | current remaining battery energy |
| 10046 | 0x273E | System Backup SoC | uint16 | % | 1 | mirrors the written Safety SoC (10102) |
| 10047 | 0x273F | SOH | uint16 | % | 1 | 0–100 |
| 10048 | 0x2740 | Hardware Max AC Charge Power | uint16 | W | 1 | device hardware ceiling, fixed at the factory, not modifiable |
| 10049 | 0x2741 | Hardware Max AC Discharge Power | uint16 | W | 1 | device hardware ceiling, fixed at the factory, not modifiable |
| 10050 | 0x2742 | Grid-Code Export Limit | uint16 | W | 1 | locally allowed grid-feed power limit; factory-locked to the grid-code default, = 10049 after App unlock — unlock is App-only, not writable over Modbus |
| 10051 | 0x2743 | Global AC Charge Power Limit | uint16 | W | 1 | mirrors the written 10100 |
| 10052 | 0x2744 | Global AC Discharge Power Limit | uint16 | W | 1 | mirrors the written 10101 |
| 10053 | 0x2745 | Wi-Fi Signal | int16 | dBm | 1 | always negative; for example, -60 |
| 10054–10061 | 0x2746 | Device Serial | string[8] | U16[8] ASCII | — | 8 registers = 16 bytes; no single-register reads — read the whole field |
| 10062–10063 | 0x274E | Firmware Version | string[2] | U16[2] ASCII | — | 2 registers = 4 bytes; no single-register reads — read the whole field |

### 3.4 Lifetime energy counters (10064–10081)

All uint32, kWh × 0.01, high word first, read-only, monotonically increasing.

| Register | Hex | Name | Type | Unit | Scale | Remarks |
| --- | --- | --- | --- | --- | --- | --- |
| 10064–10065 | 0x2750 | Grid Import Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10066–10067 | 0x2752 | Grid Export Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10068–10069 | 0x2754 | Meter Import Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10070–10071 | 0x2756 | Meter Export Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10072–10073 | 0x2758 | PV Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10074–10075 | 0x275A | Battery Charge Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10076–10077 | 0x275C | Battery Discharge Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10078–10079 | 0x275E | Bypass Output Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |
| 10080–10081 | 0x2760 | Bypass Input Energy Total | uint32 | kWh | 0.01 | read-only; monotonically increasing |

### 3.5 Control — power and SoC settings (10100–10102)

The three registers in this group can be written individually with FC 0x06 or
together with FC 0x10; all three survive power cycles. Only 10103–10106 must
be written as one atomic FC 0x10 group.

| Register | Hex | Name | Type | Unit | Remarks |
| --- | --- | --- | --- | --- | --- |
| 10100 | 0x2774 | AC Charge Power Limit | uint16 | W | default 800; writable range 50 to hardware max (10048); out-of-range writes return an exception code; persists across power cycles |
| 10101 | 0x2775 | AC Discharge Power Limit | uint16 | W | writable floor 100; writable ceiling = local grid-code export value while locked, hardware max (10049) after App unlock; persists across power cycles |
| 10102 | 0x2776 | Safety SoC | uint16 | % | 10–100, default 20; out-of-range → Modbus exception 0x03; persists across power cycles |

### 3.6 Control — real-time force charge/discharge (10103–10106)

The device **explicitly does not support single-register writes** for this
group (the one exception: direction value 3 "exit" may be written alone with FC
0x06). Write all four registers in **one FC 0x10 frame**. The group is volatile
and ends when **either** the cutoff SoC **or** the duration is reached —
whichever comes first. After a Modbus timeout (see 10114) the device falls
back to the CONOW platform mode that was active before the Modbus
service was enabled.

10104 is a **direct output setpoint**: the device outputs the set power
regardless of the load. Load-following behavior is selected by the work mode
(10107) in the App and requires a connected meter.

| Register | Hex | Name | Type | Unit | Remarks |
| --- | --- | --- | --- | --- | --- |
| 10103 | 0x2777 | Charge/Discharge Direction | uint16 | — | 0 = idle · 1 = charge · 2 = discharge · 3 = exit; direction 3 (exit) may be written alone with FC 0x06 |
| 10104 | 0x2778 | Target Charge/Discharge Power | uint16 | W | 0 to the limit set by 10100 / 10101; a written value above the limit is automatically written as the limit — no exception is returned |
| 10105 | 0x2779 | Charge/Discharge Cutoff SoC | uint16 | % | safety SoC (10102) to 100; on discharge, a written value below the safety SoC is automatically written as 10102 — no exception is returned |
| 10106 | 0x277A | Charge/Discharge Duration | uint16 | min | 30–720; ends when either the duration or the cutoff SoC is reached first |

### 3.7 Control — work strategy (10107–10114)

All registers in this group survive power cycles. Registers marked *reserved*
exist in the map but are not yet functional on current hardware.

| Register | Hex | Name | Type | Unit | Remarks |
| --- | --- | --- | --- | --- | --- |
| 10107 | 0x277B | Work Mode | uint16 | — | 1 = self-consumption · 2 = manual time slots · 3 = idle; default 1; **read before write**; with a meter it follows meter power, without one it outputs the base load; persists across power cycles |
| 10108 | 0x277C | Backup SoC | uint16 | % | safety SoC (10102) to 100, default 40; *reserved* (backup-power mode, not supported yet); persists across power cycles |
| 10109 | 0x277D | Allowed Reverse Power | uint16 | W | 0 = no reverse flow; greater than 0 = allowed maximum reverse power; writable but ineffective without a connected meter; persists across power cycles |
| 10110 | 0x277E | Allow Battery Export | uint16 | — | 0 = forbidden · 1 = allowed; *reserved* (grid-feed mode, not supported yet); persists across power cycles |
| 10111 | 0x277F | Bypass Always-On Switch | uint16 | — | 0 = off · 1 = on; default off; persists across power cycles |
| 10112 | 0x2780 | Off-Grid Output Switch | uint16 | — | 0 = off · 1 = on; default off; persists across power cycles |
| 10113 | 0x2781 | PV Curtailment Switch | uint16 | — | 0 = off · 1 = on; default off; *reserved, not supported yet*; persists across power cycles |
| 10114 | 0x2782 | Modbus Timeout | uint16 | s | 0–3600, 0 = disabled (default); watchdog — with no valid **write** frame for this long, the device falls back to the CONOW platform mode that was active before the Modbus service was enabled; persists across power cycles |

### 3.8 Control — generator and digital outputs (10115–10122)

On models without the generator feature, reads return 0 and writes return an
exception. The two DO registers are volatile; the rest survive power cycles.

| Register | Hex | Name | Type | Unit | Remarks |
| --- | --- | --- | --- | --- | --- |
| 10115 | 0x2783 | Generator Switch | uint16 | — | 0 = off · 1 = on; persists across power cycles |
| 10116 | 0x2784 | Generator Start Time | uint16 | hhmm | hour in the high byte (0–23), minute in the low byte (0–59); persists across power cycles |
| 10117 | 0x2785 | Generator Stop Time | uint16 | hhmm | hour in the high byte (0–23), minute in the low byte (0–59); persists across power cycles |
| 10118 | 0x2786 | Generator Power | uint16 | W | persists across power cycles |
| 10119 | 0x2787 | Generator Start SoC | uint16 | % | target SoC that triggers generator charging; persists across power cycles |
| 10120 | 0x2788 | Generator Stop SoC | uint16 | % | cutoff SoC that stops generator charging; persists across power cycles |
| 10121 | 0x2789 | DO1 Control | uint16 | — | 0 = off · 1 = on; volatile |
| 10122 | 0x278A | DO2 Control | uint16 | — | 0 = off · 1 = on; volatile |

### 3.9 Control — base load (10123–10148)

When no meter is connected (or the meter is faulty), the device outputs the
base-load setpoint outside any configured time slot; the setting persists
across power cycles.

<strong>Cloud synchronization note:</strong> after a device power cycle, when the cloud
connection is available, Allowed Reverse Power (10109), Base Load (10123), and
the Base-Load Schedule (10124–10148) may be synchronized to the values set in
the CONOW App, overwriting their current values. Write these registers again if
the Modbus settings must be retained.

| Register | Hex | Name | Type | Unit | Remarks |
| --- | --- | --- | --- | --- | --- |
| 10123 | 0x278B | Base Load | uint16 | W | 0–3000, default 200; persists across power cycles |
| 10124 | 0x278C | Base Load Slot Count | uint16 | — | 0–8; the device executes only the first N slots |

**Base-load schedule** — a slot count (0–8) followed by 8 slots of
(start, end, power). Write only the first N slots you actually use and set
the count register to N; the device executes only the first N slots and
ignores the rest. All
hhmm registers encode hour in the high byte, minute in the low byte.

| Slot | Start | End | Power |
| --- | --- | --- | --- |
| 1 | 10125 (0x278D) | 10126 (0x278E) | 10127 (0x278F) |
| 2 | 10128 (0x2790) | 10129 (0x2791) | 10130 (0x2792) |
| 3 | 10131 (0x2793) | 10132 (0x2794) | 10133 (0x2795) |
| 4 | 10134 (0x2796) | 10135 (0x2797) | 10136 (0x2798) |
| 5 | 10137 (0x2799) | 10138 (0x279A) | 10139 (0x279B) |
| 6 | 10140 (0x279C) | 10141 (0x279D) | 10142 (0x279E) |
| 7 | 10143 (0x279F) | 10144 (0x27A0) | 10145 (0x27A1) |
| 8 | 10146 (0x27A2) | 10147 (0x27A3) | 10148 (0x27A4) |

Slot power range 0–3000 W.

### 3.10 Control — manual charge/discharge (TOU) schedule (10149–10189)

Work mode 2 (manual time slots) executes this schedule: up to 8 strategies,
each a time window that charges to a target SoC or discharges at a set power.
Write only the first N slots you actually use and set the count register
(**10149, 0x27A5**, 0–8) to N; the device executes only the first N slots.
Persists across power cycles.

| Register | Hex | Name | Type | Unit | Remarks |
| --- | --- | --- | --- | --- | --- |
| 10149 | 0x27A5 | TOU Slot Count | uint16 | — | 0–8; the device executes only the first N slots; persists across power cycles |

Time outside the configured slots follows the **baseline strategy**. The
baseline offers two modes — self-consumption and idle — and defaults to idle;
it is adjusted in the CONOW app.

Each slot is 5 registers — start, end, mode, then one of target SoC / discharge
power (the inactive one is ignored):

| Field | Meaning |
| --- | --- |
| start / end | hhmm (hour high byte, minute low byte) |
| mode | 0 = charge (only Target SoC applies) · 1 = discharge (only Discharge Power applies) |
| target SoC | uint16 %, applies when mode = 0 |
| discharge power | uint16 W, applies when mode = 1 |

| Slot | Start | End | Mode | Target SoC | Discharge Power |
| --- | --- | --- | --- | --- | --- |
| 1 | 10150 (0x27A6) | 10151 (0x27A7) | 10152 (0x27A8) | 10153 (0x27A9) | 10154 (0x27AA) |
| 2 | 10155 (0x27AB) | 10156 (0x27AC) | 10157 (0x27AD) | 10158 (0x27AE) | 10159 (0x27AF) |
| 3 | 10160 (0x27B0) | 10161 (0x27B1) | 10162 (0x27B2) | 10163 (0x27B3) | 10164 (0x27B4) |
| 4 | 10165 (0x27B5) | 10166 (0x27B6) | 10167 (0x27B7) | 10168 (0x27B8) | 10169 (0x27B9) |
| 5 | 10170 (0x27BA) | 10171 (0x27BB) | 10172 (0x27BC) | 10173 (0x27BD) | 10174 (0x27BE) |
| 6 | 10175 (0x27BF) | 10176 (0x27C0) | 10177 (0x27C1) | 10178 (0x27C2) | 10179 (0x27C3) |
| 7 | 10180 (0x27C4) | 10181 (0x27C5) | 10182 (0x27C6) | 10183 (0x27C7) | 10184 (0x27C8) |
| 8 | 10185 (0x27C9) | 10186 (0x27CA) | 10187 (0x27CB) | 10188 (0x27CC) | 10189 (0x27CD) |

### 3.11 Control — time calibration (10190)

While the device is offline from the cloud its clock can drift, and TOU or
base-load slots then run at the wrong times. Read the device time-of-day and
calibrate it with one write when it has drifted — check that your own time
source is correct first.

| Register | Hex | Name | Type | Unit | Scale | Remarks |
| --- | --- | --- | --- | --- | --- | --- |
| 10190 | 0x27CE | Device Time of Day (read / calibrate) | uint16 | hhmm | — | hour in the high byte (0–23), minute in the low byte (0–59); calibrates the time of day only — no date, weekday, or time zone; volatile |

### 3.12 Protocol registers (9984–9986)

Identity and verification registers shared by both transports; the workflow is described in the sections above.

| Register | Hex | Name | Type | Unit | Remarks |
| --- | --- | --- | --- | --- | --- |
| 9984 | 0x2700 | Unit ID | uint16 | — | RTU slave address and TCP unit ID; readable and writable, range 128–176 (0x80–0xB0); changing it does not require repeating the TCP verification |
| 9985–9986 | 0x2701 | TCP Verification Code | uint32 | — | write-only; the dynamic 8-character hexadecimal code from the CONOW App device details page (refreshed every 120 seconds); see [Verification code](#verification-code-modbus-tcp-direct-all-in-one-machines) |

---

## 4 Frame examples

Framing and CRC-16 (Modbus) are identical to the v1 guide: slave `0xA0`,
function code, data, CRC low byte first. The examples below are RTU
frames; for TCP framing see [Modbus TCP framing (MBAP)](#modbus-tcp-framing-mbap).

**Read the firmware-version field (firmware version check, 10062 × 2):**

```
A0 03 27 4E 00 02 B7 D9
```

**Read real-time data (10000 × 12):**

```
A0 03 27 10 00 0C 57 CF
```

**Write single register — AC discharge power limit 700 W → 10101:**

```
A0 06 27 75 02 BC 8B 04
```

**Atomic group write — force discharge 500 W until SoC 80% or 120 min
(FC 0x10, registers 10103–10106):**

```
A0 10 27 77 00 04 08  00 02 01 F4 00 50 00 78  84 66
│  │  └───┘ └───┘ │   └───┘ └───┘ └───┘ └───┘  └───┘
│  │  │     │     │   │     │     │     │      └── CRC-16
│  │  │     │     │   │     │     │     └── register 10106: 0x0078 (120 min)
│  │  │     │     │   │     │     └── register 10105: 0x0050 (80%)
│  │  │     │     │   │     └── register 10104: 0x01F4 (500 W)
│  │  │     │     │   └── register 10103: 0x0002 (discharge)
│  │  │     │     └── byte count: 8 (4 registers × 2 bytes)
│  │  │     └── quantity: 4 registers
│  │  └── start address: 0x2777 (10103)
│  └── FC 0x10
└── slave 160 (0xA0)
```

### Modbus TCP framing (MBAP)

Over TCP the same PDU travels inside a 7-byte MBAP header and there is **no CRC** — the TCP transport provides the integrity check.

| MBAP field | Size | Value |
| --- | --- | --- |
| Transaction ID | 2 bytes | chosen by the master; echoed unchanged in the response |
| Protocol ID | 2 bytes | `0x0000` (Modbus) |
| Length | 2 bytes | number of bytes that follow (unit ID + PDU) |
| Unit ID | 1 byte | the device unit ID — `0xA0` by default (register 9984) |

**Write the verification code (TCP direct) — code `1A2B3C4D` → 9985–9986:**

```
00 01  00 00  00 0B  A0  10  27 01  00 02  04  1A 2B 3C 4D
└───┘  └───┘  └───┘  │   │   └───┘  └───┘  │   └─────────┘
│      │      │      │   │     │      │    │   verification code 0x1A2B3C4D
│      │      │      │   │     │      │    └── byte count: 4
│      │      │      │   │     │      └── quantity: 2 registers
│      │      │      │   │     └── start address: 0x2701 (9985)
│      │      │      │   └── FC 0x10
│      │      │      └── unit ID: 160 (0xA0)
│      │      └── length: 11 bytes (unit ID + PDU)
│      └── protocol ID: 0x0000 (Modbus)
└── transaction ID: 0x0001 — echoed in the response
```

The response echoes the header with length 6: `00 01 00 00 00 06 A0 10 27 01 00 02`.

Verify any frame's CRC yourself:

```sh
python3 - <<'PY'
def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c
frame = bytes.fromhex("A0102777000408" "0002" "01F4" "0050" "0078")
print(f"{crc16(frame):04X}")   # append low byte, then high byte
PY
```

**Exception responses** — on error the device answers `[slave] [function code + 0x80] [exception code] [CRC]`; the codes and their meanings are in [6.1 Modbus exception codes](#61-modbus-exception-codes).

### Quick test from the command line

The frames above are raw protocol bytes. For a first live test you can also drive the device with a standard Modbus client, for example [mbpoll](https://github.com/epsilonrt/mbpoll) or [pymodbus](https://github.com/pymodbus/pymodbus). Both examples below run the [firmware version check](#firmware-version-check) — reading 10062–10063 with FC 0x03 — over RS-485 RTU, which needs no verification code.

```sh
# mbpoll — RTU on /dev/ttyUSB0, slave 160 (0xA0), 38400 8N1
# -P none is required: mbpoll defaults to even parity
mbpoll -m rtu -a 160 -b 38400 -P none -t 4 -0 -r 10062 -c 2 -1 /dev/ttyUSB0
# append ":string" to -t 4 to print the registers as ASCII characters
```

```python
# pymodbus 3.x — pip install pymodbus
import struct

from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port="/dev/ttyUSB0",
    baudrate=38400,
    bytesize=8,
    parity="N",
    stopbits=1,
)
client.connect()
rr = client.read_holding_registers(address=10062, count=2, slave=160)
if not rr.isError():
    print(struct.pack(">HH", *rr.registers).decode())  # 4 ASCII characters
client.close()
```

On Modbus TCP direct, complete the [verification](#verification-code-modbus-tcp-direct-all-in-one-machines) first. With the example code `1A2B3C4D`:

```sh
# mbpoll — write the uint32 verification code, high word first (9985 = 0x1A2B, 9986 = 0x3C4D)
mbpoll -m tcp -a 160 -t 4 -0 -r 9985 -1 192.168.1.100 6699 15629
```

The equivalent in pymodbus is `client.write_registers(address=9985, values=[0x1A2B, 0x3C4D], slave=160)` on a `ModbusTcpClient("192.168.1.100", port=502)`.

---

## 5 Important notes

1. **Modbus vs. App priority.** Modbus and the App/cloud are two independent
   control paths:

   While Modbus is active, the device leaves the App-side work mode and
   follows only Modbus; after the master stops writing and the timeout at
   10114 expires, the device returns to the CONOW platform mode from before
   the Modbus service was enabled.
2. **Group-write discipline.** Commands that need an atomic write (real-time
   control) are written in one request, following the register addresses.
3. **Schedules are count-consistent.** Write only the first N slots you
   actually use and set the count register (10124 / 10149) to N — the device
   executes only the first N slots.
4. **Work mode: read before write.** Read the current value before writing
   10107, then write the target value.
5. **Persistence.** 10103–10106, 10121–10122, and 10190 are volatile;
   everything else in the control area survives power cycles.
6. **CRC errors are silently discarded.** On timeout, retry up to 3 times at
   least 500 ms apart, and treat 3 consecutive timeouts as a link fault. Poll
   real-time values no faster than once per 1 s; when one request reads or
   writes multiple registers, a polling interval of at least 2 s is
   recommended; poll energy-control registers no faster than once per 5 s,
   and do not poll the full register map at a high rate.
7. **Keep the prerequisites.** Device commissioned in CONOW ECO App once, and
   *Enable Modbus service* turned on — a never-commissioned device stays
   silent regardless of firmware, and with *Enable Modbus service* switched
   off, RTU reads and writes are answered with exception 0x06
   ([6.1 Modbus exception codes](#61-modbus-exception-codes)).
8. **The watchdog counts writes only.** The watchdog at 10114 is fed by valid
   write frames (FC 0x06 / 0x10) only — polling reads do not reset it. If the
   last instruction received was direction = idle (10103 = 0), the device
   holds that state indefinitely and does not fall back; only a new
   instruction or disabling the Modbus service changes it.
9. **One writer at a time.** With RTU and TCP both enabled, writes follow the
   RTU-priority rule in
   [Concurrent RTU and TCP](#concurrent-rtu-and-tcp-write-priority); a TCP
   write rejected with 0x86 / 0x90 is expected behavior, not a link fault.

---

## 6 Troubleshooting

Start with the first check for your symptom, then follow the referenced
sections.

| Symptom | First check | Notes / reference |
| --- | --- | --- |
| Device answers nothing | Modbus switch enabled in the App; slave address / unit ID matches the current value at 9984 | with the switch off, RTU reads and writes are answered with exception 0x06 ([6.1 Modbus exception codes](#61-modbus-exception-codes)); default 0xA0 ([transport parameters](#transport-and-connection-parameters)) |
| RTU intermittent no-reply or CRC errors | CRC-16 calculation (polynomial 0xA001) and the serial parameters 38400-8-N-1 | wrong-CRC frames are dropped with no reply — check the CRC first, then confirm wiring and the address |
| No reply when reading 128 registers or more | request longer than 127 registers | FC 0x03 serves at most 127 registers per request ([read size limit](#transport-and-connection-parameters)) |
| TCP no reply, verification error, or writes without effect | TCP switch, network, and unit ID first; a verification error means redoing the 9985–9986 verification; writes still rejected after verification — check the RTU write-priority rule | unconnected endpoints stay silent; connected-but-unverified requests get a verification error ([verification code](#verification-code-modbus-tcp-direct-all-in-one-machines), [Concurrent RTU and TCP](#concurrent-rtu-and-tcp-write-priority)) |
| Write ignored or answered with an exception | written value inside the register range | out-of-range writes are rejected with exception 0x03 ([6.1 Modbus exception codes](#61-modbus-exception-codes)) |
| Device behavior changes after a disconnect | watchdog 10114 enabled? | with 10114 = 0 the device keeps its work mode; with a timeout set it falls back to the CONOW platform mode from before the Modbus service was enabled ([notes](#5-important-notes)) |

### 6.1 Modbus exception codes

Reads and writes only use FC 0x03 / 0x06 / 0x10, and the standard exception codes 0x01–0x03 only appear in answers to these three function codes; on error the device answers `[slave] [function code + 0x80] [exception code] [CRC]`:

| Code | Meaning | Typical cause |
| --- | --- | --- |
| 0x01 | Illegal function | function code not supported (reads and writes support FC 0x03 / 0x06 / 0x10 only) |
| 0x02 | Illegal data address | register does not exist, or not supported by this model; during a TCP verification lockout, reads and writes all return 0x02 (reading 9984 excepted) |
| 0x03 | Illegal data value | written value out of range |

0x04 / 0x05 are device-defined status codes returned by the TCP-direct
verification layer, not standard read/write exception responses for FC 0x03 /
0x06 / 0x10; see [Verification code](#verification-code-modbus-tcp-direct-all-in-one-machines) for the verification-layer scenarios:

| Code | Meaning | Typical cause |
| --- | --- | --- |
| 0x04 | MAC address changed (device-defined) | the TCP verification code was invalidated by a communication-adapter MAC address change — write the code again |
| 0x05 | Manual refresh (device-defined) | returned when the device is accessed over TCP after a manual refresh invalidated the verification code — write the new code |

0x06 (device-defined) is returned only on Modbus RTU — after *Enable Modbus service* is switched off in the App, register reads and writes are answered with 0x06:

| Code | Meaning | Typical cause |
| --- | --- | --- |
| 0x06 | Modbus service not enabled (device-defined) | *Enable Modbus service* switched off in the App — switch it on again and retry |

### 6.2 Device fault code (alarm bitmap, 10001–10002)

The device fault code (10001–10002, uint32) is a 32-bit bitmap: a bit set to `1` means the matching alarm is currently active, and several bits may be set at once. Read both registers together in one request.

| Bit | CBE2000 Pro | Atlas 6000 | Lyra 2500 |
| --- | --- | --- | --- |
| bit0 | Pack 1 alarm | Cell overvoltage | Cell overvoltage |
| bit1 | Pack 2 alarm | Cell undervoltage | Cell undervoltage |
| bit2 | Pack 3 alarm | Battery overvoltage | Battery overvoltage |
| bit3 | Pack 4 alarm | Battery undervoltage | Battery undervoltage |
| bit4 | Pack 5 alarm | Charge low temperature | Charge low temperature |
| bit5 | Pack 6 alarm | Charge high temperature | Charge high temperature |
| bit6 | — | Discharge low temperature | Discharge low temperature |
| bit7 | — | Discharge high temperature | Discharge high temperature |
| bit8 | Main-expansion communication error | Charge overcurrent 1 | Charge overcurrent 1 |
| bit9 | LED panel communication error | Charge overcurrent 2 | Charge overcurrent 2 |
| bit10 | Inverter communication error | Discharge overcurrent 1 | Discharge overcurrent 1 |
| bit11 | Inverter failure | Discharge overcurrent 2 | Discharge overcurrent 2 |
| bit12 | Wi-Fi module communication fault | MOS high temperature | MOS high temperature |
| bit13 | PV1 alarm | Temperature-difference alarm | Temperature-difference alarm |
| bit14 | PV2 alarm | Voltage-difference alarm | Voltage-difference alarm |
| bit15 | PV3 alarm | Short circuit | Short circuit |
| bit16 | PV4 alarm | NTC failure | NTC failure |
| bit17 | Grid fault (under-frequency / over-frequency) | Cell failure | Cell failure |
| bit18 | Inverter output alarm | AFE failure | AFE failure |
| bit19 | — | Charge MOS alarm | Charge MOS alarm |
| bit20 | — | Discharge MOS alarm | Discharge MOS alarm |
| bit21 | — | Heater film open circuit | — |
| bit22 | Short circuit 2 | — | — |
| bit23 | Off-grid input overload | Shunt alarm | Shunt alarm |
| bit24 | Expansion repeated-addressing error | Main-expansion communication error | Main-expansion communication error |
| bit25 | Main repeated-addressing error | Inverter communication | Inverter communication |
| bit26 | Short circuit 1 | Wi-Fi communication error | Wi-Fi communication error |
| bit27 | — | — | — |
| bit28 | — | Low-temperature overload | Low-temperature overload |
| bit29 | — | Off-grid input overload | Off-grid input overload |
| bit30 | — | Battery terminal overtemperature | Meter circuit error |
| bit31 | — | Meter circuit error | — |

The cause and the fix for each alarm, for self-service troubleshooting:

**Battery alarms**

| Alarm | Cause | Fix |
| --- | --- | --- |
| Cell overvoltage | cell voltage briefly exceeded the upper limit | normal protection notice — wait for recovery; contact support if it recurs frequently |
| Cell undervoltage | cell voltage below the safety limit | charge the battery soon; contact support if charging fails or it recurs |
| Battery overvoltage | pack total voltage exceeded the upper limit | wait for automatic recovery; contact support if it recurs |
| Battery undervoltage | pack total voltage below the lower limit | charge the battery immediately; contact support if charging fails |
| Charge low temperature | temperature too low for charging | raise the ambient temperature or wait for warmer conditions before charging |
| Charge high temperature | charging temperature too high | place the device in a cool, ventilated spot and remove covers; continue after it cools |
| Discharge low temperature | discharge temperature too low | reduce the load and warm the environment; resume normal use after recovery |
| Discharge high temperature | discharge temperature too high | remove covers and keep out of direct sunlight; continue after it cools |
| Charge overcurrent 1 | charging current above the level-1 threshold | try restarting and watch for recovery; contact support if it persists |
| Charge overcurrent 2 | charging current far above the limit | try restarting and watch for recovery; contact support if it persists |
| Discharge overcurrent 1 | discharge current above the threshold, protection triggered | try restarting and watch for recovery; contact support if it persists |
| Discharge overcurrent 2 | discharge current far above the limit, forced protection | try restarting and watch for recovery; contact support if it persists |
| MOS high temperature | power MOS temperature too high | charging and discharging pause; automatic recovery after cooling; contact support if frequent |
| Temperature-difference alarm | temperature difference between sensing points too large | wait for recovery and observe; contact support if it recurs |
| Voltage-difference alarm | voltage difference between cells too large | wait for the system to balance; contact support if it recurs |
| Short circuit | short circuit detected on the DC side, protection active | power off immediately and check the wiring and loads, then restart to test; contact support if it does not recover |
| NTC failure | temperature sensor open or short circuit | try restarting and watch for recovery; contact support if it persists |
| Cell failure | a cell has failed or disconnected | stop using the device and contact support promptly |
| AFE failure | front-end sampling circuit failure | power the device down and contact support for diagnostics |
| Charge MOS alarm | abnormal switching of the charge MOS | stop charging immediately and contact support |
| Discharge MOS alarm | abnormal switching of the discharge MOS | disconnect the loads and contact support |
| Heater film open circuit | heating function failed | charging pauses at low temperature; check the connections; contact support if it persists |
| Shunt alarm | abnormal current measurement | try restarting and watch for recovery; contact support if it persists |

**System and other alarms**

| Alarm | Cause | Fix |
| --- | --- | --- |
| Main-expansion communication error | communication abnormal between the main and expansion controllers | try restarting and watch for recovery; contact support if it persists |
| LED panel communication error | communication with the LED/display panel interrupted or abnormal | try restarting and watch for recovery; contact support if it persists |
| Inverter communication error | communication between the main control and the inverter interrupted or abnormal | stop using the device and contact support promptly |
| Inverter failure | inverter malfunctioning or unable to start or output | stop using the device and contact support promptly |
| Wi-Fi module communication fault | the device cannot connect to Wi-Fi | check the Wi-Fi signal, the router settings, and the password, then reconnect |
| Low-temperature overload | at low temperature the off-grid output exceeds the maximum allowed discharge power | reduce the off-grid load power or disconnect the loads |
| Off-grid input overload | off-grid input power exceeds the maximum allowed battery charge power | reduce the off-grid input power or disconnect the input device |
| Short circuit 1 / Short circuit 2 | pre-charge failed — the 1st / 2nd short circuit recorded by the BMS | wait for the device to recover on its own; a third consecutive short circuit affects operation — restart and observe, and contact support if it does not recover |
| Grid fault | grid frequency outside the permitted range (under-frequency / over-frequency) | wait for the grid to recover; contact the utility or support if it persists |
| Meter circuit error | CT abnormal, meter data unavailable | to keep the device and the grid safe, the device runs at base-load output; check the meter wiring |
| Battery terminal overtemperature | battery terminal temperature too high | check the terminal wiring and the loads; contact support if it persists |
| Inverter output alarm | inverter output abnormal | open the App alarm page, identify the specific alarm, and handle it there |
| Pack N alarm | the matching battery pack has an alarm; Modbus does not expose the type | open the App alarm page for that pack and handle the specific alarm |
| PV1–PV4 alarm | the matching PV input string has an alarm; Modbus does not expose the type | open the App alarm page; check that PV string |
| Main/expansion repeated-addressing error | pack address assignment failed repeatedly | restart the device and observe; contact support if it persists |
