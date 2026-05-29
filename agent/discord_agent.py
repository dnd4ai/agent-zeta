import requests


def send_message(token: str, channel_id: str, content: str) -> None:
    """Postet eine Nachricht als Bot mit eigenem Token. Splittet bei >2000 Zeichen."""
    chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
    for chunk in chunks:
        resp = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            json={"content": chunk},
            headers={
                "Authorization": f"Bot {token}",
                "User-Agent": "DiscordBot (https://example.com, 1.0)",
            },
        )
        if not resp.ok:
            raise RuntimeError(f"Discord API error {resp.status_code}: {resp.text}")
