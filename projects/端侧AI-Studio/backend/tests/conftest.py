"""每个测试用自己的临时数据库，不碰真实钥匙，也不联网。"""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

MIN_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class FakeDeepSeek:
    def __init__(self, bad_first: bool = False):
        self.calls = 0
        self.bad_first = bad_first
        self.saw_image = False
        self.kind = "ecommerce"
        self.task = ""

    def complete(self, raw: bytes, mime: str, user_text: str, image_type: str) -> str:
        self.saw_image = bool(raw)
        self.calls += 1
        if self.bad_first and self.calls == 1:
            return "请看这里，不是 JSON"
        return (
            '{"product_appearance":"白色瓶子","scene_and_light":"木质桌面，柔和日光",'
            '"style":"干净商业摄影","must_not":"多余文字",'
            '"prompt":"白色瓶子放在木质桌面，柔和日光，干净商业摄影"}'
        )

    def complete_text(self, user_text: str, image_type: str) -> str:
        return self.complete(b"", "", user_text, image_type)

    def complete_drama(self, task: str, system: str, raw: bytes | None, mime: str, user_text: str) -> str:
        self.kind = "drama"
        self.task = task
        self.saw_image = bool(raw)
        samples = {
            "summary": '{"text":"女孩去店里等明天"}',
            "character": '{"text":"黑发女孩，红围巾"}',
            "prop": '{"text":"红色金属钥匙"}',
            "scene": '{"text":"暖色小店，窗边座位"}',
            "plot": '{"shots":[{"no":1,"text":"女孩推开店门"},{"no":2,"text":"女孩坐下"}]}',
            "shot": '{"no":1,"text":"女孩推门，红围巾，暖色小店"}',
        }
        return samples[task]


class FakeSense:
    def __init__(self):
        self.keys: list[str] = []
        self.prompts: list[str] = []

    def generate(self, api_key: str, prompt: str, raw: bytes, mime: str) -> bytes:
        self.keys.append(api_key)
        self.prompts.append(prompt)
        return MIN_PNG

    def generate_text(self, api_key: str, prompt: str, size: str) -> bytes:
        self.keys.append(api_key)
        self.prompts.append(prompt)
        return MIN_PNG


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(
        invite_code="studio-demo",
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        data_dir=str(tmp_path),
        fake_models=True,
        sensetime_api_keys="k1,k2,k3",
        deepseek_api_key="fake-for-test",
        deepseek_model="fake-vision",
    )


@pytest.fixture
def clients(tmp_settings: Settings):
    deepseek = FakeDeepSeek()
    sense = FakeSense()
    app = create_app(tmp_settings, card_client=deepseek, image_client=sense)
    return TestClient(app), deepseek, sense, tmp_settings


def login(client: TestClient, code: str = "studio-demo"):
    response = client.post("/api/v1/auth/login", json={"invite_code": code})
    assert response.status_code == 200
    return response
