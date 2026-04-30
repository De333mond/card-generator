# Web application for generating PNG tablegame cards

Small FastAPI app for the first card type: ability cards.

## What it does

- Serves a simple editor page with a live preview.
- Renders the card as a PNG from the same inputs.
- Uses a plain FastAPI + Pillow stack, with a minimal Dockerfile.

## Run locally

```bash
uv sync
uv run uvicorn src.main:app --reload
```

Open `http://127.0.0.1:8000` in the browser.

## Card layout

- Top-left placeholder icon area for the DDS asset.
- Card title and creature name on the right.
- Four phase arrows that can be switched on or off.
- Description area fills the rest of the card.

## Docker

```bash
docker build -t tablegame-card-generator .
docker run --rm -p 8000:8000 tablegame-card-generator
```