import os
import time

import requests


DISCORD_MESSAGE_LIMIT = 1900
DISCORD_RATE_LIMIT_DELAY_SECONDS = 0.8


def _split_message(message: str, max_length: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    if max_length <= 0:
        raise ValueError("max_length must be greater than 0.")

    chunks: list[str] = []
    remaining = message.strip()

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_index = remaining.rfind("\n\n", 0, max_length)

        if split_index == -1:
            split_index = remaining.rfind("\n", 0, max_length)

        if split_index == -1:
            split_index = max_length

        chunk = remaining[:split_index].strip()
        chunks.append(chunk)
        remaining = remaining[split_index:].strip()

    return chunks


def _delivery_failure_message(error: requests.RequestException) -> str:
    if error.response is not None:
        return f"Discord delivery failed with HTTP status {error.response.status_code}"

    if isinstance(error, requests.Timeout):
        return "Discord delivery failed: timeout"

    if isinstance(error, requests.ConnectionError):
        return "Discord delivery failed: connection error"

    return "Discord delivery failed: request error"


def send_to_discord(message: str) -> None:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL is missing. Add it to your .env file."
        )

    chunks = _split_message(message)

    for index, chunk in enumerate(chunks, start=1):
        if len(chunks) > 1:
            content = f"**Part {index}/{len(chunks)}**\n\n{chunk}"
        else:
            content = chunk

        try:
            response = requests.post(
                webhook_url,
                json={"content": content},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise RuntimeError(_delivery_failure_message(error)) from None

        if index < len(chunks):
            time.sleep(DISCORD_RATE_LIMIT_DELAY_SECONDS)
