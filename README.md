# agent-zeta – Mistralyn

DnD4AI Player Agent – verkörpert **Mistralyn**.

## Setup

```bash
git clone --recurse-submodules https://github.com/dnd4ai/agent-zeta.git
cd agent-zeta
cp .env.example .env
```

Öffne `.env` und trage die nötigen Werte ein.

```bash
pip install -r requirements.txt
python player_agent.py
```

## Limitationen

- **Memory (read-only):** Die Erinnerungsdatei (`character/memory.md`) wird beim Start geladen, aber während der Laufzeit nicht fortgeschrieben. Neue Erlebnisse werden nach einem Neustart nicht erinnert, außer die Datei wird manuell aktualisiert.
- **Kontext-Fenster:** Beim Antworten fließen maximal die letzten 20 Discord-Nachrichten des Kanals in den Kontext ein. Ältere Gesprächsverläufe sind dem Agenten nicht bekannt.
- **Skills (eager loading):** Alle Skill-Dateien aus `character/skills/` werden beim Start vollständig in den System-Prompt geladen, unabhängig davon, ob sie gerade relevant sind. Das erhöht den Token-Verbrauch pro Anfrage.
- **Kein Bildverständnis:** Der Agent verarbeitet nur Text. Teilt der Dungeon Master eine Karte, ein Monsterbild oder eine Szene als **Bild**, nimmt der Agent das nicht wahr und kann nicht darauf reagieren.
