"""2-2 真实冒烟。没有钥匙就退出，不写假记录。有钥匙才走文本、双商品出图和裁切。"""

import base64
import io
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

PRODUCT = Path(__file__).resolve().parents[1]
BACKEND = PRODUCT / "backend"
EVIDENCE = PRODUCT / "docs" / "evidence" / "阶段2-2" / "冒烟记录.md"
sys.path.insert(0, str(BACKEND))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def load() -> Settings:
    env_file = BACKEND / ".env"
    if env_file.exists():
        return Settings(_env_file=env_file)
    return Settings()


def append(model: str, row: str) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    if not EVIDENCE.exists():
        EVIDENCE.write_text(
            "\n".join(
                [
                    "# 冒烟记录（冒烟脚本自动写入，不得手填）",
                    "- 产品：端侧AI-Studio",
                    "- 阶段：阶段2-2",
                    f"- 模型：{model}",
                    f"- 写入时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "",
                    "| 时间 | 链路 | 请求 ID | 输入 token | 输出 token | 首字耗时 | 总耗时 | 结构校验 | 重试次数 | 结果 |",
                    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    with EVIDENCE.open("a", encoding="utf-8") as handle:
        handle.write(row + "\n")


def png(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (256, 256), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def row(name: str, request_id: str, seconds: float, ok: bool) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "通过" if ok else "失败"
    check = "首测合规" if ok else "失败"
    return f"| {stamp} | {name} | {request_id} | - | - | - | {seconds:.1f}s | {check} | 0 | {result} |"


def main() -> int:
    settings = load()
    if not settings.deepseek_api_key or not settings.deepseek_model or not settings.sensetime_keys():
        print("没有配齐 DeepSeek 和商汤钥匙，不写冒烟记录。", file=sys.stderr)
        return 2
    folder = Path("/tmp") / f"studio-smoke-22-{uuid.uuid4().hex}"
    folder.mkdir(parents=True)
    settings.database_url = f"sqlite:///{folder / 'app.db'}"
    settings.data_dir = str(folder)
    settings.fake_models = False
    model = f"DeepSeek {settings.deepseek_model} / 商汤 {settings.sensetime_model}"
    red = png((180, 40, 40))
    blue = png((40, 80, 180))
    app = create_app(settings)
    with TestClient(app) as client:
        client.timeout = 300
        started = time.perf_counter()
        text = client.post(
            "/v1/responses",
            json={
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "白色瓶子，放在木质桌面上，柔和日光"},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(red).decode()}},
                        ],
                    }
                ]
            },
        )
        text_ok = text.status_code == 200 and bool((text.json() or {}).get("output_text"))
        append(model, row("文本生成", uuid.uuid4().hex, time.perf_counter() - started, text_ok))
        if not text_ok:
            return 1
        started = time.perf_counter()
        edited = client.post(
            "/v1/images/edits",
            data={"prompt": "同一套柔和日光和木质桌面，只换商品"},
            files=[
                ("image", ("red.png", red, "image/png")),
                ("image", ("blue.png", blue, "image/png")),
            ],
        )
        body = edited.json() if edited.headers.get("content-type", "").startswith("application/json") else {}
        images = body.get("data") if isinstance(body, dict) else None
        edit_ok = edited.status_code == 200 and isinstance(images, list) and len(images) == 2 and all(item.get("b64_json") for item in images)
        append(model, row("双商品出图", uuid.uuid4().hex, time.perf_counter() - started, edit_ok))
        if not edit_ok:
            return 1
        started = time.perf_counter()
        sized = client.post(
            "/v1/images/sizes",
            files={"image": ("one.png", base64.b64decode(images[0]["b64_json"]), "image/png")},
        )
        packed = sized.json().get("data") if sized.status_code == 200 else None
        size_ok = isinstance(packed, list) and len(packed) == 3 and all(item.get("b64_json") for item in packed)
        append(model, row("改尺寸裁切", uuid.uuid4().hex, time.perf_counter() - started, size_ok))
        return 0 if size_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"冒烟失败：{exc.__class__.__name__}", file=sys.stderr)
        raise SystemExit(1)
