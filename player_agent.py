#!/usr/bin/env python3
"""
Player Agent – steuert einen einzelnen KI-Spieler-Charakter in Discord.
Charaktername wird automatisch vom Discord Bot-Token abgerufen.
"""
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env", override=True)
sys.path.insert(0, str(_BASE_DIR))

from agent.llm import create_adapter
from agent.discord_agent import send_message

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"]
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "hub")
def _load_config() -> dict:
    path = _BASE_DIR / "character" / "config.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

_CONFIG = _load_config()
_DM_BOT_ID = _CONFIG.get("dm_bot_id", "").strip()
DM_USERNAME = ""

if not LLM_MODEL:
    print("ERROR: LLM_MODEL nicht in .env gesetzt", file=sys.stderr)
    sys.exit(1)


def fetch_bot_username() -> str:
    resp = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
    )
    resp.raise_for_status()
    return resp.json()["username"]


def fetch_username_by_id(user_id: str) -> str:
    resp = requests.get(
        f"https://discord.com/api/v10/users/{user_id}",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
    )
    resp.raise_for_status()
    return resp.json()["username"]


CHARAKTER = fetch_bot_username()

if _DM_BOT_ID and not DM_USERNAME:
    try:
        DM_USERNAME = fetch_username_by_id(_DM_BOT_ID).lower()
        print(f"DM-Username ermittelt: {DM_USERNAME}")
    except Exception as e:
        print(f"WARNUNG: DM-Username konnte nicht abgerufen werden: {e}", file=sys.stderr)

_LOCKFILE = Path(f"/tmp/player_agent_{CHARAKTER}.lock")
try:
    if _LOCKFILE.exists():
        old_pid = int(_LOCKFILE.read_text().strip())
        try:
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(1)
        except ProcessLookupError:
            pass
    _LOCKFILE.write_text(str(os.getpid()))
except Exception:
    pass

import atexit
atexit.register(lambda: _LOCKFILE.unlink(missing_ok=True))

CHARACTER_DIR = _BASE_DIR / "character"
_STATE_FILE = _BASE_DIR / f".state_{CHARAKTER}.json"


def load_last_seen_ts() -> str | None:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text()).get("last_seen_ts")
        except Exception:
            pass
    return None


def save_last_seen_ts(ts: str) -> None:
    try:
        _STATE_FILE.write_text(json.dumps({"last_seen_ts": ts}))
    except Exception:
        pass


def fetch_messages(after_ts: str | None) -> list[dict]:
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    all_msgs = []
    last_id = None
    after_epoch = (
        datetime.fromisoformat(after_ts.replace("Z", "+00:00")).timestamp()
        if after_ts else 0
    )
    while True:
        url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
        if last_id:
            url += f"?before={last_id}"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        msgs = resp.json()
        if not msgs:
            break
        for msg in msgs:
            msg_epoch = datetime.fromisoformat(
                msg["timestamp"].replace("Z", "+00:00")
            ).timestamp()
            if msg_epoch > after_epoch:
                all_msgs.append(msg)
            else:
                return list(reversed(all_msgs))
        last_id = msgs[-1]["id"]
    return list(reversed(all_msgs))


def load_personality() -> dict:
    path = CHARACTER_DIR / "personality.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def load_memory() -> str:
    path = CHARACTER_DIR / "memory.md"
    if path.exists():
        return path.read_text().strip()
    return ""


def load_skills() -> list[str]:
    skills_dir = CHARACTER_DIR / "skills"
    if not skills_dir.exists():
        return []
    return [
        f.read_text().strip()
        for f in sorted(skills_dir.glob("*.md"))
        if f.is_file()
    ]


def load_charakterbogen() -> str:
    path = CHARACTER_DIR / "charakterbogen.md"
    if path.exists():
        return path.read_text()
    return ""


