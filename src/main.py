from __future__ import annotations

import base64
from io import BytesIO
import re
from pathlib import Path
from textwrap import wrap
from urllib.parse import quote, urlencode
import html

from playwright.sync_api import sync_playwright
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Tablegame Card Generator")

CARD_WIDTH = 900
CARD_HEIGHT = 1400
PAGE_TITLE = "Tablegame Card Generator"
PHASE_LABELS = [
    "Передвижение",
    "Атака",
    "Строительство",
    "Изучение",
]
PHASE_ICON_FILES = [
    "move-alt-svgrepo-com.svg",
    "sword-fill-svgrepo-com.svg",
    "hammer-fill-svgrepo-com.svg",
    "education-book-learn-school-library-svgrepo-com.svg",
]
PHASE_ICON_KINDS = ["move", "attack", "hammer", "book"]
PHASE_ICON_DIR = Path(__file__).resolve().parent / "public" / "icons"
PHASE_ICON_SIZE = 112


def _font(
    size: int, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "Arial.ttf"]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _query_value(request: Request, key: str, default: str = "") -> str:
    value = request.query_params.get(key)
    return default if value is None or value == "" else value


def _phase_flags(request: Request) -> list[bool]:
    phase_keys = [f"phase{index}" for index in range(1, 5)]
    if any(key in request.query_params for key in phase_keys):
        return [
            request.query_params.get(key) in {"1", "true", "on", "yes"}
            for key in phase_keys
        ]
    return [True, True, True, True]


def _query_string(
    title: str, creature: str, description: str, icon_label: str, phases: list[bool]
) -> str:
    params: list[tuple[str, str]] = [
        ("title", title),
        ("creature", creature),
        ("description", description),
        ("icon", icon_label),
    ]
    for index, active in enumerate(phases, start=1):
        if active:
            params.append((f"phase{index}", "1"))
    return urlencode(params)


def _download_filename(title: str) -> str:
    safe_title = re.sub(r"[^A-Za-z0-9А-Яа-яЁё._-]+", "_", title.strip())
    safe_title = safe_title.strip("._-") or "card"
    return f"{safe_title}.png"


def _download_header_value(title: str) -> str:
    ascii_title = re.sub(r"[^A-Za-z0-9._-]+", "_", title.strip())
    ascii_title = ascii_title.strip("._-") or "card"
    filename = _download_filename(title)
    return f"attachment; filename=\"{ascii_title}.png\"; filename*=UTF-8''{quote(filename)}"


def _icon_data_bytes(icon_data: str) -> bytes | None:
    if not icon_data:
        return None

    payload = icon_data.split(",", 1)[1] if "," in icon_data else icon_data
    try:
        return base64.b64decode(payload, validate=False)
    except (ValueError, TypeError):
        return None


def _load_icon_image(icon_data: str) -> Image.Image | None:
    icon_bytes = _icon_data_bytes(icon_data)
    if not icon_bytes:
        return None

    try:
        with Image.open(BytesIO(icon_bytes)) as icon_image:
            return icon_image.convert("RGBA")
    except Exception:
        return None


