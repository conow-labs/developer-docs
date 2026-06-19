# Modbus RTU API References

Local RS-485 communication guides for CONOW devices.

| File | Product | Protocol |
|------|---------|----------|
| [balcony-solar-storage.md](balcony-solar-storage.md) | Balcony Solar Storage (CBE2000 Pro, Lyra Series, Atlas Series) | Modbus RTU |

## Prerequisites

Before using the Modbus interface, ensure the following:

**1. Device is activated**

The device must be commissioned and online in the CONOW ECO App at least once before the RS-485 interface becomes operational.

**2. External control is enabled in the App**

Depending on your App version, use one of the following:

- **Option A:** In the **Devices** tab, enter the device panel → **Settings → Operation Mode** → select **DIY Mode**.
- **Option B:** In the **Devices** tab, enter the device panel → **Settings** → toggle on **Enable External Control**.

The RS-485 interface will not respond to any Modbus commands until one of these is enabled.

## Quick Start

1. Connect an RS-485 to USB adapter between your host and the device RS-485 port.
2. Configure serial parameters: **38400 baud, 8N1, device address 0xA0**.
3. Send a standard Modbus RTU frame -- see the product-specific guide for register maps and frame examples.
