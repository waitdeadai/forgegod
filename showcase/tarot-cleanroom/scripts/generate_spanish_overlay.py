from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content" / "tarot"
OUTPUT_PATH = ROOT / "content" / "locales" / "es-deck.json"
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7-highspeed")
API_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1/chat/completions")
API_KEY = os.environ.get("MINIMAX_API_KEY")
BATCH_SIZE = int(os.environ.get("MINIMAX_BATCH_SIZE", "6"))
RETRY_LIMIT = 3


@dataclass
class Card:
    id: str
    name: str
    keywords: list[str]
    uprightMeaning: str
    reversedMeaning: str
    symbolism: list[str]


def load_cards() -> list[Card]:
    files = [
        "major-arcana.json",
        "minor-cups.json",
        "minor-swords.json",
        "minor-pentacles.json",
        "minor-wands.json",
    ]
    cards: list[Card] = []
    for file_name in files:
        raw = json.loads((CONTENT_DIR / file_name).read_text(encoding="utf-8"))
        for item in raw:
            cards.append(
                Card(
                    id=item["id"],
                    name=item["name"],
                    keywords=item.get("keywords", []),
                    uprightMeaning=item["uprightMeaning"],
                    reversedMeaning=item["reversedMeaning"],
                    symbolism=item.get("symbolism", []),
                )
            )
    return cards


def chunked(items: list[Card], size: int) -> list[list[Card]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_prompt(cards: list[Card]) -> str:
    return json.dumps(
        {
            "task": "translate_tarot_cards",
            "target_locale": "es-AR",
            "tone": "ritual, elegant, precise, natural Latin American Spanish",
            "requirements": [
                "preserve every id exactly",
                "translate name, keywords, uprightMeaning, reversedMeaning, symbolism",
                "return only JSON",
                "do not wrap in markdown fences",
                "keep tarot naming conventional in Spanish where a standard form exists",
            ],
            "cards": [card.__dict__ for card in cards],
            "response_schema": {
                "cards": [
                    {
                        "id": "string",
                        "name": "string",
                        "keywords": ["string"],
                        "uprightMeaning": "string",
                        "reversedMeaning": "string",
                        "symbolism": ["string"],
                    }
                ]
            },
        },
        ensure_ascii=False,
    )


def extract_json(text: str) -> dict[str, Any]:
    fenced = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
      return json.loads(fenced.group(1))

    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError("No JSON object found in model response")


def request_batch(cards: list[Card]) -> dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is required")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a translation engine for a production tarot application. "
                    "Return only valid JSON."
                ),
            },
            {"role": "user", "content": build_prompt(cards)},
        ],
        "temperature": 0.15,
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    with urlopen(request, timeout=180) as response:
        body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return extract_json(content)


def validate_batch(source: list[Card], translated: dict[str, Any]) -> dict[str, Any]:
    items = translated.get("cards")
    if not isinstance(items, list):
        raise ValueError("Translated payload must contain a cards array")

    source_ids = [card.id for card in source]
    translated_ids = [item.get("id") for item in items]

    if source_ids != translated_ids:
        raise ValueError(f"Card ids do not match source batch: {source_ids} != {translated_ids}")

    by_id: dict[str, Any] = {}
    for item in items:
        if not all(
            key in item
            for key in ("id", "name", "keywords", "uprightMeaning", "reversedMeaning", "symbolism")
        ):
            raise ValueError(f"Translated item missing required keys: {item}")
        by_id[item["id"]] = {
            "name": item["name"],
            "keywords": item["keywords"],
            "uprightMeaning": item["uprightMeaning"],
            "reversedMeaning": item["reversedMeaning"],
            "symbolism": item["symbolism"],
        }
    return by_id


def main() -> int:
    cards = load_cards()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    batches = chunked(cards, BATCH_SIZE)
    overlay: dict[str, Any] = {}

    for index, batch in enumerate(batches, start=1):
        attempt = 0
        while True:
            attempt += 1
            try:
                result = request_batch(batch)
                overlay.update(validate_batch(batch, result))
                print(f"batch {index}/{len(batches)} ok")
                break
            except (ValueError, HTTPError, RuntimeError, json.JSONDecodeError) as exc:
                if attempt >= RETRY_LIMIT:
                    print(f"batch {index} failed after {attempt} attempts: {exc}", file=sys.stderr)
                    return 1
                print(f"batch {index} retry {attempt}: {exc}", file=sys.stderr)
                time.sleep(2.5 * attempt)

    OUTPUT_PATH.write_text(
        json.dumps(overlay, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(overlay)} cards to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