def _text_width(text: str, font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _text_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Ag")
    return bbox[3] - bbox[1]


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        if not paragraph.strip():
            lines.append("")
            continue

        current = ""
        for word in paragraph.split():
            candidate = word if not current else f"{current} {word}"
            if _text_width(candidate, font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                if _text_width(word, font) <= max_width:
                    current = word
                else:
                    approx_width = max(
                        4, max_width // max(1, getattr(font, "size", 16) // 2)
                    )
                    chunks = wrap(word, width=approx_width)
                    if chunks:
                        lines.extend(chunks[:-1])
                        current = chunks[-1]
                    else:
                        current = word
        if current:
            lines.append(current)
    return lines or [""]


def _svg_markup(file_name: str) -> str:
    svg_text = (PHASE_ICON_DIR / file_name).read_text(encoding="utf-8")
    svg_text = re.sub(r"<\?xml.*?\?>", "", svg_text, count=1, flags=re.DOTALL)
    return svg_text.strip()


def _svg_phase_icon(index: int, active: bool) -> str:
    color = "#fadc61" if active else "#0b0f18"
    kind = PHASE_ICON_KINDS[index]
    return (
        f'<span class="phase-icon phase-icon-{kind}" style="color:{color};">'
        f"{_svg_markup(PHASE_ICON_FILES[index])}</span>"
    )


def _icon_data_uri(icon_data: str) -> str | None:
    icon_image = _load_icon_image(icon_data)
    if icon_image is None:
        return None

    output = BytesIO()
    icon_image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_ability_card_html(
    title: str,
    creature: str,
    description: str,
    icon_label: str,
    phases: list[bool],
    icon_data: str = "",
) -> str:
    def encoded(value: str) -> str:
        return html.escape(value, quote=True)

    icon_uri = _icon_data_uri(icon_data)
    phase_items = []
    for index, active in enumerate(phases):
        phase_items.append(
            f"<div class='phase-cell'>{_svg_phase_icon(index, active)}</div>"
        )

    phase_html = "".join(phase_items)
    icon_html = (
        f"<img class='card-icon-image' src='{encoded(icon_uri)}' alt='Icon' />"
        if icon_uri
        else f"<div class='card-icon-placeholder'>{encoded(icon_label[:3] or 'DDS')}</div>"
    )

    safe_description = encoded(description.strip() or "Здесь будет описание способности.")
    safe_description = safe_description.replace("\n", "<br />")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8" />
    <style>
        * {{ box-sizing: border-box; }}
        html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; }}
        body {{
            display: grid;
            place-items: center;
            background:
                radial-gradient(circle at top left, rgba(89, 115, 174, 0.25), transparent 34%),
                radial-gradient(circle at top right, rgba(219, 166, 71, 0.18), transparent 28%),
                linear-gradient(180deg, #07101f 0%, #0a1224 100%);
            color: #eef3ff;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        .card {{
            width: 900px;
            height: 1400px;
            position: relative;
            overflow: hidden;
            border-radius: 44px;
            background:
                linear-gradient(180deg, rgba(18, 28, 56, 0.32), rgba(16, 24, 45, 0.1)),
                linear-gradient(180deg, #11182d 0%, #1e2a4a 100%);
            box-shadow: 0 36px 120px rgba(0, 0, 0, 0.45);
            border: 1px solid rgba(167, 186, 224, 0.34);
            padding: 48px;
        }}
        .card::before {{
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle at 20% 0%, rgba(252, 230, 145, 0.16), transparent 26%),
                radial-gradient(circle at 80% 8%, rgba(123, 152, 220, 0.2), transparent 24%);
            pointer-events: none;
        }}
        .panel-shadow {{
            position: absolute;
            inset: 48px;
            border-radius: 44px;
            box-shadow: inset 0 0 0 1px rgba(167, 186, 224, 0.18), 0 14px 0 rgba(0, 0, 0, 0.12);
            pointer-events: none;
        }}
        .card-content {{ position: relative; z-index: 1; height: 100%; display: grid; grid-template-rows: auto auto auto 1fr; }}
        .card-content {{ display: flex; flex-direction: column; }}
        .card-icon-wrap {{ display: flex; justify-content: center; margin-top: 28px; }}
        .card-icon {{
            width: 250px;
            height: 250px;
            border-radius: 28px;
            background: rgba(34, 46, 72, 0.98);
            border: 5px solid rgba(116, 136, 180, 1);
            display: grid;
            place-items: center;
            overflow: hidden;
        }}
        .card-icon-image {{ width: 100%; height: 100%; object-fit: contain; padding: 14px; }}
        .card-icon-placeholder {{
            font-size: 42px;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: #eff5ff;
        }}
        .title {{ margin-top: 42px; text-align: center; font-size: 54px; line-height: 1.05; font-weight: 700; color: #f5f8ff; }}
        .creature {{ margin-top: 12px; text-align: center; font-size: 32px; color: #aabbdc; }}
        .phases {{ margin-top: 56px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; align-items: start; }}
        .phase-cell {{ display: flex; justify-content: center; align-items: flex-start; min-height: 96px; }}
        .phase-icon {{ display: inline-flex; width: 96px; height: 96px; }}
        .phase-icon svg {{ width: 100%; height: 100%; display: block; }}
        .phase-icon-move svg path {{ fill: none; stroke: currentColor; }}
        .phase-icon-attack svg path {{ fill: currentColor; stroke: none; }}
        .phase-icon-attack svg path[fill="none"] {{ fill: none; }}
        .phase-icon-hammer svg path {{ fill: currentColor; stroke: none; }}
        .phase-icon-book svg path {{ stroke: none; }}
        .phase-icon-book svg path:first-of-type {{ fill: none; }}
        .phase-icon-book svg path:last-of-type {{ fill: currentColor; }}
        .body {{
            margin-top: 28px;
            flex: 1;
            display: flex;
            flex-direction: column;
            border-radius: 32px;
            background: rgba(30, 42, 74, 0.98);
            padding: 30px 34px 34px;
            min-height: 0;
        }}
        .body h2 {{ margin: 0 0 18px; font-size: 26px; color: #c6d6f2; }}
        .body p {{ margin: 0; font-size: 32px; line-height: 1.45; color: #f2f5fc; white-space: normal; word-break: break-word; flex: 1; }}
    </style>
</head>
<body>
    <section class="card" id="card">
        <div class="panel-shadow"></div>
        <div class="card-content">
            <div class="card-icon-wrap"><div class="card-icon">{icon_html}</div></div>
            <div class="title">{encoded(title)}</div>
            <div class="creature">{encoded(creature)}</div>
            <div class="phases">{phase_html}</div>
            <div class="body">
                <h2>Описание</h2>
                <p>{safe_description}</p>
            </div>
        </div>
    </section>
</body>
</html>"""


def _render_html_to_png(html_content: str) -> bytes:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = browser.new_context(
                viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
                device_scale_factor=2,
            )
            try:
                page = context.new_page()
                page.set_content(html_content, wait_until="load")
                card = page.locator("#card")
                card.wait_for(state="visible")
                return card.screenshot(type="png")
            finally:
                context.close()
        finally:
            browser.close()


def _make_placeholder_icon(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(
        box, radius=28, fill=(34, 46, 72), outline=(116, 136, 180), width=5
    )
    inner = (left + 14, top + 14, right - 14, bottom - 14)
    draw.rounded_rectangle(inner, radius=22, fill=(52, 68, 104))

    font = _font(42, bold=True)
    text = (label[:3] or "DDS").upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(
        ((left + right - text_width) / 2, (top + bottom - text_height) / 2 - 8),
        text,
        fill=(239, 245, 255),
        font=font,
    )


def _paste_icon(
    canvas: Image.Image, icon_image: Image.Image, box: tuple[int, int, int, int]
) -> None:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    frame = Image.new("RGBA", (width, height), (34, 46, 72, 255))
    frame_draw = ImageDraw.Draw(frame)
    frame_draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=28,
        fill=(34, 46, 72),
        outline=(116, 136, 180),
        width=5,
    )

    icon = icon_image.copy()
    icon.thumbnail((width - 28, height - 28), Image.Resampling.LANCZOS)
    offset_x = (width - icon.width) // 2
    offset_y = (height - icon.height) // 2
    frame.alpha_composite(icon, (offset_x, offset_y))
    canvas.alpha_composite(frame, (left, top))


def generate_ability_card_png(
    title: str,
    creature: str,
    description: str,
    icon_label: str,
    phases: list[bool],
    icon_data: str = "",
) -> bytes:
    html_content = _render_ability_card_html(
        title, creature, description, icon_label, phases, icon_data
    )
    return _render_html_to_png(html_content)


import os
from fastapi.staticfiles import StaticFiles

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/cards/ability.png")
def ability_card_png(request: Request) -> Response:
    title = _query_value(request, "title", "Карта способности")
    creature = _query_value(request, "creature", "Существо")
    description = _query_value(
        request,
        "description",
        "Короткое описание способности.\n\nЗдесь можно собрать текст под конкретную карту.",
    )
    icon_label = _query_value(request, "icon", "DDS")
    icon_data = _query_value(request, "icon_data", "")
    phases = _phase_flags(request)
    return Response(
        generate_ability_card_png(
            title, creature, description, icon_label, phases, icon_data
        ),
        media_type="image/png",
        headers={"Content-Disposition": _download_header_value(title)},
    )


def main() -> None:
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
