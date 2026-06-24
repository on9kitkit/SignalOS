import os

import requests


def send_to_discord(message: str) -> None:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL is missing. Add it to your .env file."
        )

    response = requests.post(
        webhook_url,
        json={"content": message[:1900]},
        timeout=15,
    )

    response.raise_for_status()