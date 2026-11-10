"""商汤图片请求。一次只出一张。尺寸必须符合商汤规则，否则退回 2K 方图。"""

from app.services.files import data_url

PURPOSE_LABELS = {"main": "主图", "scene": "场景图", "product": "商品图"}


def normalize_sensetime_size(value: object, allow_auto: bool = False) -> str:
    text = str(value or "").strip().lower()
    if text == "auto":
        return "auto" if allow_auto else "2048x2048"
    parts = text.split("x")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        width, height = int(parts[0]), int(parts[1])
        short, long = min(width, height), max(width, height)
        legal = (
            width % 32 == 0
            and height % 32 == 0
            and 512 <= width <= 4096
            and 512 <= height <= 4096
            and short > 0
            and long / short <= 3
        )
        if legal:
            return f"{width}x{height}"
    return "2048x2048"


def build_edit_payload(
    model: str,
    prompt: str,
    mime: str,
    raw: bytes,
    size: str = "2048x2048",
    watermark: bool = False,
    prompt_extend: bool = False,
    extras: list[tuple[bytes, str]] | None = None,
) -> dict:
    images = [{"image_url": data_url(mime, raw)}]
    for extra_raw, extra_mime in (extras or [])[:4]:
        images.append({"image_url": data_url(extra_mime, extra_raw)})
    return {
        "model": model,
        "images": images,
        "prompt": prompt,
        "n": 1,
        "size": normalize_sensetime_size(size, allow_auto=True),
        "watermark": watermark,
        "prompt_extend": prompt_extend,
        "response_format": "b64_json",
        "output_format": "png",
    }
