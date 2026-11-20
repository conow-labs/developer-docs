# CONOW Developer Docs (Deutsch)

**Offene Protokollreferenzen und Integrationsleitfäden für CONOW Energiespeicher-
und Balkonkraftwerk-Produkte.**

Sprache / Language / 语言 / Taal: [English](README.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [Nederlands](README.nl.md)

---

## Updates

- **2026-11-20**
  - Registerübersicht für Firmware v2 hinzugefügt: direktes Modbus TCP, Protokoll-Register 9984–9986, vollständiger Steuerbereich 10100–10190 und Exception-Code-Tabellen.
  - Weitere Sprachen hinzugefügt: chinesische, deutsche und niederländische Ausgaben der README und beider Registerübersichten.

## Integrationswege

Wähle den Weg, der zu deinem Setup passt:

| Weg | Am besten für | Verbindung | Wo |
|------|----------|------------|-------|
| **Modbus RTU / TCP** | lokale Steuerung, keine Cloud-Abhängigkeit, eigenes EMS | RS-485 / Ethernet (am Gerät) | [`modbus/`](modbus/) — in diesem Repository |
| **Home Assistant Local** | Home-Assistant-Nutzer, die lokale CONOW-Energieentitäten und Automatisierungen ohne Cloud-Abhängigkeit möchten | RS-485 / Modbus RTU | [conow-labs/home-assistant-local](https://github.com/conow-labs/home-assistant-local) |
| **Home Assistant** | Smart-Home-Nutzer, die Dashboards, Automatisierungen und CONOW-Energieentitäten möchten | Cloud (Tuya) | [conow-labs/home-assistant](https://github.com/conow-labs/home-assistant) |
| **Agent Skills** | KI-Agenten (zum Beispiel Claude), die Energiedaten lesen und steuern | Cloud | [conow-labs/agent-skills](https://github.com/conow-labs/agent-skills) |

> [!WARNING]
> Steuerregister und Befehle können verändern, wie dein System lädt, entlädt und ins Netz einspeist. Lies vor dem Schreiben eines Steuerwerts die Sicherheitshinweise des Produkts.

## Inhalt dieses Repositorys

| Verzeichnis | Beschreibung |
|-----------|-------------|
| [`modbus/`](modbus/) | Modbus-API-Referenzen — Registerübersichten je Firmware-Version, Datentypen und Frame-Beispiele (RTU; TCP ab v2-Firmware) |

## Unterstützte Produkte

- **CBE Serie** — All-in-one-Balkonkraftwerk mit Speicher (CBE2000 Pro)
- **Lyra Serie** — AC-gekoppeltes Speichersystem (Lyra 2500 AC, Lyra 2500 Pro)
- **Atlas Serie** — Speichersystem mit hoher Kapazität (Atlas 6000 AC)

## Firmware-Version und Registerdokumentation (wichtig)

**Voraussetzungen für den Modbus-Zugriff:** das Gerät muss über die **CONOW ECO
App** in Betrieb genommen worden sein und mindestens einmal online gegangen sein —
ein fabrikneues, nie aktiviertes Gerät beantwortet keine Anfrage an der
RS-485-Schnittstelle; aktiviere in der App unter *Geräte → dein Gerät →
Einstellungen* die Option *Modbus-Dienst aktivieren* — in älteren App-Versionen verwende stattdessen
*Einstellungen → Betriebsmodus → DIY-Modus*; beschränke Schreibzugriffe
jederzeit auf einen einzelnen Master.

Mit der **v2-Firmware** hat sich das Modbus-Registerlayout geändert — die
beiden Registerkarten sind gegenseitig inkompatibel; zuerst die Version
prüfen, dann verwenden:

| Dokument | Firmware | Registerbereich |
| --- | --- | --- |
| [balcony-solar-storage-v2.de.md](modbus/balcony-solar-storage-v2.de.md) | **ab der v2-Mindestversion** (Lyra 1.01.16 · CBE2000 Pro 1.02.17 · Atlas 1.01.08) | Monitoring 10000–10081 · Steuerung 10100–10190 · Protokoll 9984–9986 |
| [balcony-solar-storage.de.md](modbus/balcony-solar-storage.de.md) | unter der v2-Mindestversion (alt) | Monitoring 10000–10036 · Steuerung 10100–10107 |

**Versionsprüfung:** mit FC 0x03 die Firmware-Version-Register 10062–10063 lesen
(ab 10062, 0x274E, Anzahl 2).  
Antwortet das Gerät, implementiert die Firmware diesen Registerbereich und liegt
ab der v2-Mindestversion — verwende das v2-Protokolldokument.  
Bleibt die Antwort aus, gibt es einen Timeout oder eine Modbus-Exception, ist der
Registerbereich nicht implementiert und die Firmware liegt unter der
v2-Mindestversion — verwende das v1-Protokolldokument.  

Neue Firmware unterstützt zusätzlich **direktes Modbus TCP** über den
Ethernet-Anschluss des All-in-One-Geräts (Port 502): nach dem Verbinden den
dynamischen 8-stelligen hexadezimalen Bestätigungscode von der Gerätedetailseite
der CONOW-App (erneuert alle 120 Sekunden) als uint32 in die Register 9985–9986
schreiben, um die Verifizierung abzuschließen; erst danach sind Lese- und
Schreibzugriffe möglich. Modbus RTU über RS-485 (einschließlich TCP über ein
RS-485-zu-Ethernet-Gateway) benötigt keinen Bestätigungscode.

## Mitwirken

Fehler gefunden oder eine Integrationsanleitung vorschlagen? Öffne ein [Issue](../../issues). Diese Dokumentation wird vom CONOW-Dokumentationsteam gepflegt; Updates werden vom Team vorgenommen. Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Richtlinien.

## Kontakt

Fragen oder Feedback? Erreiche das CONOW-Dokumentationsteam per E-Mail an [support@conow.com](mailto:support@conow.com).

## Lizenz

Dokumente unter [CC BY 4.0](LICENSE-docs) — offizieller Text auf [creativecommons.org](https://creativecommons.org/licenses/by/4.0/), Code unter MIT ([LICENSE](LICENSE)).
