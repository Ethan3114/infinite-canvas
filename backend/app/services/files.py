"""上传校验。只认真实图片字节，文件名由系统生成，避免路径穿越。"""

import base64
import io
import uuid
from pathlib import Path

from PIL import Image

PNG = b"\x89PNG\r\n\x1a\n"
JPEG = b"\xff\xd8\xff"
WEBP = b"RIFF"


class FileRejected(Exception):
    def __init__(self, message: str):
        self.message = message


def sniff_image(raw: bytes, limit: int) -> str:
    if len(raw) == 0:
        raise FileRejected("文件是空的")
    if len(raw) > limit:
        raise FileRejected("图片超过 10 MB")
    if raw.startswith(PNG):
        return "image/png"
    if raw.startswith(JPEG):
        return "image/jpeg"
    if raw.startswith(WEBP) and raw[8:12] == b"WEBP":
        return "image/webp"
    raise FileRejected("只接收 jpg、png、webp")


def save_bytes(data_dir: Path, owner_id: str, raw: bytes, mime: str) -> str:
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    folder = data_dir / "files" / owner_id
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    path = folder / name
    path.write_bytes(raw)
    return f"files/{owner_id}/{name}"


def read_asset(data_dir: Path, relpath: str) -> Path:
    root = (data_dir / "files").resolve()
    path = (data_dir / relpath).resolve()
    if root not in path.parents and path != root:
        raise FileRejected("文件路径不对")
    if not path.is_file():
        raise FileRejected("文件不在了")
    return path


def ensure_min_size(raw: bytes) -> tuple[bytes, str]:
    """商汤要求宽高至少 256。太小的图先放大，不改画面内容。"""
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    width, height = image.size
    if width < 256 or height < 256:
        scale = max(256 / width, 256 / height)
        image = image.resize((max(256, round(width * scale)), max(256, round(height * scale))), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), "image/png"


def pack_sizes(raw: bytes) -> list[bytes]:
    """按固定比例居中裁切。不调用模型。"""
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    packed = []
    for ratio_w, ratio_h in ((1, 1), (3, 4), (16, 9)):
        target_w = 1024
        target_h = round(1024 * ratio_h / ratio_w)
        scale = max(target_w / image.width, target_h / image.height)
        resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
        left = max(0, (resized.width - target_w) // 2)
        top = max(0, (resized.height - target_h) // 2)
        cropped = resized.crop((left, top, left + target_w, top + target_h))
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        packed.append(buffer.getvalue())
    return packed


def data_url(mime: str, raw: bytes) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"
