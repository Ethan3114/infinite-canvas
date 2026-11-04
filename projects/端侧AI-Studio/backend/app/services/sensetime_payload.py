"""商汤图片编辑请求。一次只出一张，不让对方再改写我们已经确认的提示词。"""

from app.services.files import data_url


def build_edit_payload(model: str, prompt: str, mime: str, raw: bytes) -> dict:
    return {
        "model": model,
        "images": [{"image_url": data_url(mime, raw)}],
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "watermark": False,
        "prompt_extend": False,
        "response_format": "b64_json",
        "output_format": "png",
    }
