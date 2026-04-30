from __future__ import annotations

import base64
from io import BytesIO
import re
from textwrap import wrap
from urllib.parse import quote, urlencode
import html

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Tablegame Card Generator")

CARD_WIDTH = 1400
CARD_HEIGHT = 900
PAGE_TITLE = "Tablegame Card Generator"
PHASE_LABELS = [
    "Передвижение",
    "Атака",
    "Строительство",
    "Изучение",
]


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


def _draw_chevron(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], active: bool
) -> None:
    left, top, right, bottom = box
    mid_y = (top + bottom) / 2
    color = (250, 208, 97) if active else (92, 103, 130)
    outline = (255, 239, 199) if active else (132, 144, 172)
    points = [
        (left, top + 6),
        (right - 20, top + 6),
        (right, mid_y),
        (right - 20, bottom - 6),
        (left, bottom - 6),
        (left + 20, mid_y),
    ]
    draw.polygon(points, fill=color, outline=outline)


def _draw_phase_label(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, active: bool
) -> None:
    left, top, right, bottom = box
    font = _font(22, bold=True)
    fill = (245, 248, 255) if active else (165, 177, 204)
    label_width = _text_width(text, font)
    draw.text(
        ((left + right - label_width) / 2, bottom + 10), text, fill=fill, font=font
    )


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
    canvas = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (12, 18, 36, 255))
    draw = ImageDraw.Draw(canvas)

    for y in range(CARD_HEIGHT):
        blend = y / max(1, CARD_HEIGHT - 1)
        red = int(18 + (34 - 18) * blend)
        green = int(28 + (56 - 28) * blend)
        blue = int(52 + (96 - 52) * blend)
        draw.line((0, y, CARD_WIDTH, y), fill=(red, green, blue, 255))

    margin = 50
    panel = (margin, margin, CARD_WIDTH - margin, CARD_HEIGHT - margin)
    shadow = (panel[0] + 10, panel[1] + 14, panel[2] + 10, panel[3] + 14)
    draw.rounded_rectangle(shadow, radius=44, fill=(0, 0, 0, 90))
    draw.rounded_rectangle(
        panel, radius=44, fill=(21, 30, 54), outline=(120, 140, 188), width=4
    )

    icon_box = (90, 90, 330, 330)
    icon_image = _load_icon_image(icon_data)
    if icon_image is None:
        _make_placeholder_icon(draw, icon_box, icon_label)
    else:
        _paste_icon(canvas, icon_image, icon_box)

    title_font = _font(58, bold=True)
    creature_font = _font(34)
    phase_font = _font(28, bold=True)
    body_font = _font(34)

    draw.text((370, 96), title, font=title_font, fill=(245, 248, 255))
    draw.text((370, 172), creature, font=creature_font, fill=(170, 188, 220))

    phase_y = 240
    arrow_start_x = 370
    arrow_width = 145
    arrow_gap = 18
    for index, active in enumerate(phases):
        left = arrow_start_x + index * (arrow_width + arrow_gap)
        arrow_box = (left, phase_y, left + arrow_width, phase_y + 68)
        _draw_chevron(draw, arrow_box, active)
        _draw_phase_label(draw, arrow_box, PHASE_LABELS[index], active)

    body_top = 420
    body_left = 90
    body_width = CARD_WIDTH - 2 * body_left
    draw.rounded_rectangle(
        (body_left, body_top, CARD_WIDTH - body_left, CARD_HEIGHT - 100),
        radius=32,
        fill=(30, 42, 74),
    )
    draw.text(
        (body_left + 34, body_top + 28),
        "Описание",
        font=phase_font,
        fill=(198, 214, 242),
    )

    wrapped = _wrap_text(
        description.strip() or "Здесь будет описание способности.",
        body_font,
        body_width - 68,
    )
    line_height = _text_height(body_font) + 12
    text_y = body_top + 84
    for line in wrapped:
        draw.text((body_left + 34, text_y), line, font=body_font, fill=(242, 245, 252))
        text_y += line_height

    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def _card_preview_html(request: Request) -> str:
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

    query = _query_string(title, creature, description, icon_label, phases)
    image_url = f"/cards/ability.png?{query}"
    download_filename = _download_filename(title)

    def checked(index: int) -> str:
        return "checked" if phases[index] else ""

    def encoded(value: str) -> str:
        return html.escape(value, quote=True)

    description_value = encoded(description)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{encoded(PAGE_TITLE)}</title>
    <style>
        :root {{
            color-scheme: dark;
            --bg: #0a1224;
            --panel: rgba(18, 27, 50, 0.86);
            --panel-strong: #162038;
            --text: #eef3ff;
            --muted: #9eb0d2;
            --line: rgba(160, 182, 230, 0.22);
            --accent: #f5c85a;
            --accent-strong: #ffe39a;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background:
                radial-gradient(circle at top left, rgba(89, 115, 174, 0.32), transparent 34%),
                radial-gradient(circle at top right, rgba(219, 166, 71, 0.18), transparent 28%),
                linear-gradient(180deg, #07101f 0%, #0a1224 100%);
            color: var(--text);
            min-height: 100vh;
        }}
        .shell {{
            width: min(1440px, calc(100% - 32px));
            margin: 0 auto;
            padding: 28px 0 36px;
            display: grid;
            gap: 20px;
            grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
            align-items: start;
        }}
        header {{
            grid-column: 1 / -1;
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 16px;
            padding: 8px 4px 0;
        }}
        h1 {{ margin: 0; font-size: 34px; line-height: 1; letter-spacing: -0.04em; }}
        .subtitle {{ color: var(--muted); margin-top: 8px; max-width: 58ch; }}
        .card, .preview {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 24px;
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.34);
            backdrop-filter: blur(18px);
        }}
        .card {{ padding: 22px; }}
        .field {{ display: grid; gap: 8px; margin-bottom: 16px; }}
        .field label, .group-title {{ font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }}
        input[type="text"], textarea {{
            width: 100%;
            border: 1px solid rgba(150, 171, 213, 0.24);
            border-radius: 16px;
            background: rgba(7, 13, 26, 0.68);
            color: var(--text);
            padding: 14px 16px;
            font: inherit;
            outline: none;
        }}
        textarea {{ min-height: 160px; resize: vertical; line-height: 1.5; }}
        input:focus, textarea:focus {{ border-color: rgba(245, 200, 90, 0.7); box-shadow: 0 0 0 3px rgba(245, 200, 90, 0.14); }}
                input[type="file"] {{ display: none; }}
                .dropzone {{
                        border: 1px dashed rgba(150, 171, 213, 0.38);
                        border-radius: 18px;
                        background: rgba(7, 13, 26, 0.5);
                        padding: 16px;
                        display: grid;
                        gap: 8px;
                        cursor: pointer;
                        transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
                }}
                .dropzone:hover, .dropzone.is-dragover {{
                        border-color: rgba(245, 200, 90, 0.8);
                        background: rgba(17, 24, 44, 0.74);
                        transform: translateY(-1px);
                }}
                .dropzone-title {{ font-weight: 700; color: var(--text); }}
                .dropzone-status {{ font-size: 14px; color: var(--muted); line-height: 1.4; }}
        .phases {{ display: grid; gap: 10px; }}
        .phase-row {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .phase-chip {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 11px 14px;
            border-radius: 999px;
            border: 1px solid rgba(150, 171, 213, 0.24);
            background: rgba(7, 13, 26, 0.48);
            cursor: pointer;
            user-select: none;
        }}
        .phase-chip input {{ accent-color: var(--accent); }}
        .actions {{ display: flex; gap: 12px; margin-top: 8px; flex-wrap: wrap; }}
        .button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            border-radius: 14px;
            padding: 12px 16px;
            border: 1px solid transparent;
            font-weight: 700;
        }}
        .button.primary {{ background: linear-gradient(135deg, #f6cf68, #e8a94a); color: #0d1220; }}
        .button.secondary {{ background: rgba(7, 13, 26, 0.55); color: var(--text); border-color: rgba(150, 171, 213, 0.24); }}
        .preview {{ padding: 18px; }}
        .preview img {{ width: 100%; height: auto; display: block; border-radius: 18px; border: 1px solid rgba(150, 171, 213, 0.2); background: #091122; }}
        .preview-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 14px; }}
        .preview-head h2 {{ margin: 0; font-size: 18px; }}
        .hint {{ color: var(--muted); font-size: 14px; }}
        @media (max-width: 1080px) {{
            .shell {{ grid-template-columns: 1fr; }}
            header {{ flex-direction: column; align-items: start; }}
        }}
    </style>
</head>
<body>
    <main class="shell">
        <header>
            <div>
                <h1>{encoded(PAGE_TITLE)}</h1>
                <div class="subtitle">Простой FastAPI-интерфейс для первой карты: редактируешь поля слева, получаешь PNG справа.</div>
            </div>
            <div class="hint">Левый верхний угол отведён под DDS-иконку-заглушку, фазы показаны стрелками, текст занимает нижнюю часть карты.</div>
        </header>

                <section class="card">
                        <form id="card-form" method="get" action="/">
                <div class="field">
                    <label for="title">Название карты</label>
                    <input id="title" name="title" type="text" value="{encoded(title)}" />
                </div>
                <div class="field">
                    <label for="creature">Название существа</label>
                    <input id="creature" name="creature" type="text" value="{encoded(creature)}" />
                </div>
                <div class="field">
                    <label for="icon">Подпись иконки</label>
                    <input id="icon" name="icon" type="text" value="{encoded(icon_label)}" />
                </div>
                                <div class="field">
                                        <label for="icon-file">DDS иконка</label>
                                        <input id="icon-file" type="file" accept=".dds,image/vnd.ms-dds" />
                                        <input id="icon-data" name="icon_data" type="hidden" value="{encoded(icon_data)}" />
                                        <div id="icon-dropzone" class="dropzone" tabindex="0" role="button" aria-label="Загрузить DDS иконку">
                                                <div class="dropzone-title">Перетащи DDS файл сюда или нажми, чтобы выбрать</div>
                                                <div id="icon-status" class="dropzone-status">Иконка не загружена, используется заглушка.</div>
                                        </div>
                                </div>
                <div class="field">
                    <label for="description">Описание</label>
                    <textarea id="description" name="description">{description_value}</textarea>
                </div>
                <div class="field phases">
                    <div class="group-title">Фазы</div>
                    <div class="phase-row">
                                                <label class="phase-chip"><input type="checkbox" name="phase1" {checked(0)} /> {PHASE_LABELS[0]}</label>
                                                <label class="phase-chip"><input type="checkbox" name="phase2" {checked(1)} /> {PHASE_LABELS[1]}</label>
                                                <label class="phase-chip"><input type="checkbox" name="phase3" {checked(2)} /> {PHASE_LABELS[2]}</label>
                                                <label class="phase-chip"><input type="checkbox" name="phase4" {checked(3)} /> {PHASE_LABELS[3]}</label>
                    </div>
                </div>
                <div class="actions">
                    <button class="button primary" type="submit">Обновить превью</button>
                    <a class="button secondary" href="{image_url}" download="{encoded(download_filename)}">Скачать PNG</a>
                </div>
            </form>
        </section>

        <section class="preview">
            <div class="preview-head">
                <h2>Превью карты</h2>
                <div class="hint">/cards/ability.png</div>
            </div>
                        <img id="card-preview" src="{image_url}" alt="Ability card preview" />
        </section>
    </main>
        <script>
                (() => {{
                        const form = document.getElementById('card-form');
                        const preview = document.getElementById('card-preview');
                        const downloadLink = document.querySelector('.button.secondary');
                        const iconFileInput = document.getElementById('icon-file');
                        const iconDataInput = document.getElementById('icon-data');
                        const iconDropzone = document.getElementById('icon-dropzone');
                        const iconStatus = document.getElementById('icon-status');
                        let timeoutId = null;

                        const sanitizeFilename = (value) => {{
                                return `${{(value || 'card').replace(/[^A-Za-z0-9А-Яа-яЁё._-]+/g, '_').replace(/^[._-]+|[._-]+$/g, '') || 'card'}}.png`;
                        }};

                        const refreshPreview = () => {{
                                const formData = new FormData(form);
                                const params = new URLSearchParams();

                                params.set('title', formData.get('title')?.toString() ?? '');
                                params.set('creature', formData.get('creature')?.toString() ?? '');
                                params.set('description', formData.get('description')?.toString() ?? '');
                                params.set('icon', formData.get('icon')?.toString() ?? '');
                                params.set('icon_data', iconDataInput.value || '');

                                for (const phase of ['phase1', 'phase2', 'phase3', 'phase4']) {{
                                        params.set(phase, form.querySelector(`[name="${{phase}}"]`)?.checked ? '1' : '0');
                                }}

                                const url = `/cards/ability.png?${{params.toString()}}`;
                                const titleValue = (formData.get('title')?.toString() ?? '').trim();
                                const filename = sanitizeFilename(titleValue);
                                preview.src = url;
                                downloadLink.href = url;
                                downloadLink.setAttribute('download', filename);
                        }};

                        const scheduleRefresh = () => {{
                                window.clearTimeout(timeoutId);
                                timeoutId = window.setTimeout(refreshPreview, 120);
                        }};

                        const updateIconStatus = (message) => {{
                                iconStatus.textContent = message;
                        }};

                        const loadIconFile = (file) => {{
                                if (!file) {{
                                        iconDataInput.value = '';
                                        updateIconStatus('Иконка не загружена, используется заглушка.');
                                        scheduleRefresh();
                                        return;
                                }}

                                const reader = new FileReader();
                                reader.onload = () => {{
                                        iconDataInput.value = String(reader.result || '');
                                        updateIconStatus(`Загружен файл: ${{file.name}}`);
                                        scheduleRefresh();
                                }};
                                reader.onerror = () => {{
                                        iconDataInput.value = '';
                                        updateIconStatus('Не удалось прочитать DDS файл.');
                                }};
                                reader.readAsDataURL(file);
                        }};

                        form.addEventListener('input', scheduleRefresh);
                        form.addEventListener('change', scheduleRefresh);
                        iconDropzone.addEventListener('click', () => iconFileInput.click());
                        iconDropzone.addEventListener('keydown', (event) => {{
                                if (event.key === 'Enter' || event.key === ' ') {{
                                        event.preventDefault();
                                        iconFileInput.click();
                                }}
                        }});
                        iconFileInput.addEventListener('change', () => {{
                                loadIconFile(iconFileInput.files?.[0] ?? null);
                        }});
                        iconDropzone.addEventListener('dragover', (event) => {{
                                event.preventDefault();
                                iconDropzone.classList.add('is-dragover');
                        }});
                        iconDropzone.addEventListener('dragleave', () => {{
                                iconDropzone.classList.remove('is-dragover');
                        }});
                        iconDropzone.addEventListener('drop', (event) => {{
                                event.preventDefault();
                                iconDropzone.classList.remove('is-dragover');
                                const file = event.dataTransfer?.files?.[0] ?? null;
                                loadIconFile(file);
                        }});
                }})();
        </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return HTMLResponse(_card_preview_html(request))


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
