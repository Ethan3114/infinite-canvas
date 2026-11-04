"""DeepSeek 写生成卡，商汤按确认后的卡出图。失败最多再试一次，不把钥匙写进错误信息。"""

import base64
import re

import httpx

from app.core.config import Settings
from app.services.cards import system_prompt
from app.services.files import data_url
from app.services.sensetime_payload import build_edit_payload


class ModelError(Exception):
    def __init__(self, message: str):
        self.message = message


def _post(url: str, headers: dict, payload: dict, timeout: float) -> httpx.Response:
    last_error = "网络没有连上"
    for _ in range(2):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except httpx.HTTPError:
            last_error = "网络超时或中断"
            continue
        if response.status_code >= 500:
            last_error = "模型服务暂时不可用"
            continue
        return response
    raise ModelError(last_error)


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(self, raw: bytes, mime: str, user_text: str, image_type: str) -> str:
        if not self.settings.deepseek_api_key or not self.settings.deepseek_model:
            raise ModelError("还没有配置 DeepSeek 钥匙或识图模型名")
        url = self.settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.deepseek_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"图类型：{image_type}\n用户的话：{user_text}"},
                        {"type": "image_url", "image_url": {"url": data_url(mime, raw)}},
                    ],
                },
            ],
        }
        response = _post(
            url,
            {"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
            payload,
            self.settings.deepseek_timeout,
        )
        if response.status_code >= 400:
            raise ModelError("DeepSeek 没有写成生成卡")
        body = response.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("DeepSeek 没有返回文字") from exc

    def complete_text(self, user_text: str, image_type: str) -> str:
        if not self.settings.deepseek_api_key or not self.settings.deepseek_model:
            raise ModelError("还没有配置 DeepSeek 钥匙或识图模型名")
        url = self.settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.deepseek_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": f"图类型：{image_type}\n用户的话：{user_text}\n没有参考图，按文字写生成卡。"},
            ],
        }
        response = _post(
            url,
            {"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
            payload,
            self.settings.deepseek_timeout,
        )
        if response.status_code >= 400:
            raise ModelError("DeepSeek 没有写成生成卡")
        body = response.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("DeepSeek 没有返回文字") from exc

    def complete_drama(self, task: str, system: str, raw: bytes | None, mime: str, user_text: str) -> str:
        image = None
        if raw:
            image = [
                {"type": "text", "text": user_text or "根据已有内容完成本步"},
                {"type": "image_url", "image_url": {"url": data_url(mime, raw)}},
            ]
        return self._drama_call(system, user_text, image)

    def _drama_call(self, system: str, user_text: str, image_content: list | None) -> str:
        if not self.settings.deepseek_api_key or not self.settings.deepseek_model:
            raise ModelError("还没有配置 DeepSeek 钥匙或识图模型名")
        content: str | list = image_content or f"{user_text}\n没有参考图，只完成本步。"
        payload = {
            "model": self.settings.deepseek_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        }
        response = _post(
            self.settings.deepseek_base_url.rstrip("/") + "/chat/completions",
            {"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
            payload,
            self.settings.deepseek_timeout,
        )
        if response.status_code >= 400:
            raise ModelError("DeepSeek 没有写成分镜")
        body = response.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("DeepSeek 没有返回文字") from exc


class SenseTimeClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, api_key: str, prompt: str, raw: bytes, mime: str) -> bytes:
        if not api_key:
            raise ModelError("还没有配置商汤钥匙")
        url = self.settings.sensetime_base_url.rstrip("/") + "/images/edits"
        payload = build_edit_payload(self.settings.sensetime_model, prompt, mime, raw)
        response = _post(
            url,
            {"Authorization": f"Bearer {api_key}"},
            payload,
            self.settings.sensetime_timeout,
        )
        if response.status_code >= 400:
            raise ModelError(_api_message(response, "商汤没有出图"))
        body = response.json()
        try:
            item = body["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("商汤没有返回图片") from exc
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            downloaded = httpx.get(item["url"], timeout=self.settings.sensetime_timeout)
            if downloaded.status_code >= 400:
                raise ModelError("商汤的图片下载失败")
            return downloaded.content
        raise ModelError("商汤没有返回图片")

    def generate_text(self, api_key: str, prompt: str, size: str) -> bytes:
        if not api_key:
            raise ModelError("还没有配置商汤钥匙")
        url = self.settings.sensetime_base_url.rstrip("/") + "/images/generations"
        payload = {
            "model": self.settings.sensetime_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "watermark": False,
            "prompt_extend": False,
            "response_format": "b64_json",
            "output_format": "png",
        }
        response = _post(
            url,
            {"Authorization": f"Bearer {api_key}"},
            payload,
            self.settings.sensetime_timeout,
        )
        if response.status_code >= 400:
            raise ModelError(_api_message(response, "商汤没有出图"))
        body = response.json()
        try:
            item = body["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("商汤没有返回图片") from exc
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            downloaded = httpx.get(item["url"], timeout=self.settings.sensetime_timeout)
            if downloaded.status_code >= 400:
                raise ModelError("商汤的图片下载失败")
            return downloaded.content
        raise ModelError("商汤没有返回图片")


def _api_message(response: httpx.Response, fallback: str) -> str:
    try:
        message = str(response.json()["error"]["message"])
    except Exception:
        message = fallback
    message = re.sub(r"sk-[A-Za-z0-9_-]{6,}", "", message)
    if "width and height" in message:
        return "商品图太小或比例不对。宽高需要在 256 到 4096 之间。"
    return (message or fallback)[:300]


class AntVideoClient:
    """蚂蚁图生视频。只用视频模型，一次一条，前一镜做首帧，后一镜做尾帧。"""

    def __init__(self, settings: Settings):
        self.settings = settings

    def create_clip(self, prompt: str, first_url: str, last_url: str) -> str:
        if not self.settings.ant_api_key:
            raise ModelError("还没有配置蚂蚁视频钥匙。请填到 backend/.env 的 ANT_API_KEY。这一步还没扣费。720P、3 秒一段大约 270 点。")
        url = self.settings.ant_base_url.rstrip("/") + "/api/v1/services/aigc/video-generation/video-synthesis"
        payload = {
            "model": self.settings.ant_video_model or "wan2.7-i2v",
            "input": {
                "prompt": (prompt or "让画面从首帧自然过渡到尾帧")[:500],
                "media": [
                    {"type": "first_frame", "url": first_url},
                    {"type": "last_frame", "url": last_url},
                ],
            },
            "parameters": {"resolution": "720P", "duration": 3, "prompt_extend": False, "watermark": False},
        }
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {self.settings.ant_api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            },
            json=payload,
            timeout=60,
        )
        if response.status_code >= 400:
            raise ModelError("蚂蚁没有开始生成视频")
        body = response.json()
        task_id = (body.get("output") or {}).get("task_id") or body.get("task_id") or body.get("id")
        if not task_id:
            raise ModelError("蚂蚁没有返回视频任务")
        return str(task_id)

    def read_clip(self, task_id: str) -> dict:
        if not self.settings.ant_api_key:
            raise ModelError("还没有配置蚂蚁视频钥匙")
        url = self.settings.ant_base_url.rstrip("/") + f"/api/v1/tasks/{task_id}"
        response = httpx.get(url, headers={"Authorization": f"Bearer {self.settings.ant_api_key}"}, timeout=30)
        if response.status_code >= 400:
            raise ModelError("蚂蚁视频状态查询失败")
        body = response.json()
        output = body.get("output") or body
        status = str(output.get("task_status") or output.get("status") or "").upper()
        video_url = output.get("video_url") or ""
        results = output.get("results") or []
        if not video_url and results and isinstance(results[0], dict):
            video_url = results[0].get("url") or ""
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise ModelError("蚂蚁视频没有生成成功")
        if status in {"SUCCEEDED", "SUCCESS"}:
            return {"status": "succeeded", "url": video_url}
        return {"status": "pending", "url": ""}


def concat_mp4(parts: list[bytes]) -> bytes:
    """把多段 mp4 按给定顺序接成一条。不调用模型。"""
    import subprocess
    import tempfile
    from pathlib import Path

    if len(parts) < 2:
        raise ModelError("至少要有两段已经生成的视频")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        paths = []
        for index, raw in enumerate(parts):
            path = root / f"{index}.mp4"
            path.write_bytes(raw)
            paths.append(path)
        listing = root / "list.txt"
        listing.write_text("".join(f"file '{path}'\n" for path in paths), encoding="utf-8")
        output = root / "out.mp4"
        copy = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(output)], capture_output=True)
        if copy.returncode != 0 or not output.exists() or output.stat().st_size == 0:
            encoded = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)],
                capture_output=True,
            )
            if encoded.returncode != 0 or not output.exists() or output.stat().st_size == 0:
                raise ModelError("这几段视频拼不到一起")
        return output.read_bytes()