def build_system_prompt(personality: dict) -> str:
    bogen = load_charakterbogen()
    memory = load_memory()
    skills = load_skills()
    prinzipien = "\n".join(f"- {p}" for p in personality.get("spielprinzipien", []))
    zusatz = personality.get("llm_system_prompt_zusatz", "")
    situationen = personality.get("situation_antworten", [])
    situation_text = ""
    if situationen:
        lines = []
        for s in situationen:
            frage = s.get("frage", "")
            antwort = s.get("antwort", "")
            if frage and antwort:
                lines.append(f"Frage: {frage}\nDeine Antwort: {antwort}")
        if lines:
            situation_text = "\n\n".join(lines)
    parts = [
        f"Du spielst den Charakter **{CHARAKTER}** in einer D&D 5e Kampagne.",
        "Antworte immer als dieser Charakter – in der ersten Person, auf Deutsch, in 1-3 Sätzen.",
        "Halte dich an die Spielmechanik und reagiere auf die letzte Nachricht des Dungeon Masters.",
        "WICHTIG: Bei Charaktererstellungs- oder Off-Game-Fragen (z.B. Klasse wählen, Attribute verteilen, Ausrüstung) antworte direkt und klar – kein Rollenspiel, keine Umschreibungen. Beantworte die Frage des Dungeon Masters präzise.",
        "Du musst nicht auf jede Nachricht reagieren. Wenn du schweigen willst, antworte mit exakt diesem Text und nichts anderem: [SCHWEIGEN]",
        f"Wenn dein Name fällt, beurteile selbst ob eine Reaktion sinnvoll ist. Schweige wenn: dein Name nur im Narrativ vorkommt ('{CHARAKTER}s Blick', 'er betrachtet {CHARAKTER}'), der DM gerade einen anderen Spieler direkt adressiert (z.B. Charaktererstellung, Einzelfragen an jemand anderen), oder du gerade nichts Sinnvolles beizutragen hast. Reagiere wenn: du direkt angesprochen wirst, eine Frage an dich gerichtet ist, oder eine Aktion dich unmittelbar betrifft. Im Zweifel: [SCHWEIGEN].",
    ]
    if bogen:
        parts.append(f"## Dein Charakterbogen\n{bogen}")
    if prinzipien:
        parts.append(f"## Deine Spielprinzipien\n{prinzipien}")
    if situation_text:
        parts.append(f"## Wie du in Situationen reagierst\n{situation_text}")
    if skills:
        parts.append("## Deine Sonderfähigkeiten\n" + "\n\n---\n\n".join(skills))
    if memory:
        parts.append(f"## Deine Erinnerungen\n{memory}")
    if zusatz:
        parts.append(f"## Zusätzliche Hinweise\n{zusatz}")
    return "\n\n".join(parts)


GROUP_TRIGGERS = [
    "was tut die gruppe", "wer möchte handeln", "was macht ihr",
    "wer seid ihr", "stellt euch vor", "wer bist du", "stell dich vor",
]
REGISTRATION_TRIGGERS = ["alle agenten", "alle spieler", "meldet euch", "registriert euch"]
STOP_TRIGGER = "🛑 **SPIEL GESTOPPT**"


def should_respond(message_content: str, author: str) -> bool:
    lower = message_content.lower()
    # Always pass to LLM when character name is mentioned – LLM decides via [SCHWEIGEN]
    if CHARAKTER.lower() in lower:
        return True
    # Group/registration triggers only from the DM
    is_dm = not DM_USERNAME or author.lower() == DM_USERNAME
    if is_dm:
        if any(trigger in lower for trigger in GROUP_TRIGGERS):
            return True
        if any(trigger in lower for trigger in REGISTRATION_TRIGGERS):
            return True
    return False


def build_messages(recent_msgs: list[dict]) -> list[dict]:
    result = []
    for msg in recent_msgs[-20:]:
        author = (msg.get("author") or {}).get("username", "")
        content = msg.get("content", "").strip()
        if not content:
            continue
        role = "assistant" if author.lower() == CHARAKTER.lower() else "user"
        result.append({"role": role, "content": f"{author}: {content}"})
    return result


def run():
    try:
        adapter = create_adapter(LLM_MODEL, provider=LLM_PROVIDER)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Player-Bot gestartet: {CHARAKTER} → {LLM_MODEL} [{LLM_PROVIDER}]")
    print(f"Polling alle {POLL_INTERVAL}s auf Channel {DISCORD_CHANNEL_ID}\n")

    last_seen_ts = load_last_seen_ts()
    while True:
        try:
            new_msgs = fetch_messages(last_seen_ts)
            if new_msgs:
                last_seen_ts = new_msgs[-1]["timestamp"]
                save_last_seen_ts(last_seen_ts)

                # Stop signal check
                for msg in new_msgs:
                    if STOP_TRIGGER in msg.get("content", ""):
                        print(f"[{CHARAKTER}] Stop-Signal empfangen. Beende...")
                        sys.exit(0)

                # Determine if any new message should trigger a reaction.
                # We take the LAST triggering message but pass ALL new messages as
                # context so the LLM sees the full picture and can use [SCHWEIGEN].
                trigger_msg = None
                for msg in new_msgs:
                    author = (msg.get("author") or {}).get("username", "")
                    content = msg.get("content", "")
                    if CHARAKTER.lower() == author.lower():
                        continue
                    if should_respond(content, author):
                        trigger_msg = msg

                if trigger_msg:
                    trigger_content = trigger_msg.get("content", "")
                    personality = load_personality()
                    system_prompt = build_system_prompt(personality)
                    messages = build_messages(new_msgs)
                    print(f"[{CHARAKTER}] prüft Reaktion auf: {trigger_content[:60]}...")
                    try:
                        response = adapter.complete(system_prompt, messages)
                        if "schweigen" in response.lower():
                            print(f"[{CHARAKTER}] → schweigt. Trigger: {trigger_content[:80]!r}")
                        else:
                            send_message(DISCORD_TOKEN, DISCORD_CHANNEL_ID, response)
                            print(f"[{CHARAKTER}] → {response[:80]}...")
                    except Exception as e:
                        print(f"[{CHARAKTER}] Fehler: {e}", file=sys.stderr)
        except Exception as e:
            msg = str(e)
            if "429" in msg:
                print("Rate limit – warte 30s...", file=sys.stderr)
                time.sleep(30)
                continue
            print(f"Polling-Fehler: {e}", file=sys.stderr)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
