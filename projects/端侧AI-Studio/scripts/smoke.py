"""真实冒烟。没有钥匙就退出，不写假记录。有钥匙才走一遍生成卡和出图。"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

PRODUCT = Path(__file__).resolve().parents[1]
BACKEND = PRODUCT / "backend"
EVIDENCE = PRODUCT / "docs" / "evidence" / "阶段2-1" / "冒烟记录.md"
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
                    "- 阶段：阶段2-1",
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


def main() -> int:
    settings = load()
    if not settings.deepseek_api_key or not settings.deepseek_model or not settings.sensetime_keys():
        print("没有配齐 DeepSeek 和商汤钥匙，不写冒烟记录。", file=sys.stderr)
        return 2
    folder = Path(os.environ.get("TMPDIR", "/tmp")) / f"studio-smoke-{uuid.uuid4().hex}"
    folder.mkdir(parents=True)
    settings.database_url = f"sqlite:///{folder / 'app.db'}"
    settings.data_dir = str(folder)
    settings.fake_models = False
    started = time.perf_counter()
    app = create_app(settings)
    import base64

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    model = f"DeepSeek {settings.deepseek_model} / 商汤 {settings.sensetime_model}"
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"invite_code": settings.invite_code})
        login.raise_for_status()
        work = client.post("/api/v1/works", json={"title": "冒烟"}).json()
        uploaded = client.post("/api/v1/uploads", files={"file": ("dot.png", png, "image/png")}).json()
        created = client.post(
            "/api/v1/jobs",
            json={
                "work_id": work["id"],
                "upload_asset_id": uploaded["id"],
                "image_type": "场景图",
                "user_text": "木质桌面，柔和日光",
            },
        ).json()
        job = _wait(client, created["id"], {"card_ready", "failed"})
        card_ok = job["status"] == "card_ready"
        append(model, _row("生成卡", created["id"], time.perf_counter() - started, "通过" if card_ok else "失败"))
        if not card_ok:
            return 1
        client.post(f"/api/v1/jobs/{created['id']}/confirm").raise_for_status()
        image_started = time.perf_counter()
        done = _wait(client, created["id"], {"succeeded", "failed"})
        append(model, _row("出图", created["id"], time.perf_counter() - image_started, "通过" if done["status"] == "succeeded" else "失败"))
        return 0 if done["status"] == "succeeded" else 1


def _wait(client: TestClient, job_id: str, targets: set[str]) -> dict:
    for _ in range(90):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in targets:
            return job
        time.sleep(2)
    return {"status": "failed"}


def _row(name: str, request_id: str, seconds: float, result: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"| {stamp} | {name} | {request_id} | - | - | - | {seconds:.1f}s | {'首测合规' if result == '通过' else '失败'} | 0 | {result} |"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"冒烟失败：{exc.__class__.__name__}", file=sys.stderr)
        raise SystemExit(1)
