# zutritt-manager
Custom Home-Assistant-Integration mit eigener Sidebar-GUI zur Verwaltung von PIN- und RFID-Zutritten. Benutzer, Gruppen (z. B. Chef/Mitarbeiter/Lieferant), Türimpulse, LED/Beeper-Feedback und Events für Automationen – komplett lokal über ESPHome.

# Zutritt Manager (WG26 / ESPHome)

Custom Integration für **Home Assistant** zur Verwaltung von **PIN- und RFID-Zutritten** über ESPHome-Keypads (z. B. WG26).  
Die Integration stellt eine **eigene Sidebar-Oberfläche** bereit (ähnlich Zigbee2MQTT), in der Benutzer, Gruppen und Berechtigungen zentral verwaltet werden.

Alles läuft **lokal** in Home Assistant – keine Cloud, keine externen Dienste.

---

## Funktionen

- Sidebar-Panel in Home Assistant (Admin-Bereich)
- Benutzerverwaltung (anlegen / löschen / aktivieren)
- PIN-Zutritt (PINs werden **gehasht** gespeichert)
- RFID-Zutritt (UID-basiert)
- Gruppenlogik (z. B. `chef`, `mitarbeiter`, `lieferant`, `familie`)
- Gruppen-Events für Automationen
- Türöffner-Impulse (Relais / ESPHome-Switch)
- LED- & Beeper-Feedback (OK / Fehler)
- Klingel-/Taster-Unterstützung
- Logbook-Einträge für Zutritte
- Mehrere Leser/Quellen unterstützt

---

## Architektur

**ESPHome → Home Assistant → Zutritt Manager**

ESPHome sendet Events:
- `esphome.zutritt_input` (PIN oder RFID)
- `esphome.halle_taster` (Klingel)

Die Integration:
- prüft Benutzer + Gruppen
- entscheidet über **granted / denied**
- schaltet Türöffner & Feedback
- feuert eigene Events für Automationen

---

## Installation (HACS)

1. **HACS → Integrationen**
2. Drei Punkte → **Custom repositories**
3. Repository-URL eintragen
4. Kategorie: **Integration**
5. Installieren
6. **Home Assistant neu starten**

Nach dem Neustart erscheint links in der Sidebar **„Zutritt“** (nur Admin).

---

## Manuelle Installation

```text
config/custom_components/zutritt_manager/
