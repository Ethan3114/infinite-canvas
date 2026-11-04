"""2-1 的离线测试：登录、隔离、文件、生成卡、确认后才出图、钥匙轮换。"""

import json

from fastapi.testclient import TestClient

from app.services.cards import parse_card
from app.services.sensetime_payload import build_edit_payload
from tests.conftest import MIN_PNG, FakeDeepSeek, login


def test_bad_invite(clients):
    client, _, _, _ = clients
    response = client.post("/api/v1/auth/login", json={"invite_code": "nope"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "bad_invite"


def test_login_me_and_logout(clients):
    client, _, _, _ = clients
    login(client)
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_reject_gif_and_oversize(clients, tmp_settings):
    client, _, _, _ = clients
    login(client)
    gif = client.post("/api/v1/uploads", files={"file": ("a.gif", b"GIF89a", "image/gif")})
    assert gif.status_code == 400
    assert gif.json()["error"]["code"] == "bad_file"
    tmp_settings.max_upload_bytes = 20
    huge = client.post("/api/v1/uploads", files={"file": ("a.png", MIN_PNG + b"x" * 30, "image/png")})
    assert huge.status_code == 400


def test_other_user_cannot_read_job(clients):
    client, _, _, settings = clients
    login(client)
    work = client.post("/api/v1/works", json={"title": "我的"}).json()
    uploaded = client.post("/api/v1/uploads", files={"file": ("a.png", MIN_PNG, "image/png")}).json()
    created = client.post(
        "/api/v1/jobs",
        json={"work_id": work["id"], "upload_asset_id": uploaded["id"], "image_type": "场景图", "user_text": "桌面日光"},
    )
    job_id = created.json()["id"]
    other = TestClient(client.app)
    login(other)
    assert other.get(f"/api/v1/jobs/{job_id}").status_code == 404
    assert settings.fake_models is True


def test_confirm_waits_for_card_then_image(clients):
    client, deepseek, sense, _ = clients
    login(client)
    work = client.post("/api/v1/works", json={"title": "场景图"}).json()
    uploaded = client.post("/api/v1/uploads", files={"file": ("a.png", MIN_PNG, "image/png")}).json()
    created = client.post(
        "/api/v1/jobs",
        json={
            "work_id": work["id"],
            "upload_asset_id": uploaded["id"],
            "image_type": "场景图",
            "user_text": "放到木质桌面，柔和日光",
        },
    )
    assert created.status_code == 202
    job_id = created.json()["id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "card_ready"
    assert job["card"]["product_appearance"] == "白色瓶子"
    confirmed = client.post(f"/api/v1/jobs/{job_id}/confirm")
    assert confirmed.status_code == 202
    done = client.get(f"/api/v1/jobs/{job_id}").json()
    assert done["status"] == "succeeded"
    assert sense.keys == ["k1"]
    assert deepseek.calls == 1
    image = client.get(f"/api/v1/assets/{done['result_asset_id']}")
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")


def test_card_parse_retries_once(tmp_settings):
    from app.main import create_app

    deepseek = FakeDeepSeek(bad_first=True)
    sense = __import__("tests.conftest", fromlist=["FakeSense"]).FakeSense()
    app = create_app(tmp_settings, card_client=deepseek, image_client=sense)
    client = TestClient(app)
    login(client)
    work = client.post("/api/v1/works", json={"title": "重试"}).json()
    uploaded = client.post("/api/v1/uploads", files={"file": ("a.png", MIN_PNG, "image/png")}).json()
    created = client.post(
        "/api/v1/jobs",
        json={"work_id": work["id"], "upload_asset_id": uploaded["id"], "image_type": "主图", "user_text": "白底"},
    )
    job = client.get(f"/api/v1/jobs/{created.json()['id']}").json()
    assert job["status"] == "card_ready"
    assert deepseek.calls == 2


def test_three_keys_rotate(tmp_path, tmp_settings):
    from app.main import create_app
    from tests.conftest import FakeSense

    sense = FakeSense()
    app = create_app(tmp_settings, card_client=FakeDeepSeek(), image_client=sense)
    client = TestClient(app)
    login(client)
    for index in range(3):
        work = client.post("/api/v1/works", json={"title": f"图{index}"}).json()
        uploaded = client.post("/api/v1/uploads", files={"file": ("a.png", MIN_PNG, "image/png")}).json()
        created = client.post(
            "/api/v1/jobs",
            json={"work_id": work["id"], "upload_asset_id": uploaded["id"], "image_type": "主图", "user_text": "白底主图"},
        )
        job_id = created.json()["id"]
        assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "card_ready"
        assert client.post(f"/api/v1/jobs/{job_id}/confirm").status_code == 202
    assert sense.keys == ["k1", "k2", "k3"]


def test_second_job_waits_while_lock_held(tmp_settings):
    from app.main import create_app
    from app.models import Job, ProviderState
    from app.services.runner import run_image
    from tests.conftest import FakeSense

    sense = FakeSense()
    app = create_app(tmp_settings, card_client=FakeDeepSeek(), image_client=sense)
    db = app.state.factory()
    job = Job(
        id="job-wait",
        owner_id="owner",
        work_id="work",
        status="queued",
        image_type="主图",
        user_text="白底",
        card_json="{}",
        upload_asset_id="asset",
    )
    db.add(job)
    state = db.get(ProviderState, "sensetime")
    state.lock_job_id = "someone-else"
    db.commit()
    db.close()
    run_image(app.state.factory, "job-wait", tmp_settings, sense)
    db = app.state.factory()
    assert db.get(Job, "job-wait").status == "queued"
    assert sense.keys == []
    db.close()


def test_work_survives_new_process(tmp_settings):
    from app.main import create_app

    first = TestClient(create_app(tmp_settings, card_client=FakeDeepSeek(), image_client=__import__("tests.conftest", fromlist=["FakeSense"]).FakeSense()))
    login(first)
    created = first.post("/api/v1/works", json={"title": "还在"}).json()
    second = TestClient(create_app(tmp_settings, card_client=FakeDeepSeek(), image_client=__import__("tests.conftest", fromlist=["FakeSense"]).FakeSense()))
    second.cookies.update(first.cookies)
    again = second.get(f"/api/v1/works/{created['id']}")
    assert again.status_code == 200
    assert again.json()["title"] == "还在"


def test_edit_payload_does_not_rewrite_prompt():
    payload = build_edit_payload("sensenova-u1.5-lite", "白色瓶子", "image/png", MIN_PNG)
    assert payload["n"] == 1
    assert payload["watermark"] is False
    assert payload["prompt_extend"] is False
    assert payload["images"][0]["image_url"].startswith("data:image/png;base64,")


def test_parse_card_accepts_fenced_json():
    text = '```json\n{"product_appearance":"瓶","scene_and_light":"日光","style":"干净","must_not":"水印","prompt":"瓶子在日光下"}\n```'
    card = parse_card(text, "场景图")
    assert card.prompt.startswith("瓶子")


def test_canvas_gateway_returns_image(clients):
    client, _, sense, _ = clients
    response = client.post("/v1/images/generations", json={"model": "sensenova-u1.5-lite", "prompt": "木质桌面", "n": 1, "size": "1024x1024"})
    assert response.status_code == 200
    assert response.json()["data"][0]["b64_json"]
    assert sense.keys == ["k1"]
    assert sense.prompts[0] == "木质桌面"


def test_two_skus_are_generated_serially_and_sizes_skip_model(clients):
    client, _, sense, _ = clients
    png = MIN_PNG
    files = [
        ("image", ("a.png", png, "image/png")),
        ("image", ("b.png", png, "image/png")),
    ]
    response = client.post("/v1/images/edits", data={"prompt": "同一套日光风格", "n": "1"}, files=files)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
    assert sense.keys == ["k1", "k2"]
    before = len(sense.keys)
    sized = client.post("/v1/images/sizes", files={"image": ("a.png", png, "image/png")})
    assert sized.status_code == 200
    assert len(sized.json()["data"]) == 3
    assert len(sense.keys) == before


def test_text_generation_uses_deepseek_vision(clients):
    client, deepseek, _, _ = clients
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    response = client.post(
        "/v1/responses",
        json={
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "写成场景图提示词"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png}"}},
                    ],
                }
            ]
        },
    )
    assert response.status_code == 200
    assert "白色瓶子" in response.json()["output_text"]
    assert deepseek.saw_image is True
    assert deepseek.kind == "ecommerce"


