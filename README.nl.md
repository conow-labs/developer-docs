# CONOW Developer Docs (Nederlands)

**Open protocolreferenties en integratiehandleidingen voor CONOW-producten
voor thuisbatterijen en balkon-zonnestroom met opslag.**

Taal / Language / 语言 / Sprache: [English](README.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **Nederlands**

---

## Updates

- **2026-11-20**
  - Registeroverzicht voor firmware v2 toegevoegd: directe Modbus TCP, protocolregisters 9984–9986, volledig besturingsbereik 10100–10190 en exceptioncodetabellen.
  - Meer talen toegevoegd: Chinese, Duitse en Nederlandse versies van de README en beide registeroverzichten.

## Integratieroutes

Kies de route die bij je setup past:

| Route | Geschikt voor | Verbinding | Waar |
|------|----------|------------|-------|
| **Modbus RTU / TCP** | lokale besturing, geen cloudafhankelijkheid, eigen EMS | RS-485 / Ethernet (op het apparaat) | [`modbus/`](modbus/) — in deze repository |
| **Home Assistant Local** | Home Assistant-gebruikers die lokale CONOW-energie-entiteiten en automatiseringen zonder cloudafhankelijkheid willen | RS-485 / Modbus RTU | [conow-labs/home-assistant-local](https://github.com/conow-labs/home-assistant-local) |
| **Home Assistant** | smart home-gebruikers die dashboards, automatiseringen en CONOW-energie-entiteiten willen | Cloud (Tuya) | [conow-labs/home-assistant](https://github.com/conow-labs/home-assistant) |
| **Agent Skills** | AI-agenten (bijvoorbeeld Claude) die energiegegevens lezen en besturen | Cloud | [conow-labs/agent-skills](https://github.com/conow-labs/agent-skills) |

> [!WARNING]
> Besturingsregisters en commando's kunnen veranderen hoe je systeem laadt, ontladt en naar het net terugvoedt. Lees vóór het schrijven van een besturingswaarde eerst de veiligheidsinstructies van het product.

## Inhoud van deze repository

| Map | Beschrijving |
|-----------|-------------|
| [`modbus/`](modbus/) | Modbus API-referenties — registeroverzichten per firmwareversie, gegevenstypen en framevoorbeelden (RTU; TCP vanaf v2-firmware) |

## Ondersteunde producten

- **CBE-serie** — alles-in-één systeem voor balkon-zonnestroom met opslag (CBE2000 Pro)
- **Lyra serie** — AC-gekoppeld opslagsysteem (Lyra 2500 AC, Lyra 2500 Pro)
- **Atlas serie** — opslagsysteem met grote capaciteit (Atlas 6000 AC)

## Firmware-versie en registerdocumentatie (belangrijk)

**Vereisten voor Modbus-toegang:** het apparaat moet via de **CONOW ECO App** in
bedrijf zijn gesteld en minstens eenmaal online zijn geweest — een fabrieksnieuw,
nooit geactiveerd apparaat beantwoordt geen enkel verzoek op de RS-485-interface;
schakel in de app onder *Apparaten → jouw apparaat → Instellingen* de optie
*Modbus-service inschakelen* in — in oudere app-versies gebruik dan
*Instellingen → Bedrijfsmodus → DIY-modus*; houd schrijfacties telkens bij één
master.

De Modbus-registerindeling is gewijzigd met de **v2-firmware** — de twee
tabellen hieronder zijn onderling incompatibel; eerst de versie controleren,
dan gebruiken:

| Document | Firmware | Registerbereik |
| --- | --- | --- |
| [balcony-solar-storage-v2.nl.md](modbus/balcony-solar-storage-v2.nl.md) | **vanaf de v2-minimumversie** (Lyra 1.01.16 · CBE2000 Pro 1.02.17 · Atlas 1.01.08) | monitoring 10000–10081 · besturing 10100–10190 · protocol 9984–9986 |
| [balcony-solar-storage.nl.md](modbus/balcony-solar-storage.nl.md) | onder de v2-minimumversie (oud) | monitoring 10000–10036 · besturing 10100–10107 |

**Versiecontrole:** lees met FC 0x03 de firmwareversieregisters 10062–10063 (vanaf
10062, 0x274E, aantal 2).  
Antwoordt het apparaat, dan implementeert de firmware dit registerbereik en ligt
op of boven de v2-minimumversie — gebruik het v2-protocoldocument.  
Blijft het antwoord uit, of is er een timeout of een Modbus-exception, dan is het
registerbereik niet geïmplementeerd en ligt de firmware onder de
v2-minimumversie — gebruik het v1-protocoldocument.  

Nieuwe firmware ondersteunt bovendien **directe Modbus TCP** via de eigen
ethernetpoort van het all-in-one-apparaat (poort 502): schrijf na het verbinden de
dynamische 8-tekens hexadecimale verificatiecode van de apparaatdetailpagina in de
CONOW-app (ververst elke 120 seconden) als uint32 naar de registers 9985–9986 om
de verificatie af te ronden; pas daarna zijn lees- en schrijfacties mogelijk.
Modbus RTU over RS-485 (inclusief TCP via een RS-485-naar-ethernet-gateway) heeft
geen verificatiecode nodig.

## Bijdragen

Fout gevonden of een integratiehandleiding voorstellen? Open een [Issue](../../issues). Deze documentatie wordt onderhouden door het CONOW-documentatieteam; updates worden door het team doorgevoerd. Zie [CONTRIBUTING.md](CONTRIBUTING.md) voor richtlijnen.

## Contact

Vragen of feedback? Neem per e-mail contact op met het CONOW-documentatieteam: [support@conow.com](mailto:support@conow.com).

## Licentie

Documenten onder [CC BY 4.0](LICENSE-docs) — officiële tekst op [creativecommons.org](https://creativecommons.org/licenses/by/4.0/), code onder MIT ([LICENSE](LICENSE)).
