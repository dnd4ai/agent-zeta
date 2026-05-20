#!/usr/bin/env python3
"""
Player Agent – steuert einen einzelnen KI-Spieler-Charakter in Discord.
Charakter wird über CHARACTER_NAME in .env gesetzt.
"""
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_LOCKFILE = Path("/tmp/player_agent.lock")
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

from dnd4ai_core.llm import create_adapter
from dnd4ai_core.discord_agent import send_message

BASE_DIR = Path(__file__).resolve().parents[1]
CHARACTER_DIR = BASE_DIR / "character"

CHARAKTER = os.environ.get("CHARACTER_NAME", "")
if not CHARAKTER:
    print("ERROR: CHARACTER_NAME nicht in .env gesetzt", file=sys.stderr)
    sys.exit(1)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"]
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "hub")

if not LLM_MODEL:
    print("ERROR: LLM_MODEL nicht in .env gesetzt", file=sys.stderr)
    sys.exit(1)


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


GROUP_TRIGGERS = ["was tut die gruppe", "wer möchte handeln", "was macht ihr"]


def should_respond(agent_name: str, message_content: str) -> bool:
    lower = message_content.lower()
    if any(trigger in lower for trigger in GROUP_TRIGGERS):
        return True
    return CHARAKTER.lower() in lower or agent_name.lower() in lower


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
    agent_name = os.environ.get("DISCORD_BOT_NAME", CHARAKTER)
    try:
        adapter = create_adapter(LLM_MODEL, provider=LLM_PROVIDER)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Player-Bot gestartet: {CHARAKTER} → {LLM_MODEL} [{LLM_PROVIDER}]")
    print(f"Polling alle {POLL_INTERVAL}s auf Channel {DISCORD_CHANNEL_ID}\n")

    last_seen_ts = datetime.now(timezone.utc).isoformat()
    while True:
        try:
            new_msgs = fetch_messages(last_seen_ts)
            if new_msgs:
                last_seen_ts = new_msgs[-1]["timestamp"]
                for msg in new_msgs:
                    content = msg.get("content", "")
                    author = (msg.get("author") or {}).get("username", "")
                    if agent_name.lower() == author.lower():
                        continue
                    if content.startswith(f"**[{CHARAKTER.capitalize()}]**"):
                        continue
                    if not should_respond(agent_name, content):
                        continue
                    personality = load_personality()
                    system_prompt = build_system_prompt(personality)
                    messages = build_messages(new_msgs)
                    messages.append({"role": "user", "content": f"{author}: {content}"})
                    print(f"[{CHARAKTER}] antwortet auf: {content[:60]}...")
                    try:
                        response = adapter.complete(system_prompt, messages)
                        send_message(DISCORD_TOKEN, DISCORD_CHANNEL_ID, f"**[{CHARAKTER.capitalize()}]** {response}")
                        print(f"[{CHARAKTER}] → {response[:80]}...")
                    except Exception as e:
                        print(f"[{CHARAKTER}] Fehler: {e}", file=sys.stderr)
                    time.sleep(1)
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