def test_drama_tasks_stay_separate(clients):
    client, deepseek, _, _ = clients
    character = client.post("/v1/responses", json={"workflow": "drama", "task": "character", "input": "写角色"})
    character_text = character.json()["output_text"]
    assert character.status_code == 200
    assert character_text.startswith("角色画像")
    assert "镜头" not in character_text
    plot = client.post("/v1/responses", json={"workflow": "drama", "task": "plot", "input": "写分镜"})
    plot_text = plot.json()["output_text"]
    assert plot.status_code == 200
    assert "分镜情节" in plot_text and "镜头 1" in plot_text
    assert "角色画像" not in plot_text
    assert deepseek.task == "plot"


def test_plot_accepts_visual_field():
    from app.services.storyboard import format_drama, parse_drama

    parsed = parse_drama("plot", '{"shots":[{"no":"1","visual":"女孩推门"},{"description":"女孩坐下"}]}')
    text = format_drama("plot", parsed)
    assert "镜头 1｜女孩推门" in text
    assert "镜头 2｜女孩坐下" in text


def test_video_frames_do_not_call_ant_without_a_real_key(clients):
    client, _, _, settings = clients
    assert settings.fake_models is True
    created = client.post("/v1/videos/frames", json={"prompt": "过渡", "first_frame": "data:image/png;base64,YQ==", "last_frame": "data:image/png;base64,Yg=="})
    assert created.status_code == 200
    assert created.json()["task_id"] == "fake-video"
    status = client.get("/v1/videos/frames/fake-video")
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"


def test_concat_two_videos(clients, tmp_path):
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        return
    clips = []
    for index, color in enumerate(("red", "blue")):
        path = tmp_path / f"{index}.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=320x240:d=0.4", "-pix_fmt", "yuv420p", str(path)], check=True, capture_output=True)
        clips.append(path.read_bytes())
    client, _, _, _ = clients
    response = client.post("/v1/videos/concat", files=[("videos", ("a.mp4", clips[0], "video/mp4")), ("videos", ("b.mp4", clips[1], "video/mp4"))])
    assert response.status_code == 200
    assert response.content[:8] == b"\x00\x00\x00\x18ftyp" or response.content[4:8] == b"ftyp"
    assert len(response.content) > len(clips[0])


def test_invalid_body_has_error_shape(clients):
    client, _, _, _ = clients
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 400
    assert set(response.json()["error"]) == {"code", "message"}
    assert "Traceback" not in json.dumps(response.json())
