# Contributing

Thank you for helping improve CONOW developer documentation!

## How changes are made

This repository is maintained by the CONOW documentation team, and documentation updates are made by the maintainers.

Found an error or want to suggest an improvement? Open an [Issue](../../issues) describing it, and the maintainers will evaluate and apply the change.

## Style Guide

- Write in English (US spelling). Do not leave Chinese terms from the source register sheets in English documents — link to the translated READMEs instead.
- Use [GitHub Flavored Markdown](https://github.github.com/gfm/).
- Follow GitHub documentation style: sentence-case headings, "and" instead of "&", straight quotes, Oxford commas, no Latin abbreviations (write "for example", not "e.g.").
- Sign conventions and comparisons in words: "Positive = charging; negative = discharging", "greater than 0" — not "+ =", ">0", or math symbols such as ≥.
- Ranges use an en dash (10–100), never a tilde (10~100); callouts use GitHub alert syntax (`> [!WARNING]`, `> [!IMPORTANT]`, `> [!NOTE]`) instead of emoji.
- Hex values: uppercase, for example `0xA0`, `0x2710`.
- Register addresses: always show both decimal and hex.
- Frame bytes: space-separated uppercase hex, for example `A0 03 27 12 00 01 3E 6B`.
- Frame annotation diagrams: brace groups must start and end exactly on byte-token boundaries, and every stub or elbow must connect to the row above. The v1 guides place each vertical stub under the center of its brace group; the v2 guides place stubs at field start columns. Keep each diagram in one style — do not mix the two.

## Reporting Issues

Open an [Issue](../../issues) and include:
- Product model
- Firmware version (if known)
- Steps to reproduce
- Expected vs actual behavior

You can also reach the documentation team by email at [support@conow.com](mailto:support@conow.com).
