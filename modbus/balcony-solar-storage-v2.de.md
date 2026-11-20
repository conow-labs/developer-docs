# Modbus-Integrationsleitfaden — Balkonkraftwerk-Speicher (V2-Registerübersicht)

> [!IMPORTANT]
> **Gilt für:** Geräte, deren Firmware auf den Firmware-Version-Registern
> 10062–10063 antwortet (siehe [Firmware-Versionsprüfung](#firmware-versionsprüfung)).
> Dies sind die **v2-Registeradressen**. Die Mindest-Firmware-Version unterscheidet
> sich je Modell: Lyra Serie 1.01.16, CBE2000 Pro 1.02.17, Atlas 6000 AC 1.01.08
> oder neuer. Firmware unter diesen Versionen: verwende
> [balcony-solar-storage.de.md](balcony-solar-storage.de.md)
> (v1-Registerübersicht).

Sprachen / Language / 语言 / Taal: [English](balcony-solar-storage-v2.md) · [简体中文](balcony-solar-storage-v2.zh-CN.md) · **Deutsch** · [Nederlands](balcony-solar-storage-v2.nl.md)

---

## Inhaltsverzeichnis

- [1 Überblick](#1-überblick)
  - [Firmware-Versionsprüfung](#firmware-versionsprüfung)
  - [Migration von v1](#migration-von-v1)
  - [Übertragung und Verbindungsparameter](#übertragung-und-verbindungsparameter)
  - [Bestätigungscode (direktes Modbus TCP, All-in-One-Geräte)](#bestätigungscode-direktes-modbus-tcp-all-in-one-geräte)
  - [Gleichzeitiges RTU und TCP (Schreib-Priorität)](#gleichzeitiges-rtu-und-tcp-schreib-priorität)
  - [Hardware-Verdrahtung](#hardware-verdrahtung)
  - [Voraussetzungen](#voraussetzungen)
- [2 Datentypen](#2-datentypen)
- [3 Registerübersicht](#3-registerübersicht)
  - [3.1 Echtzeit-Monitoring (10000–10011)](#31-echtzeit-monitoring-1000010011)
  - [3.2 Detailliertes Monitoring (10012–10043)](#32-detailliertes-monitoring-1001210043)
  - [3.3 Betriebsparameter und Geräteinfos (10044–10063)](#33-betriebsparameter-und-geräteinfos-1004410063)
  - [3.4 Lebenslange Energiezähler (10064–10081)](#34-lebenslange-energiezähler-1006410081)
  - [3.5 Steuerung — Leistungs- und SoC-Einstellungen (10100–10102)](#35-steuerung--leistungs--und-soc-einstellungen-1010010102)
  - [3.6 Steuerung — erzwungenes Laden/Entladen in Echtzeit (10103–10106)](#36-steuerung--erzwungenes-ladenentladen-in-echtzeit-1010310106)
  - [3.7 Steuerung — Betriebsstrategie (10107–10114)](#37-steuerung--betriebsstrategie-1010710114)
  - [3.8 Steuerung — Generator und digitale Ausgänge (10115–10122)](#38-steuerung--generator-und-digitale-ausgänge-1011510122)
  - [3.9 Steuerung — Grundlast (10123–10148)](#39-steuerung--grundlast-1012310148)
  - [3.10 Steuerung — manueller Lade-/Entlade-Zeitplan TOU (10149–10189)](#310-steuerung--manueller-lade-entlade-zeitplan-tou-1014910189)
  - [3.11 Steuerung — Zeitkalibrierung (10190)](#311-steuerung--zeitkalibrierung-10190)
  - [3.12 Protokoll-Register (9984–9986)](#312-protokoll-register-99849986)
- [4 Frame-Beispiele](#4-frame-beispiele)
  - [Modbus-TCP-Frameformat (MBAP)](#modbus-tcp-frameformat-mbap)
  - [Schnelltest über die Kommandozeile](#schnelltest-über-die-kommandozeile)
- [5 Wichtige Hinweise](#5-wichtige-hinweise)
- [6 Fehlerbehebung](#6-fehlerbehebung)
  - [6.1 Modbus-Exception-Codes](#61-modbus-exception-codes)
  - [6.2 Geräte-Fehlercode (Alarm-Bitmap, 10001–10002)](#62-geräte-fehlercode-alarm-bitmap-1000110002)

---

## 1 Überblick

Dieser Leitfaden dokumentiert die **Modbus-RTU/TCP-Schnittstelle der CONOW
Balkonkraftwerk-Speicher und All-in-One-Energiespeicher mit v2-Firmware** — CBE
Serie (CBE2000 Pro), Lyra Serie (Lyra 2500 AC, Lyra 2500 Pro) und
Atlas Serie (Atlas 6000 AC).

Gegenüber der [v1-Registerübersicht](balcony-solar-storage.de.md) bringt die v2-Firmware:

- Ein Monitoring-Bereich (10000–10081): CT-/Zählerdaten, Wirkleistung je
  Netzphase, Spannung/Strom/Energie je PV-String, die vom Gerät gemeldeten
  Batteriegrenzen, SOH, Seriennummer und Firmware-Version.
- Ein Steuerungsbereich (10100–10190): Betriebsstrategien, Betriebsmodus,
  Rückspeise-Begrenzung, Modbus-Timeout, Grundlast-Zeitplan, ein manueller
  Lade-/Entlade-Zeitplan (TOU) mit bis zu 8 Zeitfenstern und ein
  Zeitkalibrierungsregister.
- **Direktes Modbus TCP** auf All-in-One-Geräten (Port 502), geschützt durch
  einen **dynamischen Bestätigungscode** — RTU und TCP sind gleichzeitig
  nutzbar, unter einer RTU-prioritären Schreib-Arbitrierungsregel.
- **Atomare Gruppen-Schreibzugriffe** — mehrere Steuerungswerte müssen
  gemeinsam in einem FC-0x10-Frame geschrieben werden.

### Firmware-Versionsprüfung

Die beiden Registerübersichten schließen sich gegenseitig aus: Ein Gerät antwortet entweder auf die v1-Adressen oder auf die v2-Adressen, nie auf beide. Die Mindest-Firmware-Version, die die v2-Registerübersicht aktiviert, unterscheidet sich je Modell:

| Modell | Mindest-Firmware |
| --- | --- |
| Lyra Serie | 1.01.16 |
| CBE2000 Pro | 1.02.17 |
| Atlas 6000 AC | 1.01.08 |

Firmware unter diesen Versionen verwendet standardmäßig die v1-Registeradressen. Wenn du nicht sicher bist, welche Übersicht ein Gerät verwendet, prüfe einmalig nach dem Verbinden:

1. Lese das Firmware-Version-Feld **10062 (0x274E), Anzahl 2** (10062–10063) mit FC 0x03.
2. Wähle den Leitfaden anhand der Antwort:

   - **Das Gerät antwortet** — die Firmware implementiert diesen Registerbereich, liegt also bei oder über der Modell-Mindestversion, und das Gerät nutzt die v2-Registerübersicht. Bleib bei diesem Leitfaden.
   - **Keine Antwort, ein Timeout oder eine Modbus-Exception** — die Firmware implementiert diesen Registerbereich nicht, liegt also unter der Modell-Mindestversion. Wechsle zu [balcony-solar-storage.de.md](balcony-solar-storage.de.md).

Hinweise:

- Das Firmware-Version-Feld (10062–10063, U16[2] ASCII) **beantwortet keine
  Einzelregister-Lesezugriffe** — lies beide Register in einem Frame.
- Für das Seriennummer-Feld (10054–10061, U16[8] ASCII) gilt dieselbe
  Einschränkung: alle 8 Register in einer Anforderung lesen.

### Migration von v1

Die Steueradressen wurden zwischen den Übersichten verschoben — mappe eine bestehende v1-Integration vor dem Schreiben neu:

| Funktion | v1 | v2 |
| --- | --- | --- |
| AC-Ladeleistungslimit | 10100 | 10100 — unverändert |
| Entladeleistungslimit | 10101 | 10101 — unverändert |
| Backup-SoC | 10102 | 10102 — unverändert |
| Lade-/Entladerichtung | 10105 | 10103 |
| Ziel-Lade-/Entladeleistung | 10106 | 10104 |
| Lade-/Entlade-Abschalt-SoC | 10107 | 10105 |

Die v1-Schreibreihenfolge (10106 → 10105 → 10107, FC 0x06) gilt auf v2 **nicht**: 10103–10106 werden als eine atomare FC-0x10-Gruppe geschrieben (nur Richtung = 3 erlaubt das Einzelregister).

Der v1-Schalter für den Notstrom-Ausgang (10103) und die PV-Abregelung (10104) haben auf v2 keine Entsprechung an diesen Adressen — 10103/10104 sind dort Richtungs- und Leistungsregister; prüfe vor der Migration dieser Funktionen die Steuerungstabellen.

Auch die Monitoring-Register wurden neu gruppiert — verifiziere vor dem Pollen jede Adresse gegen die v2-Tabellen.

Auch die Vorzeichenkonvention der Netz-Wirkleistung hat sich geändert: Auf v1 meldet der CBE2000 Pro positiv = Einspeisung und negativ = Bezug, Lyra / Atlas positiv = Bezug und negativ = Einspeisung; auf v2 melden alle Modelle positiv = Bezug aus dem Netz und negativ = Einspeisung ins Netz (10006, 10013).

### Übertragung und Verbindungsparameter

| Parameter | Wert |
| --- | --- |
| Übertragung | RS-485 Modbus RTU, oder Modbus TCP (All-in-One-Geräte, TCP-Port **502**) |
| Serielle Parameter (RTU) | **38400** Baud, 8 Datenbits, keine Parität, 1 Stoppbit (8N1) |
| Standard-Slave-/Unit-ID | **160 (0xA0)** |
| Unit-ID-Bereich | 128–176 (0x80–0xB0); die ID ist im Register **9984 (0x2700)** lesbar und schreibbar; eine Änderung erfordert keine erneute TCP-Verifizierung |
| Funktionscodes | 0x03 lesen · 0x06 einzeln schreiben · 0x10 mehrfach schreiben |
| Lesebegrenzung | eine FC-0x03-Anfrage liefert höchstens **127** Register; eine längere Anfrage bleibt unbeantwortet. Die Modbus-Spezifikation begrenzt Lesezugriffe auf 125 Register — plane maximal 125 Register ein |

### Bestätigungscode (direktes Modbus TCP, All-in-One-Geräte)

**Modbus RTU benötigt keinen Bestätigungscode; direktes Modbus TCP erfordert,
dass der TCP-Schalter in der App aktiviert und die Verifizierung abgeschlossen
ist.** Verbinde dich über TCP und schreibe danach den 8-stelligen hexadezimalen
Bestätigungscode (abzurufen über die Gerätedetailseite in der CONOW-App) in
das Gerät:

- Schreibe ihn als **uint32** in die Holding-Register
  **9985–9986 (0x2701–0x2702)**, hohes Wort zuerst.
- Der Code ist **dynamisch und erneuert sich alle 120
  Sekunden**, bis die Verifizierung erfolgreich war; danach wird er nicht mehr
  erneuert. Lehnt das Gerät den Code ab, lies den neuen Code aus der App und
  schreibe ihn erneut.
- **Verifizierungssperre:** nach 5 aufeinanderfolgenden fehlgeschlagenen
  Verifizierungen innerhalb von 5 Minuten wird die TCP-Verifizierung für
  5 Minuten gesperrt — während der Sperre kann die Verifizierung nicht
  abgeschlossen werden und TCP-Lese- und Schreibzugriffe werden mit
  Exception 0x02 beantwortet (ausgenommen ist das Lesen des Unit-ID-Registers
  9984); warte das Ende der Sperre ab, lies dann einen neuen Code aus der App
  und schreibe ihn erneut.
- Die Verifizierung ist zu wiederholen, nachdem der Modbus-Schalter in der App
  erneut aktiviert wurde, nachdem sich die MAC-Adresse des Adapters geändert
  hat oder nach einer manuellen Aktualisierung.
- Das Gerät fordert die Verifizierung an, indem es Anforderungen mit einer
  **Modbus-Exception** beantwortet — eine verbundene, aber unverifizierte
  Anfrage erhält einen Verifizierungsfehler, während ein nicht verbundener
  Endpunkt stumm bleibt; verwechsele die beiden Fälle nicht. Sobald eine
  Anfrage normal beantwortet wurde, wird der Code **nicht** bei jedem Poll
  erneut gesendet — schreibe ihn nur bei Aufforderung sowie nach einem
  Codewechsel.

RTU über RS-485 (und Modbus TCP über einen RS-485-auf-Ethernet-Gateway)
benötigt keinen Bestätigungscode.

### Gleichzeitiges RTU und TCP (Schreib-Priorität)

Die App bietet **unabhängige RTU- und TCP-Schalter**, und beide Kanäle können
gleichzeitig aktiviert sein. RTU-Lesezugriffe (FC 0x03) funktionieren direkt;
TCP-Lese- und Schreibzugriffe erfordern zuerst die Verifizierung über
9985–9986. Schreibframes (FC 0x06 / 0x10) folgen einer
**Einzel-Schreiber-Regel mit RTU-Priorität**:

- Hält die RTU-Seite die Schreibberechtigung — jeder gültige Schreibframe
  innerhalb des Watchdog-Fensters von 10114 —, werden verifizierte
  TCP-Schreibzugriffe ohne Bestätigung und ohne Ausführung abgelehnt.
  Verifizierte TCP-Lesezugriffe funktionieren weiterhin.
- Bricht die RTU-Verbindung ab oder bleibt die RTU-Seite länger als das
  Timeout 10114 stumm, wird die Schreibberechtigung freigegeben, und
  verifizierte TCP-Schreibzugriffe greifen. Jeder neue RTU-Schreibframe übernimmt die Schreibberechtigung
  sofort zurück; TCP kann RTU nicht verdrängen.
- Die Verifizierung (9985–9986) ist Voraussetzung für TCP-Lese- und
  -schreibzugriffe, aber kein Weg, Schreibberechtigung zu erlangen — beides
  ist unabhängig voneinander.

Betreibe jederzeit nur einen schreibenden Master. Ein TCP-Schreibzugriff, der
mit Exception 0x86 (FC 0x06) oder 0x90 (FC 0x10) beantwortet wird, ist
erwartetes Verhalten der Schreib-Priorität, kein Verbindungsfehler. Es wird
empfohlen, je nach tatsächlichem Bedarf nur eine Steuerungsmethode zu
aktivieren.

### Hardware-Verdrahtung

Die Verdrahtung ist identisch mit der v1-Anleitung — Pinbelegung und
Anschlussschemata stehen dort im Abschnitt
[Hardware-Schnittstelle](balcony-solar-storage.de.md#12-hardware-schnittstelle).

### Voraussetzungen

Das Gerät muss über die **CONOW ECO App** in Betrieb genommen worden sein und
mindestens einmal online gegangen sein — ein fabrikneues, nie aktiviertes
Gerät beantwortet keine Anfrage an der RS-485-Schnittstelle.

1. Aktiviere in der App unter *Geräte → dein Gerät → Einstellungen* die
   Option *Modbus-Dienst aktivieren*; für direktes TCP aktiviere zusätzlich
   den TCP-Schalter. Fehlt der Schalter in älteren App-Versionen, wähle
   stattdessen unter *Einstellungen → Betriebsmodus* den *DIY-Modus*.
2. Schreibzugriffe jederzeit auf einen einzelnen Master beschränken — siehe
   [Gleichzeitiges RTU und TCP](#gleichzeitiges-rtu-und-tcp-schreib-priorität).

---

## 2 Datentypen

| Typ | Codierung |
| --- | --- |
| `uint16` | 1 Register, ohne Vorzeichen |
| `int16` | 1 Register, Zweierkomplement; Vorzeichenbedeutung siehe Registerbeschreibung |
| `uint32` | 2 Register, **Big-Endian, hohes Wort zuerst** — `value = (reg[n] << 16) \| reg[n+1]` |
| `string` | U16-Feld, 2 ASCII-Zeichen pro Register (hohes Byte zuerst), aufgefüllt mit 0x00 |
| `hhmm`-Zeit | 1 Register: hohes Byte = Stunde, niedriges Byte = Minute (zum Beispiel `06:30` → `0x06 0x1E` → `0x061E` = 1566) |
| Skalierung | Physikalischer Wert = Rohwert × Skalierung (Skalierung 1, sofern nicht angegeben) |
| Enums / Boolesche Werte | Wertetabellen der jeweiligen Register unten |

---

## 3 Registerübersicht

Drei Bereiche, nicht zusammenhängend:

| Bereich | Register | Zugriff |
| --- | --- | --- |
| Monitoring | **10000–10081** (0x2710–0x2761) | nur lesen, FC 0x03 |
| Steuerung | **10100–10190** (0x2774–0x27CE) | lesen FC 0x03 · schreiben FC 0x06 / 0x10 — ausgenommen 10103–10106: nur eine atomare FC-0x10-Gruppe (Richtung = 3 akzeptiert auch FC 0x06) |
| Protokoll | 9984 (Unit-ID, lesbar/schreibbar) · 9985–9986 (Bestätigungscode, WO) | siehe 3.12; Ablauf in den Abschnitten oben |

Anders als die v1-Firmware (die Einzel-Lesezugriffe über 38 Register und mehr
stillschweigend verwirft) bedient die v2-Firmware Lesezugriffe über ganze
Bereiche — die Home-Assistant-Referenzintegration fragt den gesamten
Monitoring-Bereich (82 Register) und den gesamten Steuerungsbereich (91
Register) mit je einer FC-0x03-Anfrage ab. Falls dein Gateway oder Werkzeug
Probleme mit langen Frames hat, teile Lesezugriffe an den unten markierten
Gruppengrenzen.

### 3.1 Echtzeit-Monitoring (10000–10011)

| Register | Hex | Name | Typ | Einheit | Skalierung | Bemerkungen |
| --- | --- | --- | --- | --- | --- | --- |
| 10000 | 0x2710 | Systemstatus | uint16 | — | — | Bitfeld — siehe die Bittabelle unten |
| 10001–10002 | 0x2711 | Geräte-Fehlercode | uint32 | — | — | [6.2 Alarm-Bitmap](#62-geräte-fehlercode-alarm-bitmap-1000110002); 10001–10002 zusammen lesen |
| 10003 | 0x2713 | System-SoC | uint16 | % | 1 | 0–100 |
| 10004 | 0x2714 | Zählerverbindungsstatus | enum | — | — | 0 = gekoppelt und verbunden · 1 = nicht gekoppelt und nicht verbunden · 2 = gekoppelt, nicht verbunden |
| 10005 | 0x2715 | Zähler-Gesamtleistung | int16 | W | 1 | Positiv = Netzbezug; negativ = Einspeisung ins Netz |
| 10006 | 0x2716 | Netz-Wirkleistung | int16 | W | 1 | Positiv = Bezug aus dem Netz / Batterie lädt; negativ = Einspeisung ins Netz / Batterie entlädt |
| 10007 | 0x2717 | PV-Gesamtleistung | uint16 | W | 1 | — |
| 10008 | 0x2718 | Batterie-Betriebsstatus | enum | — | — | 0 = inaktiv · 1 = laden · 2 = entladen; meldet den tatsächlichen Zustand, kein Echo des Befehls |
| 10009 | 0x2719 | Batterieleistung | int16 | W | 1 | Positiv = Laden; negativ = Entladen |
| 10010 | 0x271A | Bypass-Schalterzustand | enum | — | — | 0 = aus · 1 = ein |
| 10011 | 0x271B | Bypass-Leistung | int16 | W | 1 | Positiv = Entladen in den Bypass; negativ = Laden aus dem Bypass |

**Systemstatus (10000) Bitfeld** — dieser Status meldet den tatsächlichen
Zustand des Batterieanschlusses, kein Echo des Befehls:

| Bit | Bedeutung | Gesetztes Bit (= 1) bedeutet |
| --- | --- | --- |
| 0 | Bereitschaft | Batterieanschluss ist im Bereitschaftszustand |
| 1 | Reserviert | reserviert |
| 2 | Störung | Störung aktiv — Fehlercode unter 10001–10002 lesen ([6.2 Alarm-Bitmap](#62-geräte-fehlercode-alarm-bitmap-1000110002)) |
| 3 | Laden | Batterie lädt |
| 4 | Entladen | Batterie entlädt |
| 5–15 | Reserviert | ignorieren |

Beispiel: eine Auslesung von 0x0008 (nur Bit 3 gesetzt) bedeutet, dass der
Batterieanschluss lädt; 0x0001 (nur Bit 0 gesetzt) bedeutet Bereitschaft.

### 3.2 Detailliertes Monitoring (10012–10043)

| Register | Hex | Name | Typ | Einheit | Skalierung | Bemerkungen |
| --- | --- | --- | --- | --- | --- | --- |
| 10012 | 0x271C | Netzspannung | uint16 | V | 0.1 | Phasenspannung; Phase A bei dreiphasigen Modellen |
| 10013 | 0x271D | Netzstrom | int16 | A | 0.1 | Positiv = Bezug; negativ = Einspeisung |
| 10014 | 0x271E | Netzfrequenz | uint16 | Hz | 0.01 | — |
| 10015 | 0x271F | Leistung Phase A | int16 | W | 1 | dreiphasige Modelle |
| 10016 | 0x2720 | Leistung Phase B | int16 | W | 1 | dreiphasige Modelle |
| 10017 | 0x2721 | Leistung Phase C | int16 | W | 1 | dreiphasige Modelle |
| 10018 | 0x2722 | PV-String-Anzahl | uint16 | — | — | liest N = N unterstützte Strings; nicht unterstützte Strings lesen 0 |
| 10019 | 0x2723 | PV1-Spannung | uint16 | V | 0.1 | — |
| 10020 | 0x2724 | PV1-Strom | uint16 | A | 0.1 | — |
| 10021–10022 | 0x2725 | PV1-Energie | uint32 | kWh | 0.01 | hohes Wort zuerst |
| 10023 | 0x2727 | PV2-Spannung | uint16 | V | 0.1 | — |
| 10024 | 0x2728 | PV2-Strom | uint16 | A | 0.1 | — |
| 10025–10026 | 0x2729 | PV2-Energie | uint32 | kWh | 0.01 | hohes Wort zuerst |
| 10027 | 0x272B | PV3-Spannung | uint16 | V | 0.1 | — |
| 10028 | 0x272C | PV3-Strom | uint16 | A | 0.1 | — |
| 10029–10030 | 0x272D | PV3-Energie | uint32 | kWh | 0.01 | hohes Wort zuerst |
| 10031 | 0x272F | PV4-Spannung | uint16 | V | 0.1 | — |
| 10032 | 0x2730 | PV4-Strom | uint16 | A | 0.1 | — |
| 10033–10034 | 0x2731 | PV4-Energie | uint32 | kWh | 0.01 | hohes Wort zuerst |
| 10035 | 0x2733 | Batteriespannung | uint16 | V | 0.01 | DC-Zwischenkreisspannung |
| 10036 | 0x2734 | Batteriestrom | int16 | A | 0.1 | Positiv = Laden; negativ = Entladen |
| 10037 | 0x2735 | Max. Zelltemperatur | **int16** | °C | 0.1 | vorzeichenbehaftet — keine Offset-Codierung |
| 10038 | 0x2736 | Min. Zelltemperatur | **int16** | °C | 0.1 | vorzeichenbehaftet — keine Offset-Codierung |
| 10039 | 0x2737 | Batterie max. Ladeleistung | uint16 | W | 1 | aktuell erlaubte Ladeleistung; kann bei Abregelung durch Temperatur / SoC unter dem 10100-Wert liegen |
| 10040 | 0x2738 | Batterie max. Entladeleistung | uint16 | W | 1 | aktuell erlaubte Entladeleistung; kann bei Abregelung durch Temperatur / SoC unter dem 10101-Wert liegen |
| 10041 | 0x2739 | Bypass-Spannung | uint16 | V | 0.1 | — |
| 10042 | 0x273A | Bypass-Strom | uint16 | A | 0.1 | — |
| 10043 | 0x273B | Bypass-Frequenz | uint16 | Hz | 0.01 | — |

### 3.3 Betriebsparameter und Geräteinfos (10044–10063)

Die Seriennummer- und Firmware-Version-Felder beantworten keine
Einzelregister-Lesezugriffe. Lies jedes Feld vollständig in einer Anforderung —
Seriennummer 10054 (0x2746) × 8, Firmware-Version 10062 (0x274E) × 2.

| Register | Hex | Name | Typ | Einheit | Skalierung | Bemerkungen |
| --- | --- | --- | --- | --- | --- | --- |
| 10044 | 0x273C | Nennkapazität | uint16 | kWh | 0.01 | Nennkapazität des Batteriepacks |
| 10045 | 0x273D | Restkapazität | uint16 | kWh | 0.01 | aktuell gespeicherte Batterieenergie |
| 10046 | 0x273E | System-Backup-SoC | uint16 | % | 1 | spiegelt den geschriebenen Sicherheits-SoC (10102) |
| 10047 | 0x273F | SOH | uint16 | % | 1 | 0–100 |
| 10048 | 0x2740 | Hardware max. AC-Ladeleistung | uint16 | W | 1 | Hardware-Obergrenze des Geräts, ab Werk festgelegt, nicht veränderbar |
| 10049 | 0x2741 | Hardware max. AC-Entladeleistung | uint16 | W | 1 | Hardware-Obergrenze des Geräts, ab Werk festgelegt, nicht veränderbar |
| 10050 | 0x2742 | Netzcode-Einspeiselimit | uint16 | W | 1 | lokal erlaubte Einspeiseleistungsgrenze; ab Werk auf den Netzcode-Standardwert gesperrt, = 10049 nach App-Freischaltung — Freischaltung nur über die App, per Modbus nicht schreibbar |
| 10051 | 0x2743 | Globales AC-Ladeleistungslimit | uint16 | W | 1 | spiegelt das geschriebene 10100 |
| 10052 | 0x2744 | Globales AC-Entladeleistungslimit | uint16 | W | 1 | spiegelt das geschriebene 10101 |
| 10053 | 0x2745 | WLAN-Signal | int16 | dBm | 1 | immer negativ; zum Beispiel -60 |
| 10054–10061 | 0x2746 | Seriennummer | string[8] | U16[8] ASCII | — | 8 Register = 16 Bytes; keine Einzelregister-Lesezugriffe — das ganze Feld lesen |
| 10062–10063 | 0x274E | Firmware-Version | string[2] | U16[2] ASCII | — | 2 Register = 4 Bytes; keine Einzelregister-Lesezugriffe — das ganze Feld lesen |

### 3.4 Lebenslange Energiezähler (10064–10081)

Alle uint32, kWh × 0.01, hohes Wort zuerst, nur lesbar, monoton steigend.

| Register | Hex | Name | Typ | Einheit | Skalierung | Bemerkungen |
| --- | --- | --- | --- | --- | --- | --- |
| 10064–10065 | 0x2750 | Netzbezug gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10066–10067 | 0x2752 | Netzeinspeisung gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10068–10069 | 0x2754 | Zählerbezug gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10070–10071 | 0x2756 | Zählereinspeisung gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10072–10073 | 0x2758 | PV-Energie gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10074–10075 | 0x275A | Ladeenergie Batterie gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10076–10077 | 0x275C | Entladeenergie Batterie gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10078–10079 | 0x275E | Bypass-Ausgangsenergie gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |
| 10080–10081 | 0x2760 | Bypass-Eingangsenergie gesamt | uint32 | kWh | 0.01 | nur lesbar; monoton steigend |

### 3.5 Steuerung — Leistungs- und SoC-Einstellungen (10100–10102)

Die drei Register dieser Gruppe können einzeln mit FC 0x06 oder gemeinsam mit
FC 0x10 geschrieben werden; alle drei überstehen Stromausfälle. Nur
10103–10106 müssen als eine atomare FC-0x10-Gruppe geschrieben werden.

| Register | Hex | Name | Typ | Einheit | Bemerkungen |
| --- | --- | --- | --- | --- | --- |
| 10100 | 0x2774 | AC-Ladeleistungslimit | uint16 | W | Standard 800; schreibbarer Bereich 50 bis Hardware-Maximum (10048); Schreibzugriffe außerhalb des Bereichs geben einen Exception-Code zurück; übersteht Stromausfälle |
| 10101 | 0x2775 | AC-Entladeleistungslimit | uint16 | W | schreibbare Untergrenze 100; schreibbare Obergrenze = lokaler Netzcode-Einspeisewert während der Sperrung, Hardware-Maximum (10049) nach App-Freischaltung; übersteht Stromausfälle |
| 10102 | 0x2776 | Sicherheits-SoC | uint16 | % | 10–100, Standard 20; außerhalb des Bereichs → Modbus-Exception 0x03; übersteht Stromausfälle |

### 3.6 Steuerung — erzwungenes Laden/Entladen in Echtzeit (10103–10106)

Das Gerät unterstützt für diese Gruppe **ausdrücklich keine
Einzelregister-Schreibzugriffe** (einzige Ausnahme: der Richtwert 3 "beenden"
darf allein mit FC 0x06 geschrieben werden). Schreibe alle vier Register in
**einen FC-0x10-Frame**. Die Gruppe ist flüchtig und endet, sobald
**entweder** der Abschalt-SoC **oder** die Dauer erreicht ist — was zuerst
eintritt. Nach einem Modbus-Timeout (siehe 10114) kehrt das Gerät in den
CONOW-Plattformmodus zurück, der aktiv war, bevor der Modbus-Dienst
aktiviert wurde.

10104 ist ein **direkter Leistungs-Sollwert**: Das Gerät gibt die eingestellte
Leistung unabhängig von der Last aus. Lastfolgendes Verhalten wird über den
Betriebsmodus (10107) in der App gewählt und erfordert einen angeschlossenen
Zähler.

| Register | Hex | Name | Typ | Einheit | Bemerkungen |
| --- | --- | --- | --- | --- | --- |
| 10103 | 0x2777 | Lade-/Entladerichtung | uint16 | — | 0 = inaktiv · 1 = laden · 2 = entladen · 3 = beenden; Richtung 3 (beenden) darf einzeln mit FC 0x06 geschrieben werden |
| 10104 | 0x2778 | Ziel-Lade-/Entladeleistung | uint16 | W | 0 bis zum über 10100 / 10101 gesetzten Limit; ein darüber liegender Wert wird automatisch als Limit geschrieben — keine Exception |
| 10105 | 0x2779 | Lade-/Entlade-Abschalt-SoC | uint16 | % | Sicherheits-SoC (10102) bis 100; beim Entladen wird ein Wert unter dem Sicherheits-SoC automatisch als 10102 geschrieben — keine Exception |
| 10106 | 0x277A | Lade-/Entladedauer | uint16 | min | 30–720; endet, sobald Dauer oder Abschalt-SoC zuerst erreicht ist |

### 3.7 Steuerung — Betriebsstrategie (10107–10114)

Alle Register dieser Gruppe überstehen Stromausfälle. Als *reserviert* markierte
Register existieren in der Übersicht, sind aber auf aktueller Hardware noch ohne Funktion.

| Register | Hex | Name | Typ | Einheit | Bemerkungen |
| --- | --- | --- | --- | --- | --- |
| 10107 | 0x277B | Betriebsmodus | uint16 | — | 1 = Eigenverbrauch · 2 = manuelle Zeitfenster · 3 = inaktiv; Standard 1; **vor dem Schreiben lesen**; mit Zähler folgt das Gerät der Zählerleistung, ohne Zähler gibt es die Grundlast aus; übersteht Stromausfälle |
| 10108 | 0x277C | Backup-SoC | uint16 | % | Sicherheits-SoC (10102) bis 100, Standard 40; *reserviert* (Backup-Betrieb, noch nicht unterstützt); übersteht Stromausfälle |
| 10109 | 0x277D | Erlaubte Rückspeiseleistung | uint16 | W | 0 = keine Rückspeisung; größer als 0 = maximal erlaubte Rückspeiseleistung; schreibbar, aber ohne angeschlossenen Zähler wirkungslos; übersteht Stromausfälle |
| 10110 | 0x277E | Batterieeinspeisung erlauben | uint16 | — | 0 = verboten · 1 = erlaubt; *reserviert* (Netzeinspeisemodus, noch nicht unterstützt); übersteht Stromausfälle |
| 10111 | 0x277F | Bypass-Dauerschalter | uint16 | — | 0 = aus · 1 = ein; Standard aus; übersteht Stromausfälle |
| 10112 | 0x2780 | Notstrom-Ausgangsschalter | uint16 | — | 0 = aus · 1 = ein; Standard aus; übersteht Stromausfälle |
| 10113 | 0x2781 | PV-Abregelungsschalter | uint16 | — | 0 = aus · 1 = ein; Standard aus; *reserviert, noch nicht unterstützt*; übersteht Stromausfälle |
| 10114 | 0x2782 | Modbus-Timeout | uint16 | s | 0–3600, 0 = deaktiviert (Standard); Watchdog — ohne gültigen **Schreib**frame für diese Dauer kehrt das Gerät in den CONOW-Plattformmodus zurück, der vor dem Aktivieren des Modbus-Dienstes aktiv war; übersteht Stromausfälle |

### 3.8 Steuerung — Generator und digitale Ausgänge (10115–10122)

Auf Modellen ohne Generatorfunktion lesen die Register 0 und
Schreibzugriffe geben eine Exception zurück. Die beiden DO-Register sind
flüchtig; der Rest übersteht Stromausfälle.

| Register | Hex | Name | Typ | Einheit | Bemerkungen |
| --- | --- | --- | --- | --- | --- |
| 10115 | 0x2783 | Generatorschalter | uint16 | — | 0 = aus · 1 = ein; übersteht Stromausfälle |
| 10116 | 0x2784 | Generator-Startzeit | uint16 | hhmm | Stunde im hohen Byte (0–23), Minute im niedrigen Byte (0–59); übersteht Stromausfälle |
| 10117 | 0x2785 | Generator-Stoppzeit | uint16 | hhmm | Stunde im hohen Byte (0–23), Minute im niedrigen Byte (0–59); übersteht Stromausfälle |
| 10118 | 0x2786 | Generatorleistung | uint16 | W | übersteht Stromausfälle |
| 10119 | 0x2787 | Generator-Start-SoC | uint16 | % | Ziel-SoC, das die Generatorladung auslöst; übersteht Stromausfälle |
| 10120 | 0x2788 | Generator-Stopp-SoC | uint16 | % | Abschalt-SoC, der die Generatorladung beendet; übersteht Stromausfälle |
| 10121 | 0x2789 | DO1-Steuerung | uint16 | — | 0 = aus · 1 = ein; flüchtig |
| 10122 | 0x278A | DO2-Steuerung | uint16 | — | 0 = aus · 1 = ein; flüchtig |

### 3.9 Steuerung — Grundlast (10123–10148)

Wenn kein Zähler angeschlossen ist (oder der Zähler defekt ist), gibt das
Gerät außerhalb der konfigurierten Zeitfenster den Grundlast-Sollwert aus;
die Einstellung übersteht Stromausfälle.

<strong>Hinweis zur Cloud-Synchronisierung:</strong> Nach einem Gerätestart können bei
bestehender Cloud-Verbindung die erlaubte Rückspeiseleistung (10109), die
Grundlast (10123) und der Grundlast-Zeitplan (10124–10148) mit den in der
CONOW-App gesetzten Werten synchronisiert werden und ihre aktuellen Werte
überschreiben. Müssen die Modbus-Einstellungen erhalten bleiben, schreibe
diese Register erneut.

| Register | Hex | Name | Typ | Einheit | Bemerkungen |
| --- | --- | --- | --- | --- | --- |
| 10123 | 0x278B | Grundlast | uint16 | W | 0–3000, Standard 200; übersteht Stromausfälle |
| 10124 | 0x278C | Grundlast-Fensteranzahl | uint16 | — | 0–8; das Gerät führt nur die ersten N Fenster aus |

**Grundlast-Zeitplan** — eine Fensteranzahl (0–8), gefolgt von 8 Fenstern aus
(Start, Ende, Leistung). Schreibe nur die tatsächlich genutzten ersten N
Fenster und setze das Anzahlregister auf N; das Gerät führt nur die ersten N
Fenster aus und ignoriert den Rest. Alle hhmm-Register codieren die Stunde
im hohen Byte, die Minute im niedrigen Byte.

| Fenster | Start | Ende | Leistung |
| --- | --- | --- | --- |
| 1 | 10125 (0x278D) | 10126 (0x278E) | 10127 (0x278F) |
| 2 | 10128 (0x2790) | 10129 (0x2791) | 10130 (0x2792) |
| 3 | 10131 (0x2793) | 10132 (0x2794) | 10133 (0x2795) |
| 4 | 10134 (0x2796) | 10135 (0x2797) | 10136 (0x2798) |
| 5 | 10137 (0x2799) | 10138 (0x279A) | 10139 (0x279B) |
| 6 | 10140 (0x279C) | 10141 (0x279D) | 10142 (0x279E) |
| 7 | 10143 (0x279F) | 10144 (0x27A0) | 10145 (0x27A1) |
| 8 | 10146 (0x27A2) | 10147 (0x27A3) | 10148 (0x27A4) |

Leistungsbereich pro Fenster 0–3000 W.

### 3.10 Steuerung — manueller Lade-/Entlade-Zeitplan TOU (10149–10189)

Betriebsmodus 2 (manuelle Zeitfenster) führt diesen Zeitplan aus: bis zu 8
Strategien, jedes ein Zeitfenster, das bis zu einem Ziel-SoC lädt oder mit
festgelegter Leistung entlädt. Schreibe nur die tatsächlich genutzten ersten
N Fenster und setze das Anzahlregister (**10149, 0x27A5**, 0–8) auf N; das
Gerät führt nur die ersten N Fenster aus. Übersteht Stromausfälle.

| Register | Hex | Name | Typ | Einheit | Bemerkungen |
| --- | --- | --- | --- | --- | --- |
| 10149 | 0x27A5 | TOU-Fensteranzahl | uint16 | — | 0–8; das Gerät führt nur die ersten N Fenster aus; übersteht Stromausfälle |

Zeit außerhalb der konfigurierten Fenster folgt der **Baseline-Strategie**.
Die Baseline umfasst zwei Strategien — Eigenverbrauch und Idle — und ist
standardmäßig Idle; sie wird in der CONOW App angepasst.

Jedes Fenster besteht aus 5 Registern — Start, Ende, Modus, dann entweder
Ziel-SoC oder Entladeleistung (das inaktive Feld wird ignoriert):

| Feld | Bedeutung |
| --- | --- |
| Start / Ende | hhmm (Stunde hohes Byte, Minute niedriges Byte) |
| Modus | 0 = laden (nur Ziel-SoC gilt) · 1 = entladen (nur Entladeleistung gilt) |
| Ziel-SoC | uint16 %, gilt bei Modus = 0 |
| Entladeleistung | uint16 W, gilt bei Modus = 1 |

| Fenster | Start | Ende | Modus | Ziel-SoC | Entladeleistung |
| --- | --- | --- | --- | --- | --- |
| 1 | 10150 (0x27A6) | 10151 (0x27A7) | 10152 (0x27A8) | 10153 (0x27A9) | 10154 (0x27AA) |
| 2 | 10155 (0x27AB) | 10156 (0x27AC) | 10157 (0x27AD) | 10158 (0x27AE) | 10159 (0x27AF) |
| 3 | 10160 (0x27B0) | 10161 (0x27B1) | 10162 (0x27B2) | 10163 (0x27B3) | 10164 (0x27B4) |
| 4 | 10165 (0x27B5) | 10166 (0x27B6) | 10167 (0x27B7) | 10168 (0x27B8) | 10169 (0x27B9) |
| 5 | 10170 (0x27BA) | 10171 (0x27BB) | 10172 (0x27BC) | 10173 (0x27BD) | 10174 (0x27BE) |
| 6 | 10175 (0x27BF) | 10176 (0x27C0) | 10177 (0x27C1) | 10178 (0x27C2) | 10179 (0x27C3) |
| 7 | 10180 (0x27C4) | 10181 (0x27C5) | 10182 (0x27C6) | 10183 (0x27C7) | 10184 (0x27C8) |
| 8 | 10185 (0x27C9) | 10186 (0x27CA) | 10187 (0x27CB) | 10188 (0x27CC) | 10189 (0x27CD) |

### 3.11 Steuerung — Zeitkalibrierung (10190)

Solange das Gerät nicht mit der Cloud verbunden ist, kann seine Uhr driften,
und TOU- oder Grundlast-Zeitfenster laufen dann zur falschen Zeit. Lies die
Geräteuhrzeit und kalibriere sie mit einem Schreibzugriff, wenn sie gedriftet
ist — prüfe zuerst, dass deine eigene Zeitquelle korrekt ist.

| Register | Hex | Name | Typ | Einheit | Skalierung | Bemerkungen |
| --- | --- | --- | --- | --- | --- | --- |
| 10190 | 0x27CE | Geräteuhrzeit (lesen / kalibrieren) | uint16 | hhmm | — | Stunde im hohen Byte (0–23), Minute im niedrigen Byte (0–59); kalibriert nur die Tageszeit — ohne Datum, Wochentag oder Zeitzone; flüchtig |

### 3.12 Protokoll-Register (9984–9986)

Identitäts- und Verifizierungsregister, die beide Transportwege gemeinsam nutzen; der Ablauf ist in den Abschnitten oben beschrieben.

| Register | Hex | Name | Typ | Einheit | Bemerkungen |
| --- | --- | --- | --- | --- | --- |
| 9984 | 0x2700 | Unit-ID | uint16 | — | RTU-Slave-Adresse und TCP-Unit-ID; lesbar und schreibbar, Bereich 128–176 (0x80–0xB0); eine Änderung erfordert keine erneute TCP-Verifizierung |
| 9985–9986 | 0x2701 | TCP-Bestätigungscode | uint32 | — | nur schreibbar; der dynamische 8-stellige hexadezimale Code von der Gerätedetailseite der CONOW App (erneuert alle 120 Sekunden); siehe [Bestätigungscode](#bestätigungscode-direktes-modbus-tcp-all-in-one-geräte) |

---

## 4 Frame-Beispiele

Framing und CRC-16 (Modbus) sind identisch mit der v1-Anleitung: Slave `0xA0`,
Funktionscode, Daten, CRC niedriges Byte zuerst. Die folgenden Beispiele sind
RTU-Frames; zum TCP-Frameformat siehe [Modbus-TCP-Frameformat (MBAP)](#modbus-tcp-frameformat-mbap).

**Firmware-Version-Feld lesen (Firmware-Versionsprüfung, 10062 × 2):**

```
A0 03 27 4E 00 02 B7 D9
```

**Echtzeitdaten lesen (10000 × 12):**

```
A0 03 27 10 00 0C 57 CF
```

**Einzelregister schreiben — AC-Entladeleistungslimit 700 W → 10101:**

```
A0 06 27 75 02 BC 8B 04
```

**Atomarer Gruppen-Schreibzugriff — Entladen mit 500 W erzwingen bis SoC 80%
oder 120 min (FC 0x10, Register 10103–10106):**

```
A0 10 27 77 00 04 08  00 02 01 F4 00 50 00 78  84 66
│  │  └───┘ └───┘ │   └───┘ └───┘ └───┘ └───┘  └───┘
│  │  │     │     │   │     │     │     │      └── CRC-16
│  │  │     │     │   │     │     │     └── Register 10106: 0x0078 (120 Min.)
│  │  │     │     │   │     │     └── Register 10105: 0x0050 (80%)
│  │  │     │     │   │     └── Register 10104: 0x01F4 (500 W)
│  │  │     │     │   └── Register 10103: 0x0002 (Entladen)
│  │  │     │     └── Byteanzahl: 8 (4 Register × 2 Bytes)
│  │  │     └── Anzahl: 4 Register
│  │  └── Startadresse: 0x2777 (10103)
│  └── FC 0x10
└── Slave 160 (0xA0)
```

### Modbus-TCP-Frameformat (MBAP)

Über TCP reist dieselbe PDU in einem 7-Byte-MBAP-Header; es gibt **keine CRC** — die Integrität sichert die TCP-Transportschicht.

| MBAP-Feld | Größe | Wert |
| --- | --- | --- |
| Transaktions-ID | 2 Bytes | vom Master frei gewählt; wird in der Antwort unverändert zurückgegeben |
| Protokoll-ID | 2 Bytes | `0x0000` (Modbus) |
| Länge | 2 Bytes | Anzahl der folgenden Bytes (Unit-ID + PDU) |
| Unit-ID | 1 Byte | die Unit-ID des Geräts — standardmäßig `0xA0` (Register 9984) |

**Bestätigungscode schreiben (direktes TCP) — Code `1A2B3C4D` → 9985–9986:**

```
00 01  00 00  00 0B  A0  10  27 01  00 02  04  1A 2B 3C 4D
└───┘  └───┘  └───┘  │   │   └───┘  └───┘  │   └─────────┘
│      │      │      │   │     │      │    │   Bestätigungscode 0x1A2B3C4D
│      │      │      │   │     │      │    └── Byteanzahl: 4
│      │      │      │   │     │      └── Anzahl: 2 Register
│      │      │      │   │     └── Startadresse: 0x2701 (9985)
│      │      │      │   └── FC 0x10
│      │      │      └── Unit-ID: 160 (0xA0)
│      │      └── Länge: 11 Bytes (Unit-ID + PDU)
│      └── Protokoll-ID: 0x0000 (Modbus)
└── Transaktions-ID: 0x0001 — wird in der Antwort zurückgegeben
```

Die Antwort wiederholt den Header mit Länge 6: `00 01 00 00 00 06 A0 10 27 01 00 02`.

Prüfe die CRC eines beliebigen Frames selbst:

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
print(f"{crc16(frame):04X}")   # erst niedriges Byte anhängen, dann hohes
PY
```

**Exception-Antworten** — im Fehlerfall antwortet das Gerät mit `[Slave][Funktionscode + 0x80][Exception-Code][CRC]`; die Codes und ihre Bedeutungen stehen unter [6.1 Modbus-Exception-Codes](#61-modbus-exception-codes).

### Schnelltest über die Kommandozeile

Die Frames oben sind rohe Protokollbytes. Für einen ersten Livetest kannst du das Gerät auch mit einem Standard-Modbus-Client ansteuern, zum Beispiel [mbpoll](https://github.com/epsilonrt/mbpoll) oder [pymodbus](https://github.com/pymodbus/pymodbus). Beide Beispiele führen die [Firmware-Versionsprüfung](#firmware-versionsprüfung) aus — Lesen von 10062–10063 mit FC 0x03 — über RS-485 RTU; RTU benötigt keinen Bestätigungscode.

```sh
# mbpoll — RTU auf /dev/ttyUSB0, Slave 160 (0xA0), 38400 8N1
# -P none ist erforderlich: mbpoll verwendet standardmäßig gerade Parität
mbpoll -m rtu -a 160 -b 38400 -P none -t 4 -0 -r 10062 -c 2 -1 /dev/ttyUSB0
# hänge ":string" an -t 4 an, um die Register als ASCII-Zeichen auszugeben
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
    print(struct.pack(">HH", *rr.registers).decode())  # 4 ASCII-Zeichen
client.close()
```

Bei direktem Modbus TCP muss zuerst die [Verifizierung](#bestätigungscode-direktes-modbus-tcp-all-in-one-geräte) abgeschlossen werden. Mit dem Beispielcode `1A2B3C4D`:

```sh
# mbpoll — uint32-Bestätigungscode schreiben, hohes Wort zuerst (9985 = 0x1A2B, 9986 = 0x3C4D)
mbpoll -m tcp -a 160 -t 4 -0 -r 9985 -1 192.168.1.100 6699 15629
```

Das Äquivalent in pymodbus ist `client.write_registers(address=9985, values=[0x1A2B, 0x3C4D], slave=160)` auf einem `ModbusTcpClient("192.168.1.100", port=502)`.

---

## 5 Wichtige Hinweise

1. **Modbus gegen App-Priorität.** Modbus und App/Cloud sind zwei
   unabhängige Steuerungspfade:

   Während Modbus aktiv ist, verlässt das Gerät den App-seitigen Betriebsmodus
   und folgt nur Modbus; nachdem der Master mit dem Schreiben aufhört und das
   Timeout bei 10114 abläuft, kehrt das Gerät in den CONOW-Plattformmodus von
   vor dem Aktivieren des Modbus-Dienstes zurück.
2. **Gruppen-Schreibregeln.** Befehle, die einer atomaren Schreiboperation
   bedürfen (Echtzeitsteuerung), werden gemäß den Registeradressen in einer
   Anforderung geschrieben.
3. **Zeitpläne mit konsistenter Anzahl.** Schreibe nur die tatsächlich
   genutzten ersten N Fenster und setze das Anzahlregister (10124 / 10149)
   auf N — das Gerät führt nur die ersten N Fenster aus.
4. **Betriebsmodus: erst lesen, dann schreiben.** Lies vor dem Schreiben von
   10107 den aktuellen Wert und schreibe dann den Zielwert.
5. **Persistenz.** 10103–10106, 10121–10122 und 10190 sind flüchtig;
   alle anderen Register des Steuerungsbereichs überstehen Stromausfälle.
6. **CRC-Fehler werden stillschweigend verworfen.** Wiederhole nach einem
   Timeout bis zu 3 Mal, mindestens 500 ms Abstand, und werte 3
   aufeinanderfolgende Timeouts als Verbindungsfehler. Frage Realtime-Werte
   nicht öfter als einmal pro 1 s ab; wenn eine Anfrage mehrere Register liest
   oder schreibt, wird ein Abfrageintervall von mindestens 2 s empfohlen;
   frage Energie-/Steuerregister nicht öfter als einmal pro 5 s ab; poll die
   gesamte Registerübersicht nicht mit hoher Frequenz.
7. **Voraussetzungen einhalten.** Gerät einmal über die CONOW ECO App in
   Betrieb genommen und der *Modbus-Dienst* aktiviert — ein nie in Betrieb
   genommenes Gerät bleibt unabhängig von der Firmware stumm, und mit
   deaktiviertem *Modbus-Dienst* werden RTU-Lese- und -Schreibzugriffe mit
   Exception 0x06 beantwortet
   ([6.1 Modbus-Exception-Codes](#61-modbus-exception-codes)).
8. **Der Watchdog zählt nur Schreibframes.** Der Watchdog bei 10114 wird nur
   von gültigen Schreibframes (FC 0x06 / 0x10) zurückgesetzt — Poll-Lesezugriffe
   setzen ihn nicht zurück. War die zuletzt empfangene Anweisung Richtung =
   inaktiv (10103 = 0), hält das Gerät diesen Zustand unbegrenzt und fällt
   nicht zurück; nur eine neue Anweisung oder das Deaktivieren des
   Modbus-Dienstes ändert das.
9. **Zeitgleich nur ein Schreiber.** Sind RTU und TCP beide aktiviert, folgen
   Schreibzugriffe der RTU-Prioritätsregel unter
   [Gleichzeitiges RTU und TCP](#gleichzeitiges-rtu-und-tcp-schreib-priorität);
   ein mit 0x86 / 0x90 abgelehnter TCP-Schreibzugriff ist erwartetes
   Verhalten, kein Verbindungsfehler.

---

## 6 Fehlerbehebung

Beginne mit der ersten Prüfung zum Symptom und folge dann den verlinkten
Abschnitten.

| Symptom | Erste Prüfung | Hinweise / Referenz |
| --- | --- | --- |
| Gerät antwortet gar nicht | Modbus-Schalter in der App aktiviert; Slave-Adresse / Unit-ID entspricht dem aktuellen Wert in 9984 | bei deaktiviertem Schalter werden RTU-Lese- und -Schreibzugriffe mit Exception 0x06 beantwortet ([6.1 Modbus-Exception-Codes](#61-modbus-exception-codes)); Standard 0xA0 ([Übertragungsparameter](#übertragung-und-verbindungsparameter)) |
| RTU zeitweise ohne Antwort oder CRC-Fehler | CRC-16-Berechnung (Polynom 0xA001) und serielle Parameter 38400-8-N-1 | Frames mit falschem CRC werden verworfen, ohne zu antworten — prüfe zuerst das CRC, dann Verdrahtung und Adresse |
| Keine Antwort beim Lesen von 128 Registern oder mehr | Anfrage länger als 127 Register? | FC 0x03 bedient höchstens 127 Register pro Anfrage ([Lesebegrenzung](#übertragung-und-verbindungsparameter)) |
| TCP ohne Antwort, Verifizierungsfehler oder Schreibzugriffe ohne Wirkung | zuerst TCP-Schalter, Netzwerk und Unit-ID; ein Verifizierungsfehler bedeutet: Verifizierung über 9985–9986 wiederholen; auch nach der Verifizierung abgelehnte Schreibzugriffe — RTU-Schreib-Prioritätsregel prüfen | nicht verbundene Endpunkte bleiben stumm; verbundene, aber unverifizierte Anfragen erhalten einen Verifizierungsfehler ([Bestätigungscode](#bestätigungscode-direktes-modbus-tcp-all-in-one-geräte), [Gleichzeitiges RTU und TCP](#gleichzeitiges-rtu-und-tcp-schreib-priorität)) |
| Schreibzugriff ignoriert oder mit Exception beantwortet | geschriebener Wert innerhalb des Registerbereichs? | Schreibzugriffe außerhalb des Bereichs werden mit Exception 0x03 abgelehnt ([6.1 Modbus-Exception-Codes](#61-modbus-exception-codes)) |
| Geräneverhalten ändert sich nach dem Trennen | Watchdog 10114 aktiviert? | bei 10114 = 0 behält das Gerät seinen Betriebsmodus; mit gesetztem Timeout fällt es in den CONOW-Plattformmodus von vor dem Aktivieren des Modbus-Dienstes zurück ([Hinweise](#5-wichtige-hinweise)) |

### 6.1 Modbus-Exception-Codes

Lese- und Schreibbefehle nutzen nur FC 0x03 / 0x06 / 0x10, und die Standard-Exception-Codes 0x01–0x03 erscheinen nur in Antworten auf diese drei Funktionscodes; im Fehlerfall antwortet das Gerät mit `[Slave][Funktionscode + 0x80][Exception-Code][CRC]`:

| Code | Bedeutung | Typische Ursache |
| --- | --- | --- |
| 0x01 | Unzulässige Funktion | Funktionscode wird nicht unterstützt (Lese- und Schreibbefehle unterstützen nur FC 0x03 / 0x06 / 0x10) |
| 0x02 | Unzulässige Datenadresse | Register existiert nicht oder wird von diesem Modell nicht unterstützt; während einer TCP-Verifizierungssperre werden Lese- und Schreibzugriffe mit 0x02 beantwortet (Lesen von 9984 ausgenommen) |
| 0x03 | Unzulässiger Datenwert | geschriebener Wert außerhalb des Bereichs |

0x04 / 0x05 sind gerätespezifische Statuscodes der Verifizierungsschicht bei
direktem Modbus TCP, keine Standard-Lese-/Schreib-Exception-Antworten für
FC 0x03 / 0x06 / 0x10; die Szenarien der Verifizierungsschicht stehen unter
[Bestätigungscode](#bestätigungscode-direktes-modbus-tcp-all-in-one-geräte):

| Code | Bedeutung | Typische Ursache |
| --- | --- | --- |
| 0x04 | MAC-Adresse geändert (gerätespezifisch) | der TCP-Bestätigungscode wurde durch eine MAC-Adressänderung des Adapters ungültig — Code erneut schreiben |
| 0x05 | Manuelle Aktualisierung (gerätespezifisch) | wird zurückgegeben, wenn nach einer manuellen Aktualisierung des Bestätigungscodes per TCP zugegriffen wird — neuen Code schreiben |

0x06 (gerätespezifisch) wird nur bei Modbus RTU zurückgegeben — nachdem *Modbus-Dienst aktivieren* in der App ausgeschaltet wurde, werden Lese- und Schreibzugriffe auf Register mit 0x06 beantwortet:

| Code | Bedeutung | Typische Ursache |
| --- | --- | --- |
| 0x06 | Modbus-Dienst nicht aktiviert (gerätespezifisch) | *Modbus-Dienst aktivieren* in der App ausgeschaltet — erneut aktivieren und danach lesen bzw. schreiben |

### 6.2 Geräte-Fehlercode (Alarm-Bitmap, 10001–10002)

Der Geräte-Fehlercode (10001–10002, uint32) ist eine 32-Bit-Bitmap: Ein auf `1` gesetztes Bit bedeutet, dass der zugehörige Alarm aktuell aktiv ist; mehrere Bits können gleichzeitig gesetzt sein. Beide Register müssen in derselben Anfrage zusammen gelesen werden.

| Bit | CBE2000 Pro | Atlas 6000 | Lyra 2500 |
| --- | --- | --- | --- |
| bit0 | Akkupack-1-Alarm | Zellüberspannung | Zellüberspannung |
| bit1 | Akkupack-2-Alarm | Zellunterspannung | Zellunterspannung |
| bit2 | Akkupack-3-Alarm | Batterieüberspannung | Batterieüberspannung |
| bit3 | Akkupack-4-Alarm | Batterieunterspannung | Batterieunterspannung |
| bit4 | Akkupack-5-Alarm | Laden bei Niedrigtemperatur | Laden bei Niedrigtemperatur |
| bit5 | Akkupack-6-Alarm | Laden bei Hochtemperatur | Laden bei Hochtemperatur |
| bit6 | — | Entladen bei Niedrigtemperatur | Entladen bei Niedrigtemperatur |
| bit7 | — | Entladen bei Hochtemperatur | Entladen bei Hochtemperatur |
| bit8 | Haupt-Erweiterungs-Kommunikationsfehler | Ladestrom 1 | Ladestrom 1 |
| bit9 | LED-Panel-Kommunikationsfehler | Ladestrom 2 | Ladestrom 2 |
| bit10 | Wechselrichter-Kommunikationsfehler | Entladestrom 1 | Entladestrom 1 |
| bit11 | Wechselrichterfehler | Entladestrom 2 | Entladestrom 2 |
| bit12 | WLAN-Modul-Kommunikationsfehler | MOS-Übertemperatur | MOS-Übertemperatur |
| bit13 | PV1-Alarm | Temperaturdifferenz-Alarm | Temperaturdifferenz-Alarm |
| bit14 | PV2-Alarm | Spannungsdifferenz-Alarm | Spannungsdifferenz-Alarm |
| bit15 | PV3-Alarm | Kurzschluss | Kurzschluss |
| bit16 | PV4-Alarm | NTC-Ausfall | NTC-Ausfall |
| bit17 | Netzfehler (Unter-/Überfrequenz) | Zellausfall | Zellausfall |
| bit18 | Wechselrichter-Ausgangsalarm | AFE-Ausfall | AFE-Ausfall |
| bit19 | — | Lade-MOS-Alarm | Lade-MOS-Alarm |
| bit20 | — | Entlade-MOS-Alarm | Entlade-MOS-Alarm |
| bit21 | — | Heizfolie offen | — |
| bit22 | Kurzschluss 2 | — | — |
| bit23 | Überlast am Notstrom-Eingang | Shunt-Alarm | Shunt-Alarm |
| bit24 | Wiederholter Adressierungsfehler (Erweiterung) | Haupt-Erweiterungs-Kommunikationsfehler | Haupt-Erweiterungs-Kommunikationsfehler |
| bit25 | Wiederholter Adressierungsfehler (Haupt) | Wechselrichter-Kommunikation | Wechselrichter-Kommunikation |
| bit26 | Kurzschluss 1 | WLAN-Kommunikationsfehler | WLAN-Kommunikationsfehler |
| bit27 | — | — | — |
| bit28 | — | Überlast bei Niedrigtemperatur | Überlast bei Niedrigtemperatur |
| bit29 | — | Überlast am Notstrom-Eingang | Überlast am Notstrom-Eingang |
| bit30 | — | Akkuklemmen-Übertemperatur | Zählerkreisfehler |
| bit31 | — | Zählerkreisfehler | — |

Ursache und Lösung je Alarm, zur Selbsthilfe:

**Akkualarme**

| Alarm | Ursache | Lösung |
| --- | --- | --- |
| Zellüberspannung | Zellspannung kurzzeitig über der Obergrenze | normaler Schutz — Wiederherstellung abwarten; bei häufigem Auftreten Support kontaktieren |
| Zellunterspannung | Zellspannung unter der Sicherheitsgrenze | Akku zeitnah laden; Support kontaktieren, wenn Laden nicht möglich ist oder es wiederholt auftritt |
| Batterieüberspannung | Gesamtspannung des Akkupacks über der Obergrenze | automatische Wiederherstellung abwarten; Support kontaktieren, wenn es wiederholt auftritt |
| Batterieunterspannung | Gesamtspannung des Akkupacks unter der Untergrenze | Akku sofort laden; Support kontaktieren, wenn Laden nicht möglich ist |
| Laden bei Niedrigtemperatur | Temperatur zu niedrig zum Laden | Umgebungstemperatur erhöhen oder wärmere Bedingungen abwarten |
| Laden bei Hochtemperatur | Ladetemperatur zu hoch | Gerät an einen kühlen, belüfteten Ort stellen und Abdeckungen entfernen; nach dem Abkühlen fortsetzen |
| Entladen bei Niedrigtemperatur | Entladetemperatur zu niedrig | Last reduzieren und Umgebung erwärmen; nach der Erholung normal weiterverwenden |
| Entladen bei Hochtemperatur | Entladetemperatur zu hoch | Abdeckungen entfernen und direkte Sonne meiden; nach dem Abkühlen fortsetzen |
| Ladestrom 1 | Ladestrom über der Stufe-1-Schwelle | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |
| Ladestrom 2 | Ladestrom weit über dem Limit | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |
| Entladestrom 1 | Entladestrom über der Schwelle, Schutz ausgelöst | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |
| Entladestrom 2 | Entladestrom weit über dem Limit, erzwungener Schutz | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |
| MOS-Übertemperatur | Temperatur der Leistungs-MOS zu hoch | Laden und Entladen pausieren; automatische Erholung nach dem Abkühlen; bei häufigem Auftreten Support kontaktieren |
| Temperaturdifferenz-Alarm | Temperaturdifferenz zwischen den Messpunkten zu groß | Erholung abwarten und beobachten; Support kontaktieren, wenn es wiederholt auftritt |
| Spannungsdifferenz-Alarm | Spannungsdifferenz zwischen den Zellen zu groß | System-Balancing abwarten; Support kontaktieren, wenn es wiederholt auftritt |
| Kurzschluss | Kurzschluss auf der DC-Seite erkannt, Schutz aktiv | sofort ausschalten und Verdrahtung sowie Lasten prüfen, dann Neustart-Test; Support kontaktieren, falls keine Erholung |
| NTC-Ausfall | Temperatursensor offen oder kurzgeschlossen | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |
| Zellausfall | eine Zelle ausgefallen oder abgetrennt | Gerät außer Betrieb nehmen und zeitnah Support kontaktieren |
| AFE-Ausfall | Ausfall der vorgeschalteten Messschaltung | Gerät herunterfahren und Support zur Diagnose kontaktieren |
| Lade-MOS-Alarm | ungewöhnliches Schaltverhalten des Lade-MOS | Laden sofort stoppen und Support kontaktieren |
| Entlade-MOS-Alarm | ungewöhnliches Schaltverhalten des Entlade-MOS | Lasten abtrennen und Support kontaktieren |
| Heizfolie offen | Heizfunktion ausgefallen | Laden pausiert bei Niedrigtemperatur; Verbindungen prüfen; Support kontaktieren, falls weiterhin anormal |
| Shunt-Alarm | Strommessung anormal | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |

**System- und weitere Alarme**

| Alarm | Ursache | Lösung |
| --- | --- | --- |
| Haupt-Erweiterungs-Kommunikationsfehler | Kommunikation zwischen Haupt- und Erweiterungssteuerung anormal | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |
| LED-Panel-Kommunikationsfehler | Kommunikation mit dem LED-/Anzeige-Panel unterbrochen oder anormal | Neustart versuchen und Erholung beobachten; Support kontaktieren, falls keine Erholung |
| Wechselrichter-Kommunikationsfehler | Kommunikation zwischen Hauptsteuerung und Wechselrichter unterbrochen oder anormal | Gerät außer Betrieb nehmen und zeitnah Support kontaktieren |
| Wechselrichterfehler | Wechselrichter funktionsgestört oder ohne Start oder Ausgang | Gerät außer Betrieb nehmen und zeitnah Support kontaktieren |
| WLAN-Modul-Kommunikationsfehler | keine WLAN-Verbindung möglich | WLAN-Signal, Router-Einstellungen und Passwort prüfen und neu verbinden |
| Überlast bei Niedrigtemperatur | bei Niedrigtemperatur überschreitet die Notstrom-Ausgangsleistung die maximal zulässige Entladeleistung | Notstrom-Lasten reduzieren oder abtrennen |
| Überlast am Notstrom-Eingang | Eingangsleistung am Notstromanschluss übersteigt die maximal zulässige Ladeleistung des Akkus | Eingangsleistung reduzieren oder das Eingabegerät trennen |
| Kurzschluss 1 / Kurzschluss 2 | Vorladen nicht erfolgreich — der vom BMS erfasste 1. / 2. Kurzschluss | automatische Erholung abwarten; ein dritter Kurzschluss in Folge beeinträchtigt die Nutzung — Neustart versuchen und beobachten, Support kontaktieren, falls keine Erholung |
| Netzfehler | Netzfrequenz außerhalb des zulässigen Bereichs (Unter-/Überfrequenz) | Wiederherstellung des Netzes abwarten; bei anhaltender Anomalie Netzbetreiber oder Support kontaktieren |
| Zählerkreisfehler | CT abnorm, Zählerdaten nicht verfügbar | zur Sicherheit von Gerät und Netz gibt das Gerät nur die Basislast aus; Zählerverdrahtung prüfen |
| Akkuklemmen-Übertemperatur | Temperatur der Akkuklemmen zu hoch | Klemmverdrahtung und Lasten prüfen; Support kontaktieren, falls weiterhin anormal |
| Wechselrichter-Ausgangsalarm | Wechselrichter-Ausgang anormal | Alarmseite der App öffnen, den konkreten Alarm aufsuchen und dort behandeln |
| Akkupack-N-Alarm | der zugehörige Akkupack hat einen Alarm; Modbus nennt den Typ nicht | Alarmseite der App für dieses Pack öffnen und den konkreten Alarm behandeln |
| PV1–PV4-Alarm | der zugehörige PV-Eingang hat einen Alarm; Modbus nennt den Typ nicht | Alarmseite der App öffnen; diesen PV-Strang prüfen |
| Wiederholter Adressierungsfehler Haupt/Erweiterung | Adressvergabe der Packs wiederholt fehlgeschlagen | Gerät neu starten und beobachten; Support kontaktieren, falls weiterhin anormal |
