# Modbus-integratiegids — Balkon-zonne-energieopslag (V2-registeroverzicht)

> [!IMPORTANT]
> **Van toepassing op:** apparaten waarvan de firmware antwoordt op de
> firmwareversieregisters 10062–10063 (zie [Firmware-versiecontrole](#firmware-versiecontrole)).
> Dit zijn de **v2-registeradressen**. De minimale firmware-versie verschilt per
> model: Lyra serie 1.01.16, CBE2000 Pro 1.02.17, Atlas 6000 AC 1.01.08 of nieuwer.
> Firmware onder deze versies: gebruik
> [balcony-solar-storage.nl.md](balcony-solar-storage.nl.md) (v1-registeroverzicht).

Talen / Language / 语言 / Sprache: [English](balcony-solar-storage-v2.md) · [简体中文](balcony-solar-storage-v2.zh-CN.md) · [Deutsch](balcony-solar-storage-v2.de.md) · **Nederlands**

---

## Inhoudsopgave

- [1 Overzicht](#1-overzicht)
  - [Firmware-versiecontrole](#firmware-versiecontrole)
  - [Migreren vanaf v1](#migreren-vanaf-v1)
  - [Transport- en verbindingsparameters](#transport--en-verbindingsparameters)
  - [Verificatiecode (directe Modbus TCP, all-in-one-apparaten)](#verificatiecode-directe-modbus-tcp-all-in-one-apparaten)
  - [Gelijktijdige RTU en TCP (schrijfprioriteit)](#gelijktijdige-rtu-en-tcp-schrijfprioriteit)
  - [Hardware-aansluiting](#hardware-aansluiting)
  - [Vereisten](#vereisten)
- [2 Datatypes](#2-datatypes)
- [3 Registeroverzicht](#3-registeroverzicht)
  - [3.1 Realtime monitoring (10000–10011)](#31-realtime-monitoring-1000010011)
  - [3.2 Gedetailleerde monitoring (10012–10043)](#32-gedetailleerde-monitoring-1001210043)
  - [3.3 Bedrijfsparameters en apparaatinfo (10044–10063)](#33-bedrijfsparameters-en-apparaatinfo-1004410063)
  - [3.4 Levenslange energietellers (10064–10081)](#34-levenslange-energietellers-1006410081)
  - [3.5 Besturing — vermogens- en SoC-instellingen (10100–10102)](#35-besturing--vermogens--en-soc-instellingen-1010010102)
  - [3.6 Besturing — realtime geforceerd laden/ontladen (10103–10106)](#36-besturing--realtime-geforceerd-ladenontladen-1010310106)
  - [3.7 Besturing — bedrijfsstrategie (10107–10114)](#37-besturing--bedrijfsstrategie-1010710114)
  - [3.8 Besturing — generator en digitale uitgangen (10115–10122)](#38-besturing--generator-en-digitale-uitgangen-1011510122)
  - [3.9 Besturing — basislast (10123–10148)](#39-besturing--basislast-1012310148)
  - [3.10 Besturing — handmatig laad-/ontlaadschema TOU (10149–10189)](#310-besturing--handmatig-laad-ontlaadschema-tou-1014910189)
  - [3.11 Besturing — tijdkalibratie (10190)](#311-besturing--tijdkalibratie-10190)
  - [3.12 Protocolregisters (9984–9986)](#312-protocolregisters-99849986)
- [4 Framevoorbeelden](#4-framevoorbeelden)
  - [Modbus TCP-framestructuur (MBAP)](#modbus-tcp-framestructuur-mbap)
  - [Snelle test via de commandoregel](#snelle-test-via-de-commandoregel)
- [5 Belangrijke opmerkingen](#5-belangrijke-opmerkingen)
- [6 Probleemoplossing](#6-probleemoplossing)
  - [6.1 Modbus-exceptioncodes](#61-modbus-exceptioncodes)
  - [6.2 Apparaatfoutcode (alarmbitmap, 10001–10002)](#62-apparaatfoutcode-alarmbitmap-1000110002)

---

## 1 Overzicht

Deze gids documenteert de **Modbus RTU/TCP-interface van CONOW
balkon-zonne-energieopslag en all-in-one energieapparaten met v2-firmware** — CBE-serie (CBE2000 Pro), Lyra serie (Lyra 2500 AC, Lyra 2500 Pro)
en Atlas serie (Atlas 6000 AC).

Ten opzichte van het [v1-registeroverzicht](balcony-solar-storage.nl.md) brengt
de v2-firmware:

- Een monitoringgebied (10000–10081): CT-/metergegevens, vermogen per netfase,
  spanning/stroom/energie per PV-string, de door het apparaat gerapporteerde
  batterijlimieten, SOH, serienummer en firmwareversie.
- Een besturingsgebied (10100–10190): bedrijfsstrategieën, bedrijfsmodus,
  terugleverbegrenzing, Modbus-timeout, basislastschema, een handmatig
  laad-/ontlaadschema (TOU) met elk tot 8 tijdvakken en een
  tijdkalibratieregister.
- **Directe Modbus TCP** op all-in-one-apparaten (poort 502), beveiligd met
  een **dynamische verificatiecode** — RTU en TCP zijn tegelijk bruikbaar,
  onder een RTU-prioriteitsregel voor schrijfarbitrage.
- **Atomaire groepsschrijfacties** — meerdere besturingswaarden moeten
  samen in één FC 0x10-frame worden geschreven.

### Firmware-versiecontrole

De twee registeroverzichten sluiten elkaar uit: een apparaat antwoordt of op de v1-adressen of op de v2-adressen, nooit op beide. De minimale firmware-versie die het v2-registeroverzicht activeert, verschilt per model:

| Model | Minimale firmware |
| --- | --- |
| Lyra serie | 1.01.16 |
| CBE2000 Pro | 1.02.17 |
| Atlas 6000 AC | 1.01.08 |

Firmware onder deze versies gebruikt standaard de v1-registeradressen. Weet je niet zeker welk overzicht een apparaat gebruikt, controleer dit eenmaal na het verbinden:

1. Lees het firmwareversieveld **10062 (0x274E), aantal 2** (10062–10063) met FC 0x03.
2. Kies de gids aan de hand van het antwoord:

   - **Het apparaat antwoordt** — de firmware implementeert dit registerbereik, is dus op of boven de minimale versie voor het model, en het apparaat gebruikt het v2-registeroverzicht. Blijf deze gids volgen.
   - **Geen antwoord, een timeout of een Modbus-exception** — de firmware implementeert dit registerbereik niet, is dus onder de minimale versie voor het model. Ga verder met [balcony-solar-storage.nl.md](balcony-solar-storage.nl.md).

Opmerkingen:

- Het firmwareversieveld (10062–10063, U16[2] ASCII) **beantwoordt geen losse
  register-leesopdrachten** — vraag beide registers in één frame op.
- Voor het serienummerveld (10054–10061, U16[8] ASCII) geldt dezelfde
  beperking: lees alle 8 registers in één opdracht.

### Migreren vanaf v1

De besturingsadressen zijn tussen de overzichten verschoven — map een bestaande v1-integratie vóór het schrijven opnieuw:

| Functie | v1 | v2 |
| --- | --- | --- |
| AC-laadvermogenlimiet | 10100 | 10100 — ongewijzigd |
| Ontlaadvermogenlimiet | 10101 | 10101 — ongewijzigd |
| Back-up-SoC | 10102 | 10102 — ongewijzigd |
| Laad-/ontlaadrichting | 10105 | 10103 |
| Doel-laad-/ontlaadvermogen | 10106 | 10104 |
| Stop-SoC laden/ontladen | 10107 | 10105 |

De v1-schrijfvolgorde (10106 → 10105 → 10107, FC 0x06) geldt op v2 **niet**: 10103–10106 worden als één atomaire FC 0x10-groep geschreven (alleen richting = 3 accepteert één register).

De v1-schakelaars voor de noodstroomuitgang (10103) en PV-afregeling (10104) hebben op v2 geen tegenhanger op deze adressen — 10103/10104 zijn daar het richtings- en het vermogensregister; controleer vóór migratie van deze functies de besturingstabellen.

Ook de monitoringregisters zijn opnieuw gegroepeerd — verifieer vóór het pollen elk adres tegen de v2-tabellen.

Ook de tekenconventie van het actieve netvermogen is gewijzigd: op v1 rapporteert de CBE2000 Pro positief = teruglevering en negatief = afname, Lyra / Atlas positief = afname en negatief = teruglevering; op v2 rapporteren alle modellen positief = afname van het net en negatief = teruglevering aan het net (10006, 10013).

### Transport- en verbindingsparameters

| Parameter | Waarde |
| --- | --- |
| Transport | RS-485 Modbus RTU, of Modbus TCP (all-in-one-apparaten, TCP-poort **502**) |
| Seriële parameters (RTU) | **38400** baud, 8 databits, geen pariteit, 1 stopbit (8N1) |
| Standaard slave-/unit-ID | **160 (0xA0)** |
| Unit-ID-bereik | 128–176 (0x80–0xB0); de ID is leesbaar en schrijfbaar in register **9984 (0x2700)**; wijzigen vereist geen hernieuwde TCP-verificatie |
| Functiecodes | 0x03 lezen · 0x06 één schrijven · 0x10 meerdere schrijven |
| Leeslimiet | één FC 0x03-verzoek bedient maximaal **127** registers; een langer verzoek krijgt geen antwoord. De Modbus-specificatie begrenst leesopdrachten tot 125 registers — ontwerp voor maximaal 125 |

### Verificatiecode (directe Modbus TCP, all-in-one-apparaten)

**Modbus RTU heeft geen verificatiecode nodig; directe Modbus TCP vereist dat
de TCP-schakelaar in de app is ingeschakeld en de verificatie is voltooid.**
Verbind via TCP en schrijf daarna de 8-tekens hexadecimale verificatiecode
(op te halen via de apparaatdetailpagina in de CONOW-app) naar het apparaat:

- Schrijf deze als een **uint32** naar holding registers
  **9985–9986 (0x2701–0x2702)**, hoogste woord eerst.
- De code is **dynamisch en ververst elke 120 seconden**,
  totdat de verificatie slaagt; daarna stopt het verversen. Als het apparaat
  de code afwijst, lees dan de nieuwe code uit de app en schrijf hem
  opnieuw.
- **Verificatievergrendeling:** na 5 opeenvolgende mislukte verificaties
  binnen 5 minuten wordt de TCP-verificatie 5 minuten vergrendeld — tijdens
  de vergrendeling kan de verificatie niet worden voltooid en worden
  TCP-lees- en schrijfopdrachten beantwoord met exception 0x02 (uitzondering:
  het lezen van unit-ID-register 9984); wacht tot de vergrendeling voorbij
  is, lees daarna een nieuwe code uit de app en schrijf deze opnieuw.
- Verificatie moet opnieuw worden gedaan nadat de Modbus-schakelaar in de app
  opnieuw is ingeschakeld, nadat het MAC-adres van de adapter wijzigt, of na
  een handmatige verversing.
- Het apparaat vraagt om verificatie door verzoeken te beantwoorden met een
  **Modbus-exception** — een verbonden maar ongeverifieerd verzoek krijgt een
  verificatiefout, terwijl een niet-verbonden endpoint stil blijft; verwissel
  de twee gevallen niet. Zodra een verzoek normaal is beantwoord, wordt de
  code **niet** bij elke poll opnieuw verstuurd — schrijf hem alleen wanneer
  erom wordt gevraagd en na een codewijziging.

RTU over RS-485 (en Modbus TCP via een RS-485-naar-ethernet-gateway) heeft
geen verificatiecode nodig.

### Gelijktijdige RTU en TCP (schrijfprioriteit)

De app biedt **onafhankelijke RTU- en TCP-schakelaars**, en beide kanalen
kunnen tegelijk ingeschakeld zijn. RTU-leesopdrachten (FC 0x03) werken
rechtstreeks; TCP-lees- en schrijfacties vereisen eerst de verificatie via
9985–9986. Schrijfframes (FC 0x06 / 0x10) volgen een **regel met één schrijver
en RTU-prioriteit**:

- Zolang de RTU-zijde de schrijfrechten houdt — elk geldig schrijfframe
  binnen het watchdogvenster van 10114 — worden geverifieerde
  TCP-schrijfacties zonder bevestiging en zonder uitvoering geweigerd.
  Geverifieerde TCP-leesopdrachten blijven werken.
- Valt de RTU-verbinding weg of blijft de RTU-zijde langer dan de timeout
  van 10114 stil, dan komen de schrijfrechten vrij en worden geverifieerde
  TCP-schrijfacties uitgevoerd. Elk nieuw RTU-schrijfframe pakt de schrijfrechten direct terug; TCP kan RTU
  niet verdringen.
- Verificatie (9985–9986) is een voorwaarde voor TCP-lees- en schrijfacties,
  geen manier om schrijfrechten te verkrijgen — de twee zijn onafhankelijk.

Bedrijf telkens maar één schrijvende master. Een TCP-schrijfactie die wordt
beantwoord met exception 0x86 (FC 0x06) of 0x90 (FC 0x10) is verwacht gedrag
van de schrijfprioriteit, geen verbindingsfout. Het wordt aangeraden naar
praktische behoefte één besturingsmethode in te schakelen.

### Hardware-aansluiting

De aansluiting is identiek aan de v1-gids — pinbezetting en
aansluitschema's staan daar in de sectie
[Hardware-interface](balcony-solar-storage.nl.md#12-hardware-interface).

### Vereisten

Het apparaat moet via de **CONOW ECO App** in bedrijf zijn gesteld en
minstens eenmaal online zijn geweest — een fabrieksnieuw, nooit geactiveerd
apparaat beantwoordt geen enkel verzoek op de RS-485-interface.

1. Schakel in de app onder *Apparaten → jouw apparaat → Instellingen* de
   optie *Modbus-service inschakelen* in; schakel voor directe TCP ook de
   TCP-schakelaar in. Ontbreekt de schakelaar in oudere app-versies, kies dan
   onder *Instellingen → Bedrijfsmodus* voor *DIY-modus*.
2. Houd schrijfacties telkens bij één master — zie
   [Gelijktijdige RTU en TCP](#gelijktijdige-rtu-en-tcp-schrijfprioriteit).

---

## 2 Datatypes

| Type | Codering |
| --- | --- |
| `uint16` | 1 register, zonder teken |
| `int16` | 1 register, tweeëncomplement; tekenbetekenis volgens de registerbeschrijving |
| `uint32` | 2 registers, **big-endian, hoogste woord eerst** — `value = (reg[n] << 16) \| reg[n+1]` |
| `string` | U16-array, 2 ASCII-tekens per register (hoogste byte eerst), opgevuld met 0x00 |
| `hhmm`-tijd | 1 register: hoogste byte = uur, laagste byte = minuut (bijvoorbeeld `06:30` → `0x06 0x1E` → `0x061E` = 1566) |
| Schaal | Fysische waarde = ruwe waarde × schaal (schaal 1 tenzij vermeld) |
| Enums / booleans | waardetabellen per register hieronder |

---

## 3 Registeroverzicht

Drie gebieden, niet aaneengesloten:

| Gebied | Registers | Toegang |
| --- | --- | --- |
| Monitoring | **10000–10081** (0x2710–0x2761) | alleen lezen, FC 0x03 |
| Besturing | **10100–10190** (0x2774–0x27CE) | lezen FC 0x03 · schrijven FC 0x06 / 0x10 — behalve 10103–10106: alleen één atomaire FC 0x10-groepsactie (richting = 3 accepteert ook FC 0x06) |
| Protocol | 9984 (unit-ID, lezen/schrijven) · 9985–9986 (verificatiecode, WO) | zie 3.12; werkwijze in de secties hierboven |

Anders dan v1-firmware (die losse leesopdrachten over 38 registers of meer
stilzwijgend negeert) bedient v2-firmware leesopdrachten over hele gebieden —
de referentie-Home-Assistant-integratie pollt het volledige monitoringgebied
(82 registers) en het volledige besturingsgebied (91 registers) elk met één
FC 0x03-verzoek. Als jouw gateway of tool problemen heeft met lange frames,
splits de leesopdrachten dan bij de groepsgrenzen hieronder.

### 3.1 Realtime monitoring (10000–10011)

| Register | Hex | Naam | Type | Eenheid | Schaal | Opmerkingen |
| --- | --- | --- | --- | --- | --- | --- |
| 10000 | 0x2710 | Systeemstatus | uint16 | — | — | bitveld — zie de bittabel hieronder |
| 10001–10002 | 0x2711 | Apparaatfoutcode | uint32 | — | — | [6.2 Alarmbitmap](#62-apparaatfoutcode-alarmbitmap-1000110002); lees 10001–10002 samen |
| 10003 | 0x2713 | Systeem-SoC | uint16 | % | 1 | 0–100 |
| 10004 | 0x2714 | Meterverbindingsstatus | enum | — | — | 0 = gekoppeld en verbonden · 1 = niet gekoppeld en niet verbonden · 2 = gekoppeld, niet verbonden |
| 10005 | 0x2715 | Totaalvermogen meter | int16 | W | 1 | Positief = afname van het net; negatief = teruglevering aan het net |
| 10006 | 0x2716 | Actief vermogen net | int16 | W | 1 | Positief = afname van het net / batterij laden; negatief = teruglevering aan het net / batterij ontladen |
| 10007 | 0x2717 | Totaal PV-vermogen | uint16 | W | 1 | — |
| 10008 | 0x2718 | Bedrijfsstatus batterij | enum | — | — | 0 = inactief · 1 = laden · 2 = ontladen; meldt de werkelijke toestand, geen echo van de opdracht |
| 10009 | 0x2719 | Batterijvermogen | int16 | W | 1 | Positief = laden; negatief = ontladen |
| 10010 | 0x271A | Bypass-schakelstatus | enum | — | — | 0 = uit · 1 = aan |
| 10011 | 0x271B | Bypass-vermogen | int16 | W | 1 | Positief = ontladen naar de bypass; negatief = laden vanuit de bypass |

**Systeemstatus (10000) bitveld** — deze status meldt de werkelijke toestand
van de batterijpoort, geen echo van de opdracht:

| Bit | Betekenis | Bit gezet (= 1) betekent |
| --- | --- | --- |
| 0 | Standby | batterijpoort is in standby |
| 1 | Gereserveerd | gereserveerd |
| 2 | Fout | fout actief — lees de foutcode op 10001–10002 ([6.2 Alarmbitmap](#62-apparaatfoutcode-alarmbitmap-1000110002)) |
| 3 | Laden | batterij laadt |
| 4 | Ontladen | batterij ontlaadt |
| 5–15 | Gereserveerd | negeren |

Voorbeeld: een uitlezing van 0x0008 (alleen bit 3 gezet) betekent dat de
batterijpoort laadt; 0x0001 (alleen bit 0 gezet) betekent standby.

### 3.2 Gedetailleerde monitoring (10012–10043)

| Register | Hex | Naam | Type | Eenheid | Schaal | Opmerkingen |
| --- | --- | --- | --- | --- | --- | --- |
| 10012 | 0x271C | Netspanning | uint16 | V | 0.1 | fasespanning; fase A bij driefasige modellen |
| 10013 | 0x271D | Netstroom | int16 | A | 0.1 | Positief = afname; negatief = teruglevering |
| 10014 | 0x271E | Netfrequentie | uint16 | Hz | 0.01 | — |
| 10015 | 0x271F | Vermogen fase A | int16 | W | 1 | driefasige modellen |
| 10016 | 0x2720 | Vermogen fase B | int16 | W | 1 | driefasige modellen |
| 10017 | 0x2721 | Vermogen fase C | int16 | W | 1 | driefasige modellen |
| 10018 | 0x2722 | Aantal PV-strings | uint16 | — | — | leest N = N ondersteunde strings; niet-ondersteunde strings lezen 0 |
| 10019 | 0x2723 | PV1-spanning | uint16 | V | 0.1 | — |
| 10020 | 0x2724 | PV1-stroom | uint16 | A | 0.1 | — |
| 10021–10022 | 0x2725 | PV1-energie | uint32 | kWh | 0.01 | hoogste woord eerst |
| 10023 | 0x2727 | PV2-spanning | uint16 | V | 0.1 | — |
| 10024 | 0x2728 | PV2-stroom | uint16 | A | 0.1 | — |
| 10025–10026 | 0x2729 | PV2-energie | uint32 | kWh | 0.01 | hoogste woord eerst |
| 10027 | 0x272B | PV3-spanning | uint16 | V | 0.1 | — |
| 10028 | 0x272C | PV3-stroom | uint16 | A | 0.1 | — |
| 10029–10030 | 0x272D | PV3-energie | uint32 | kWh | 0.01 | hoogste woord eerst |
| 10031 | 0x272F | PV4-spanning | uint16 | V | 0.1 | — |
| 10032 | 0x2730 | PV4-stroom | uint16 | A | 0.1 | — |
| 10033–10034 | 0x2731 | PV4-energie | uint32 | kWh | 0.01 | hoogste woord eerst |
| 10035 | 0x2733 | Batterijspanning | uint16 | V | 0.01 | DC-busspanning |
| 10036 | 0x2734 | Batterijstroom | int16 | A | 0.1 | Positief = laden; negatief = ontladen |
| 10037 | 0x2735 | Celtemperatuur max | **int16** | °C | 0.1 | met teken — geen offsetcodering |
| 10038 | 0x2736 | Celtemperatuur min | **int16** | °C | 0.1 | met teken — geen offsetcodering |
| 10039 | 0x2737 | Max. laadvermogen batterij | uint16 | W | 1 | momenteel toegestaan laadvermogen; kan bij terugregeling door temperatuur / SoC onder de 10100-instelling liggen |
| 10040 | 0x2738 | Max. ontlaadvermogen batterij | uint16 | W | 1 | momenteel toegestaan ontlaadvermogen; kan bij terugregeling door temperatuur / SoC onder de 10101-instelling liggen |
| 10041 | 0x2739 | Bypass-spanning | uint16 | V | 0.1 | — |
| 10042 | 0x273A | Bypass-stroom | uint16 | A | 0.1 | — |
| 10043 | 0x273B | Bypass-frequentie | uint16 | Hz | 0.01 | — |

### 3.3 Bedrijfsparameters en apparaatinfo (10044–10063)

De serienummer- en firmwareversievelden beantwoorden geen losse
register-leesopdrachten. Lees elk veld volledig in één opdracht — serienummer
10054 (0x2746) × 8, firmwareversie 10062 (0x274E) × 2.

| Register | Hex | Naam | Type | Eenheid | Schaal | Opmerkingen |
| --- | --- | --- | --- | --- | --- | --- |
| 10044 | 0x273C | Nominale capaciteit | uint16 | kWh | 0.01 | nominale capaciteit van de batterijpack |
| 10045 | 0x273D | Resterende capaciteit | uint16 | kWh | 0.01 | momenteel opgeslagen batterijenergie |
| 10046 | 0x273E | Systeem-back-up-SoC | uint16 | % | 1 | spiegelt de geschreven veiligheids-SoC (10102) |
| 10047 | 0x273F | SOH | uint16 | % | 1 | 0–100 |
| 10048 | 0x2740 | Max. AC-laadvermogen (hardware) | uint16 | W | 1 | hardwarebovengrens van het apparaat, fabrieksvast, niet wijzigbaar |
| 10049 | 0x2741 | Max. AC-ontlaadvermogen (hardware) | uint16 | W | 1 | hardwarebovengrens van het apparaat, fabrieksvast, niet wijzigbaar |
| 10050 | 0x2742 | Terugleverlimiet netcode | uint16 | W | 1 | lokaal toegestane terugleververmogenslimiet; fabrieksgesloten op de netcode-standaardwaarde, = 10049 na ontgrendeling in de app — ontgrendelen kan alleen in de app, niet schrijfbaar via Modbus |
| 10051 | 0x2743 | Globale AC-laadvermogenlimiet | uint16 | W | 1 | spiegelt het geschreven 10100 |
| 10052 | 0x2744 | Globale AC-ontlaadvermogenlimiet | uint16 | W | 1 | spiegelt het geschreven 10101 |
| 10053 | 0x2745 | Wi-Fi-signaal | int16 | dBm | 1 | altijd negatief; bijvoorbeeld -60 |
| 10054–10061 | 0x2746 | Serienummer | string[8] | U16[8] ASCII | — | 8 registers = 16 bytes; geen losse register-leesopdrachten — lees het hele veld |
| 10062–10063 | 0x274E | Firmwareversie | string[2] | U16[2] ASCII | — | 2 registers = 4 bytes; geen losse register-leesopdrachten — lees het hele veld |

### 3.4 Levenslange energietellers (10064–10081)

Alle uint32, kWh × 0.01, hoogste woord eerst, alleen lezen, monoton toenemend.

| Register | Hex | Naam | Type | Eenheid | Schaal | Opmerkingen |
| --- | --- | --- | --- | --- | --- | --- |
| 10064–10065 | 0x2750 | Totaal netafname | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10066–10067 | 0x2752 | Totaal netteruglevering | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10068–10069 | 0x2754 | Totaal meterafname | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10070–10071 | 0x2756 | Totaal meterteruglevering | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10072–10073 | 0x2758 | Totale PV-opbrengst | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10074–10075 | 0x275A | Totaal laadenergie batterij | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10076–10077 | 0x275C | Totaal ontlaadenergie batterij | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10078–10079 | 0x275E | Totaal bypass-uitgangsenergie | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |
| 10080–10081 | 0x2760 | Totaal bypass-invoerenergie | uint32 | kWh | 0.01 | alleen lezen; monoton toenemend |

### 3.5 Besturing — vermogens- en SoC-instellingen (10100–10102)

De drie registers in deze groep kunnen afzonderlijk met FC 0x06 of samen met
FC 0x10 worden geschreven; alle drie blijven bewaard na spanningsuitval.
Alleen 10103–10106 moeten als één atomaire FC 0x10-groep worden geschreven.

| Register | Hex | Naam | Type | Eenheid | Opmerkingen |
| --- | --- | --- | --- | --- | --- |
| 10100 | 0x2774 | AC-laadvermogenlimiet | uint16 | W | standaard 800; schrijfbaar bereik 50 tot hardwaremaximum (10048); schrijfacties buiten het bereik geven een exception-code terug; blijft bewaard na spanningsuitval |
| 10101 | 0x2775 | AC-ontlaadvermogenlimiet | uint16 | W | schrijfbare ondergrens 100; schrijfbare bovengrens = lokale netcode-terugleverwaarde zolang geblokkeerd, hardwaremaximum (10049) na ontgrendeling in de app; blijft bewaard na spanningsuitval |
| 10102 | 0x2776 | Veiligheids-SoC | uint16 | % | 10–100, standaard 20; buiten het bereik → Modbus-exception 0x03; blijft bewaard na spanningsuitval |

### 3.6 Besturing — realtime geforceerd laden/ontladen (10103–10106)

Het apparaat ondersteunt voor deze groep **expliciet geen losse
registerschrijfacties** (één uitzondering: richtingswaarde 3 "afsluiten" mag
alleen met FC 0x06 worden geschreven). Schrijf alle vier de registers in **één
FC 0x10-frame**. De groep is vluchtig en eindigt zodra **ofwel** de stop-SoC
**ofwel** de duur is bereikt — wat het eerst plaatsvindt. Na een
Modbus-timeout (zie 10114) valt het apparaat terug op de CONOW-platformmodus
die actief was voordat de Modbus-service werd ingeschakeld.

10104 is een **directe uitgangsinstelling**: het apparaat levert het
ingestelde vermogen ongeacht de belasting. Lastvolgend gedrag wordt gekozen
met de bedrijfsmodus (10107) in de app en vereist een aangesloten meter.

| Register | Hex | Naam | Type | Eenheid | Opmerkingen |
| --- | --- | --- | --- | --- | --- |
| 10103 | 0x2777 | Laad-/ontlaadrichting | uint16 | — | 0 = inactief · 1 = laden · 2 = ontladen · 3 = afsluiten; richting 3 (afsluiten) mag los met FC 0x06 worden geschreven |
| 10104 | 0x2778 | Doel-laad-/ontlaadvermogen | uint16 | W | 0 tot de via 10100 / 10101 ingestelde limiet; een waarde boven de limiet wordt automatisch als de limiet geschreven — geen exception |
| 10105 | 0x2779 | Stop-SoC laden/ontladen | uint16 | % | veiligheids-SoC (10102) tot 100; bij ontladen wordt een waarde onder de veiligheids-SoC automatisch als 10102 geschreven — geen exception |
| 10106 | 0x277A | Duur laden/ontladen | uint16 | min | 30–720; eindigt zodra de duur of de stop-SoC het eerst is bereikt |

### 3.7 Besturing — bedrijfsstrategie (10107–10114)

Alle registers in deze groep blijven bewaard na spanningsuitval. Registers
gemarkeerd als *gereserveerd* bestaan in het overzicht maar zijn op huidige
hardware nog niet functioneel.

| Register | Hex | Naam | Type | Eenheid | Opmerkingen |
| --- | --- | --- | --- | --- | --- |
| 10107 | 0x277B | Bedrijfsmodus | uint16 | — | 1 = zelfverbruik · 2 = handmatige tijdvakken · 3 = inactief; standaard 1; **eerst lezen, dan schrijven**; met een meter volgt het apparaat het metervermogen, zonder meter levert het de basislast; blijft bewaard na spanningsuitval |
| 10108 | 0x277C | Back-up-SoC | uint16 | % | veiligheids-SoC (10102) tot 100, standaard 40; *gereserveerd* (back-upstroommodus, nog niet ondersteund); blijft bewaard na spanningsuitval |
| 10109 | 0x277D | Toegestaan terugleververmogen | uint16 | W | 0 = geen teruglevering; groter dan 0 = maximaal toegestaan terugleververmogen; schrijfbaar maar zonder aangesloten meter zonder effect; blijft bewaard na spanningsuitval |
| 10110 | 0x277E | Terugleveren vanuit batterij toestaan | uint16 | — | 0 = verboden · 1 = toegestaan; *gereserveerd* (teruglevermodus, nog niet ondersteund); blijft bewaard na spanningsuitval |
| 10111 | 0x277F | Bypass-altijd-aan-schakelaar | uint16 | — | 0 = uit · 1 = aan; standaard uit; blijft bewaard na spanningsuitval |
| 10112 | 0x2780 | Noodstroom-uitgangsschakelaar | uint16 | — | 0 = uit · 1 = aan; standaard uit; blijft bewaard na spanningsuitval |
| 10113 | 0x2781 | PV-afregelschakelaar | uint16 | — | 0 = uit · 1 = aan; standaard uit; *gereserveerd, nog niet ondersteund*; blijft bewaard na spanningsuitval |
| 10114 | 0x2782 | Modbus-timeout | uint16 | s | 0–3600, 0 = uitgeschakeld (standaard); watchdog — zo lang zonder geldig **schrijf**frame valt het apparaat terug op de CONOW-platformmodus die actief was vóór het inschakelen van de Modbus-service; blijft bewaard na spanningsuitval |

### 3.8 Besturing — generator en digitale uitgangen (10115–10122)

Op modellen zonder generatorfunctie lezen de registers 0 en
geven schrijfacties een exception terug. De twee DO-registers zijn vluchtig;
de rest blijft bewaard na spanningsuitval.

| Register | Hex | Naam | Type | Eenheid | Opmerkingen |
| --- | --- | --- | --- | --- | --- |
| 10115 | 0x2783 | Generatorschakelaar | uint16 | — | 0 = uit · 1 = aan; blijft bewaard na spanningsuitval |
| 10116 | 0x2784 | Generatorstarttijd | uint16 | hhmm | uur in de hoogste byte (0–23), minuut in de laagste byte (0–59); blijft bewaard na spanningsuitval |
| 10117 | 0x2785 | Generatorstoptijd | uint16 | hhmm | uur in de hoogste byte (0–23), minuut in de laagste byte (0–59); blijft bewaard na spanningsuitval |
| 10118 | 0x2786 | Generatorvermogen | uint16 | W | blijft bewaard na spanningsuitval |
| 10119 | 0x2787 | Generatorstart-SoC | uint16 | % | doel-SoC die het opladen via de generator start; blijft bewaard na spanningsuitval |
| 10120 | 0x2788 | Generatorstop-SoC | uint16 | % | stop-SoC die het opladen via de generator beëindigt; blijft bewaard na spanningsuitval |
| 10121 | 0x2789 | DO1-besturing | uint16 | — | 0 = uit · 1 = aan; vluchtig |
| 10122 | 0x278A | DO2-besturing | uint16 | — | 0 = uit · 1 = aan; vluchtig |

### 3.9 Besturing — basislast (10123–10148)

Wanneer geen meter is aangesloten (of de meter defect is), levert het apparaat
buiten de ingestelde tijdvakken het basislast-instelpunt; de instelling blijft
bewaard na spanningsuitval.

<strong>Opmerking over cloudsynchronisatie:</strong> Na een herstart kunnen, wanneer de
cloudverbinding beschikbaar is, Toegestaan terugleververmogen (10109),
Basislast (10123) en het basislastschema (10124–10148) worden gesynchroniseerd
met de waarden die in de CONOW-app zijn ingesteld, waardoor de huidige waarden
worden overschreven. Schrijf deze registers opnieuw als de Modbus-instellingen
behouden moeten blijven.

| Register | Hex | Naam | Type | Eenheid | Opmerkingen |
| --- | --- | --- | --- | --- | --- |
| 10123 | 0x278B | Basislast | uint16 | W | 0–3000, standaard 200; blijft bewaard na spanningsuitval |
| 10124 | 0x278C | Basislast-tijdvakkentelling | uint16 | — | 0–8; het apparaat voert alleen de eerste N tijdvakken uit |

**Basislastschema** — een tijdvakkentelling (0–8), gevolgd door 8 tijdvakken
van (start, einde, vermogen). Schrijf alleen de eerste N tijdvakken die je
daadwerkelijk gebruikt en zet het tellingregister op N; het apparaat voert
alleen de eerste N tijdvakken uit en negeert de rest. Alle hhmm-registers
coderen het uur in de hoogste byte en de minuut in de laagste byte.

| Tijdvak | Start | Einde | Vermogen |
| --- | --- | --- | --- |
| 1 | 10125 (0x278D) | 10126 (0x278E) | 10127 (0x278F) |
| 2 | 10128 (0x2790) | 10129 (0x2791) | 10130 (0x2792) |
| 3 | 10131 (0x2793) | 10132 (0x2794) | 10133 (0x2795) |
| 4 | 10134 (0x2796) | 10135 (0x2797) | 10136 (0x2798) |
| 5 | 10137 (0x2799) | 10138 (0x279A) | 10139 (0x279B) |
| 6 | 10140 (0x279C) | 10141 (0x279D) | 10142 (0x279E) |
| 7 | 10143 (0x279F) | 10144 (0x27A0) | 10145 (0x27A1) |
| 8 | 10146 (0x27A2) | 10147 (0x27A3) | 10148 (0x27A4) |

Vermogensbereik per tijdvak 0–3000 W.

### 3.10 Besturing — handmatig laad-/ontlaadschema TOU (10149–10189)

Bedrijfsmodus 2 (handmatige tijdvakken) voert dit schema uit: tot 8 strategieën,
elk een tijdvenster dat naar een doel-SoC laadt of met een ingesteld vermogen
ontlaadt. Schrijf alleen de eerste N tijdvakken die je daadwerkelijk gebruikt
en zet het tellingregister (**10149, 0x27A5**, 0–8) op N; het apparaat voert
alleen de eerste N tijdvakken uit. Blijft bewaard na spanningsuitval.

| Register | Hex | Naam | Type | Eenheid | Opmerkingen |
| --- | --- | --- | --- | --- | --- |
| 10149 | 0x27A5 | TOU-tijdvakkentelling | uint16 | — | 0–8; het apparaat voert alleen de eerste N tijdvakken uit; blijft bewaard na spanningsuitval |

Tijd buiten de geconfigureerde tijdvakken volgt de **baseline-strategie**.
De baseline kent twee strategieën — zelfverbruik en idle — en is standaard
idle; de baseline wordt in de CONOW-app aangepast.

Elk tijdvak bestaat uit 5 registers — start, einde, modus, en daarna één van
doel-SoC / ontlaadvermogen (het inactieve veld wordt genegeerd):

| Veld | Betekenis |
| --- | --- |
| start / einde | hhmm (uur hoogste byte, minuut laagste byte) |
| modus | 0 = laden (alleen doel-SoC geldt) · 1 = ontladen (alleen ontlaadvermogen geldt) |
| doel-SoC | uint16 %, geldt bij modus = 0 |
| ontlaadvermogen | uint16 W, geldt bij modus = 1 |

| Tijdvak | Start | Einde | Modus | Doel-SoC | Ontlaadvermogen |
| --- | --- | --- | --- | --- | --- |
| 1 | 10150 (0x27A6) | 10151 (0x27A7) | 10152 (0x27A8) | 10153 (0x27A9) | 10154 (0x27AA) |
| 2 | 10155 (0x27AB) | 10156 (0x27AC) | 10157 (0x27AD) | 10158 (0x27AE) | 10159 (0x27AF) |
| 3 | 10160 (0x27B0) | 10161 (0x27B1) | 10162 (0x27B2) | 10163 (0x27B3) | 10164 (0x27B4) |
| 4 | 10165 (0x27B5) | 10166 (0x27B6) | 10167 (0x27B7) | 10168 (0x27B8) | 10169 (0x27B9) |
| 5 | 10170 (0x27BA) | 10171 (0x27BB) | 10172 (0x27BC) | 10173 (0x27BD) | 10174 (0x27BE) |
| 6 | 10175 (0x27BF) | 10176 (0x27C0) | 10177 (0x27C1) | 10178 (0x27C2) | 10179 (0x27C3) |
| 7 | 10180 (0x27C4) | 10181 (0x27C5) | 10182 (0x27C6) | 10183 (0x27C7) | 10184 (0x27C8) |
| 8 | 10185 (0x27C9) | 10186 (0x27CA) | 10187 (0x27CB) | 10188 (0x27CC) | 10189 (0x27CD) |

### 3.11 Besturing — tijdkalibratie (10190)

Zolang het apparaat offline is van de cloud kan zijn klok drift vertonen, en
dan draaien TOU- of basislasttijdvakken op de verkeerde tijden. Lees de
apparaattijd en kalibreer deze met één schrijfactie als hij is gedreven —
controleer eerst dat je eigen tijdbron correct is.

| Register | Hex | Naam | Type | Eenheid | Schaal | Opmerkingen |
| --- | --- | --- | --- | --- | --- | --- |
| 10190 | 0x27CE | Apparaattijd van de dag (lezen / kalibreren) | uint16 | hhmm | — | uur in de hoogste byte (0–23), minuut in de laagste byte (0–59); kalibreert alleen de tijd van de dag — zonder datum, weekdag of tijdzone; vluchtig |

### 3.12 Protocolregisters (9984–9986)

Identiteits- en verificatieregisters die beide transportwegen delen; de werkwijze staat in de secties hierboven.

| Register | Hex | Naam | Type | Eenheid | Opmerkingen |
| --- | --- | --- | --- | --- | --- |
| 9984 | 0x2700 | Unit-ID | uint16 | — | RTU-slaveadres en TCP-unit-ID; leesbaar en schrijfbaar, bereik 128–176 (0x80–0xB0); wijzigen vereist geen hernieuwde TCP-verificatie |
| 9985–9986 | 0x2701 | TCP-verificatiecode | uint32 | — | alleen schrijven; de dynamische 8-tekens hexadecimale code van de apparaatdetailpagina in de CONOW-app (ververst elke 120 seconden); zie [Verificatiecode](#verificatiecode-directe-modbus-tcp-all-in-one-apparaten) |

---

## 4 Framevoorbeelden

Framing en CRC-16 (Modbus) zijn identiek aan de v1-gids: slave `0xA0`,
functiecode, data, CRC laagste byte eerst. De onderstaande voorbeelden zijn
RTU-frames; voor het TCP-frameformat zie [Modbus TCP-framestructuur (MBAP)](#modbus-tcp-framestructuur-mbap).

**Het firmwareversieveld lezen (firmware-versiecontrole, 10062 × 2):**

```
A0 03 27 4E 00 02 B7 D9
```

**Realtimegegevens lezen (10000 × 12):**

```
A0 03 27 10 00 0C 57 CF
```

**Één register schrijven — AC-ontlaadvermogenlimiet 700 W → 10101:**

```
A0 06 27 75 02 BC 8B 04
```

**Atomaire groepsschrijfactie — ontladen met 500 W forceren tot SoC 80% of
120 min (FC 0x10, registers 10103–10106):**

```
A0 10 27 77 00 04 08  00 02 01 F4 00 50 00 78  84 66
│  │  └───┘ └───┘ │   └───┘ └───┘ └───┘ └───┘  └───┘
│  │  │     │     │   │     │     │     │      └── CRC-16
│  │  │     │     │   │     │     │     └── register 10106: 0x0078 (120 min)
│  │  │     │     │   │     │     └── register 10105: 0x0050 (80%)
│  │  │     │     │   │     └── register 10104: 0x01F4 (500 W)
│  │  │     │     │   └── register 10103: 0x0002 (ontladen)
│  │  │     │     └── byte-aantal: 8 (4 registers × 2 bytes)
│  │  │     └── aantal: 4 registers
│  │  └── startadres: 0x2777 (10103)
│  └── FC 0x10
└── slave 160 (0xA0)
```

### Modbus TCP-framestructuur (MBAP)

Over TCP reist dezelfde PDU in een 7-byte MBAP-header; er is **geen CRC** — de integriteit wordt geborgd door de TCP-transportlaag.

| MBAP-veld | Grootte | Waarde |
| --- | --- | --- |
| Transactie-ID | 2 bytes | vrij te kiezen door de master; wordt ongewijzigd in de reactie teruggegeven |
| Protocol-ID | 2 bytes | `0x0000` (Modbus) |
| Lengte | 2 bytes | aantal volgende bytes (unit-ID + PDU) |
| Unit-ID | 1 byte | de unit-ID van het apparaat — standaard `0xA0` (register 9984) |

**De verificatiecode schrijven (directe TCP) — code `1A2B3C4D` → 9985–9986:**

```
00 01  00 00  00 0B  A0  10  27 01  00 02  04  1A 2B 3C 4D
└───┘  └───┘  └───┘  │   │   └───┘  └───┘  │   └─────────┘
│      │      │      │   │     │      │    │   verificatiecode 0x1A2B3C4D
│      │      │      │   │     │      │    └── byte-aantal: 4
│      │      │      │   │     │      └── aantal: 2 registers
│      │      │      │   │     └── startadres: 0x2701 (9985)
│      │      │      │   └── FC 0x10
│      │      │      └── unit-ID: 160 (0xA0)
│      │      └── lengte: 11 bytes (unit-ID + PDU)
│      └── protocol-ID: 0x0000 (Modbus)
└── transactie-ID: 0x0001 — wordt in de reactie teruggegeven
```

De reactie herhaalt de header met lengte 6: `00 01 00 00 00 06 A0 10 27 01 00 02`.

Controleer de CRC van elk frame zelf:

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
print(f"{crc16(frame):04X}")   # eerst lage byte toevoegen, dan hoge byte
PY
```

**Exception-antwoorden** — bij een fout antwoordt het apparaat met `[slave][functiecode + 0x80][exception-code][CRC]`; de codes en hun betekenis staan onder [6.1 Modbus-exceptioncodes](#61-modbus-exceptioncodes).

### Snelle test via de commandoregel

De frames hierboven zijn ruwe protocolbytes. Voor een eerste livetest kun je het apparaat ook aansturen met een standaard Modbus-client, bijvoorbeeld [mbpoll](https://github.com/epsilonrt/mbpoll) of [pymodbus](https://github.com/pymodbus/pymodbus). Beide voorbeelden voeren de [firmware-versiecontrole](#firmware-versiecontrole) uit — register 10062–10063 lezen met FC 0x03 — over RS-485 RTU; voor RTU is geen verificatiecode nodig.

```sh
# mbpoll — RTU op /dev/ttyUSB0, slave 160 (0xA0), 38400 8N1
# -P none is vereist: mbpoll gebruikt standaard even pariteit
mbpoll -m rtu -a 160 -b 38400 -P none -t 4 -0 -r 10062 -c 2 -1 /dev/ttyUSB0
# voeg ":string" toe aan -t 4 om de registers als ASCII-tekens weer te geven
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
    print(struct.pack(">HH", *rr.registers).decode())  # 4 ASCII-tekens
client.close()
```

Bij directe Modbus TCP moet je eerst de [verificatie](#verificatiecode-directe-modbus-tcp-all-in-one-apparaten) afronden. Met de voorbeeldcode `1A2B3C4D`:

```sh
# mbpoll — uint32-verificatiecode schrijven, hoge woord eerst (9985 = 0x1A2B, 9986 = 0x3C4D)
mbpoll -m tcp -a 160 -t 4 -0 -r 9985 -1 192.168.1.100 6699 15629
```

Het equivalent in pymodbus is `client.write_registers(address=9985, values=[0x1A2B, 0x3C4D], slave=160)` op een `ModbusTcpClient("192.168.1.100", port=502)`.

---

## 5 Belangrijke opmerkingen

1. **Modbus versus app-prioriteit.** Modbus en de app/cloud zijn twee
   onafhankelijke besturingspaden:

   Zolang Modbus actief is, verlaat het apparaat de bedrijfsmodus van de app
   en volgt het alleen Modbus; nadat de master stopt met schrijven en de
   timeout bij 10114 verstrijkt, keert het apparaat terug naar de
   CONOW-platformmodus van vóór het inschakelen van de Modbus-service.
2. **Groepsschrijfregels.** Instructies die een atomaire schrijfactie nodig
   hebben (realtime besturing) worden volgens de registeradressen in één
   opdracht geschreven.
3. **Schema's met consistente telling.** Schrijf alleen de eerste N tijdvakken
   die je daadwerkelijk gebruikt en zet het tellingregister (10124 / 10149)
   op N — het apparaat voert alleen de eerste N tijdvakken uit.
4. **Bedrijfsmodus: eerst lezen, dan schrijven.** Lees vóór het schrijven van
   10107 de huidige waarde en schrijf daarna de doelwaarde.
5. **Persistentie.** 10103–10106, 10121–10122 en 10190 zijn vluchtig;
   alle andere registers in het besturingsgebied blijven bewaard na
   spanningsuitval.
6. **CRC-fouten worden stilzwijgend genegeerd.** Probeer na een timeout tot 3
   keer opnieuw, met minstens 500 ms tussenpozen, en beschouw 3 opeenvolgende
   timeouts als een verbindingsfout. Poll realtime waarden niet vaker dan één
   keer per 1 s; wanneer één verzoek meerdere registers leest of schrijft,
   wordt een interval van minstens 2 s tussen polls aanbevolen; poll
   energie-/besturingsregisters niet vaker dan één keer per 5 s; poll het
   volledige registeroverzicht niet op hoge frequentie.
7. **Houd de vereisten aan.** Apparaat eenmalig via de CONOW ECO App in
   bedrijf gesteld en de *Modbus-service* ingeschakeld — een nooit in
   bedrijf gesteld apparaat blijft stil, ongeacht de firmware, en met de
   *Modbus-service* uit worden RTU-lees- en schrijfopdrachten beantwoord met
   exception 0x06
   ([6.1 Modbus-exceptioncodes](#61-modbus-exceptioncodes)).
8. **De watchdog telt alleen schrijfacties.** De watchdog bij 10114 wordt
   alleen gevoed door geldige schrijfframes (FC 0x06 / 0x10) — pollende
   leesopdrachten zetten hem niet terug. Was de laatst ontvangen instructie
   richting = inactief (10103 = 0), dan houdt het apparaat die toestand
   onbepaald vast en valt niet terug; alleen een nieuwe instructie of het
   uitschakelen van de Modbus-service verandert dat.
9. **Telkens één schrijver.** Zijn RTU en TCP beide ingeschakeld, dan volgen
   schrijfacties de RTU-prioriteitsregel onder
   [Gelijktijdige RTU en TCP](#gelijktijdige-rtu-en-tcp-schrijfprioriteit);
   een TCP-schrijfactie die wordt geweigerd met 0x86 / 0x90 is verwacht
   gedrag, geen verbindingsfout.

---

## 6 Probleemoplossing

Begin met de eerste controle voor jouw symptoom en volg daarna de verwezen
secties.

| Symptoom | Eerste controle | Opmerkingen / referentie |
| --- | --- | --- |
| Apparaat antwoordt helemaal niet | Modbus-schakelaar ingeschakeld in de app; slave-adres / unit-ID komt overeen met de huidige waarde in 9984 | met de schakelaar uit worden RTU-lees- en schrijfopdrachten beantwoord met exception 0x06 ([6.1 Modbus-exceptioncodes](#61-modbus-exceptioncodes)); standaard 0xA0 ([transportparameters](#transport--en-verbindingsparameters)) |
| RTU soms geen antwoord of CRC-fouten | CRC-16-berekening (polynoom 0xA001) en de seriële parameters 38400-8-N-1 | frames met een verkeerde CRC worden genegeerd zonder antwoord — controleer eerst de CRC, controleer daarna bedrading en adres |
| Geen antwoord bij het lezen van 128 registers of meer | verzoek langer dan 127 registers? | FC 0x03 bedient maximaal 127 registers per verzoek ([leeslimiet](#transport--en-verbindingsparameters)) |
| TCP geen antwoord, verificatiefout of schrijfacties zonder effect | eerst TCP-schakelaar, netwerk en unit-ID; een verificatiefout betekent: de verificatie via 9985–9986 opnieuw doen; ook na verificatie geweigerde schrijfacties — controleer de RTU-schrijfprioriteitsregel | niet-verbonden endpoints blijven stil; verbonden maar ongeverifieerde verzoeken krijgen een verificatiefout ([verificatiecode](#verificatiecode-directe-modbus-tcp-all-in-one-apparaten), [Gelijktijdige RTU en TCP](#gelijktijdige-rtu-en-tcp-schrijfprioriteit)) |
| Schrijfactie genegeerd of met exception beantwoord | geschreven waarde binnen het registerbereik? | schrijfacties buiten het bereik worden geweigerd met exception 0x03 ([6.1 Modbus-exceptioncodes](#61-modbus-exceptioncodes)) |
| Apparaatgedrag verandert na loskoppelen | watchdog 10114 ingeschakeld? | bij 10114 = 0 behoudt het apparaat zijn bedrijfsmodus; met een ingestelde timeout valt het terug op de CONOW-platformmodus van vóór het inschakelen van de Modbus-service ([opmerkingen](#5-belangrijke-opmerkingen)) |

### 6.1 Modbus-exceptioncodes

Lees- en schrijfopdrachten gebruiken alleen FC 0x03 / 0x06 / 0x10, en de standaard-exceptioncodes 0x01–0x03 verschijnen alleen in antwoorden op deze drie functiecodes; bij een fout antwoordt het apparaat met `[slave][functiecode + 0x80][exception-code][CRC]`:

| Code | Betekenis | Typische oorzaak |
| --- | --- | --- |
| 0x01 | Ongeldige functie | functiecode wordt niet ondersteund (lezen en schrijven ondersteunen alleen FC 0x03 / 0x06 / 0x10) |
| 0x02 | Ongeldig data-adres | register bestaat niet, of wordt door dit model niet ondersteund; tijdens een TCP-verificatievergrendeling krijgen lees- en schrijfopdrachten 0x02 terug (lezen van 9984 uitgezonderd) |
| 0x03 | Ongeldige gegevenswaarde | geschreven waarde buiten het bereik |

0x04 / 0x05 zijn apparaatgedefinieerde statuscodes van de verificatielaag bij
directe Modbus TCP, geen standaard exception-antwoorden voor lezen/schrijven
met FC 0x03 / 0x06 / 0x10; zie [Verificatiecode](#verificatiecode-directe-modbus-tcp-all-in-one-apparaten) voor de scenario's van de verificatielaag:

| Code | Betekenis | Typische oorzaak |
| --- | --- | --- |
| 0x04 | MAC-adres gewijzigd (apparaatgedefinieerd) | de TCP-verificatiecode is vervallen door een MAC-adreswijziging van de adapter — schrijf de code opnieuw |
| 0x05 | Handmatig vernieuwd (apparaatgedefinieerd) | wordt teruggegeven bij TCP-toegang nadat de verificatiecode handmatig is vernieuwd en daarmee vervallen — schrijf de nieuwe code |

0x06 (apparaatgedefinieerd) wordt alleen bij Modbus RTU teruggegeven — nadat *Modbus-service inschakelen* in de app is uitgezet, worden lees- en schrijfopdrachten op registers met 0x06 beantwoord:

| Code | Betekenis | Typische oorzaak |
| --- | --- | --- |
| 0x06 | Modbus-service niet ingeschakeld (apparaatgedefinieerd) | *Modbus-service inschakelen* in de app uitgezet — schakel de optie opnieuw in en herhaal de opdracht |

### 6.2 Apparaatfoutcode (alarmbitmap, 10001–10002)

De apparaatfoutcode (10001–10002, uint32) is een 32-bit bitmap: een bit op `1` betekent dat de bijbehorende melding actief is; meerdere bits kunnen tegelijk gezet zijn. Lees beide registers in één verzoek samen.

| Bit | CBE2000 Pro | Atlas 6000 | Lyra 2500 |
| --- | --- | --- | --- |
| bit0 | Accupakket 1-alarm | Celoverspanning | Celoverspanning |
| bit1 | Accupakket 2-alarm | Celunderspanning | Celunderspanning |
| bit2 | Accupakket 3-alarm | Batterijoverspanning | Batterijoverspanning |
| bit3 | Accupakket 4-alarm | Batterijunderspanning | Batterijunderspanning |
| bit4 | Accupakket 5-alarm | Laden bij lage temperatuur | Laden bij lage temperatuur |
| bit5 | Accupakket 6-alarm | Laden bij hoge temperatuur | Laden bij hoge temperatuur |
| bit6 | — | Ontladen bij lage temperatuur | Ontladen bij lage temperatuur |
| bit7 | — | Ontladen bij hoge temperatuur | Ontladen bij hoge temperatuur |
| bit8 | Hoofd-uitbreidingscommunicatiefout | Laadstroom 1 | Laadstroom 1 |
| bit9 | LED-paneelcommunicatiefout | Laadstroom 2 | Laadstroom 2 |
| bit10 | Omvormercommunicatiefout | Ontlaadstroom 1 | Ontlaadstroom 1 |
| bit11 | Omvormerfout | Ontlaadstroom 2 | Ontlaadstroom 2 |
| bit12 | Wi-Fi-modulecommunicatiefout | MOS-overtemperatuur | MOS-overtemperatuur |
| bit13 | PV1-alarm | Temperatuurverschilalarm | Temperatuurverschilalarm |
| bit14 | PV2-alarm | Spanningsverschilalarm | Spanningsverschilalarm |
| bit15 | PV3-alarm | Kortsluiting | Kortsluiting |
| bit16 | PV4-alarm | NTC-defect | NTC-defect |
| bit17 | Netfout (onder-/bovenfrequentie) | Celdefect | Celdefect |
| bit18 | Omvormeruitgangalarm | AFE-defect | AFE-defect |
| bit19 | — | Laad-MOS-alarm | Laad-MOS-alarm |
| bit20 | — | Ontlaad-MOS-alarm | Ontlaad-MOS-alarm |
| bit21 | — | Verwarmingsfolie onderbroken | — |
| bit22 | Kortsluiting 2 | — | — |
| bit23 | Overbelasting noodstroomingang | Shunt-alarm | Shunt-alarm |
| bit24 | Herhaalde adresfout (uitbreiding) | Hoofd-uitbreidingscommunicatiefout | Hoofd-uitbreidingscommunicatiefout |
| bit25 | Herhaalde adresfout (hoofd) | Omvormercommunicatie | Omvormercommunicatie |
| bit26 | Kortsluiting 1 | Wi-Fi-communicatiefout | Wi-Fi-communicatiefout |
| bit27 | — | — | — |
| bit28 | — | Overbelasting bij lage temperatuur | Overbelasting bij lage temperatuur |
| bit29 | — | Overbelasting noodstroomingang | Overbelasting noodstroomingang |
| bit30 | — | Overtemperatuur accuklemmen | Meterkringfout |
| bit31 | — | Meterkringfout | — |

Oorzaak en oplossing per melding, voor zelfdiagnose:

**Accumularmen**

| Melding | Oorzaak | Oplossing |
| --- | --- | --- |
| Celoverspanning | celspanning kort boven de bovengrens | normale beveiligingsmelding — herstel afwachten; bij frequent optreden support contacteren |
| Celunderspanning | celspanning onder de veiligheidsgrens | accu snel opladen; support contacteren als opladen niet lukt of het terugkeert |
| Batterijoverspanning | totaalspanning van het accupakket boven de bovengrens | automatisch herstel afwachten; support contacteren bij herhaling |
| Batterijunderspanning | totaalspanning van het accupakket onder de ondergrens | accu direct opladen; support contacteren als opladen niet lukt |
| Laden bij lage temperatuur | temperatuur te laag om te laden | omgevingstemperatuur verhogen of warmere omstandigheden afwachten |
| Laden bij hoge temperatuur | laadtemperatuur te hoog | apparaat op een koele, geventileerde plek plaatsen en bedekkingen verwijderen; na afkoeling doorgaan |
| Ontladen bij lage temperatuur | ontlaadtemperatuur te laag | last verminderen en omgeving voorverwarmen; na herstel normaal gebruiken |
| Ontladen bij hoge temperatuur | ontlaadtemperatuur te hoog | bedekkingen verwijderen en uit de zon houden; na afkoeling doorgaan |
| Laadstroom 1 | laadstroom boven de drempel van niveau 1 | herstart proberen en herstel afwachten; support contacteren zonder herstel |
| Laadstroom 2 | laadstroom ver boven de limiet | herstart proberen en herstel afwachten; support contacteren zonder herstel |
| Ontlaadstroom 1 | ontlaadstroom boven de drempel, beveiliging getriggerd | herstart proberen en herstel afwachten; support contacteren zonder herstel |
| Ontlaadstroom 2 | ontlaadstroom ver boven de limiet, gedwongen beveiliging | herstart proberen en herstel afwachten; support contacteren zonder herstel |
| MOS-overtemperatuur | temperatuur van de vermogens-MOS te hoog | laden en ontladen pauzeren; automatisch herstel na afkoeling; support contacteren bij frequent optreden |
| Temperatuurverschilalarm | temperatuurverschil tussen de meetpunten te groot | herstel afwachten en observeren; support contacteren bij herhaling |
| Spanningsverschilalarm | spanningsverschil tussen de cellen te groot | systeembalancing afwachten; support contacteren bij herhaling |
| Kortsluiting | kortsluiting gedetecteerd aan de gelijkspanningszijde, beveiliging actief | direct uitschakelen, bedrading en lasten controleren en daarna herstarten; support contacteren zonder herstel |
| NTC-defect | temperatuursensor open of kortgesloten | herstart proberen en herstel afwachten; support contacteren zonder herstel |
| Celdefect | een cel is defect of losgekoppeld | apparaat buiten gebruik stellen en snel support contacteren |
| AFE-defect | defect in de front-end meetcircuits | apparaat uitschakelen en support contacteren voor diagnostiek |
| Laad-MOS-alarm | abnormaal schakelgedrag van de laad-MOS | laden direct stoppen en support contacteren |
| Ontlaad-MOS-alarm | abnormaal schakelgedrag van de ontlaad-MOS | lasten afkoppelen en support contacteren |
| Verwarmingsfolie onderbroken | verwarmingsfunctie defect | laden pauzeert bij lage temperatuur; verbindingen controleren; support contacteren bij aanhoudende afwijking |
| Shunt-alarm | stroommeting abnormaal | herstart proberen en herstel afwachten; support contacteren zonder herstel |

**Systeem- en overige meldingen**

| Melding | Oorzaak | Oplossing |
| --- | --- | --- |
| Hoofd-uitbreidingscommunicatiefout | communicatie tussen hoofd- en uitbreidingscontroller abnormaal | herstart proberen en herstel afwachten; support contacteren zonder herstel |
| LED-paneelcommunicatiefout | communicatie met het LED-/displaypaneel onderbroken of abnormaal | herstart proberen en herstel afwachten; support contacteren zonder herstel |
| Omvormercommunicatiefout | communicatie tussen hoofdcontroller en omvormer onderbroken of abnormaal | apparaat buiten gebruik stellen en snel support contacteren |
| Omvormerfout | omvormer functioneert abnormaal of kan niet starten of uitsturen | apparaat buiten gebruik stellen en snel support contacteren |
| Wi-Fi-modulecommunicatiefout | geen Wi-Fi-verbinding mogelijk | Wi-Fi-signaal, routerinstellingen en wachtwoord controleren en opnieuw verbinden |
| Overbelasting bij lage temperatuur | bij lage temperatuur overschrijdt het noodstroomuitgangsvermogen het maximaal toegestane ontlaadvermogen | noodstroomlasten verminderen of afkoppelen |
| Overbelasting noodstroomingang | ingangsvermogen op de noodstroomingang overschrijdt het maximaal toegestane laadvermogen van de accu | ingangsvermogen verminderen of het invoerapparaat afkoppelen |
| Kortsluiting 1 / Kortsluiting 2 | voorladen mislukt — de 1e / 2e kortsluiting geregistreerd door het BMS | automatisch herstel afwachten; een derde kortsluiting op rij beïnvloedt het gebruik — herstarten en observeren, support contacteren zonder herstel |
| Netfout | netfrequentie buiten het toegestane bereik (onder-/bovenfrequentie) | herstel van het net afwachten; bij aanhoudende afwijking netbeheerder of support contacteren |
| Meterkringfout | CT abnormaal, metergegevens niet beschikbaar | voor de veiligheid van apparaat en net levert het apparaat alleen de basislast; meterbedrading controleren |
| Overtemperatuur accuklemmen | temperatuur van de accuklemmen te hoog | klembedrading en lasten controleren; support contacteren bij aanhoudende afwijking |
| Omvormeruitgangalarm | omvormeruitgang abnormaal | alarmpagina in de app openen, de specifieke melding opzoeken en daar afhandelen |
| Accupakket N-alarm | het bijbehorende accupakket heeft een melding; Modbus geeft het type niet | alarmpagina in de app voor dat pakket openen en de specifieke melding afhandelen |
| PV1–PV4-alarm | de bijbehorende PV-ingang heeft een melding; Modbus geeft het type niet | alarmpagina in de app openen; die PV-string controleren |
| Herhaalde adresfout hoofd/uitbreiding | adrestoewijzing van de pakketen herhaaldelijk mislukt | apparaat herstarten en observeren; support contacteren bij aanhoudende afwijking |
