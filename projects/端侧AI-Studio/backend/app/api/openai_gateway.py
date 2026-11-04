"""给 infinite-canvas 用的图片接口。

画布按 OpenAI 的地址来请求。钥匙留在后端，商汤同一时间只出一张。
"""

import base64
import threading
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.cards import image_prompt, parse_card
from app.services.files import ensure_min_size, pack_sizes
from app.services.providers import AntVideoClient, ModelError, concat_mp4
from app.services.runner import seed_provider
from app.services.storyboard import format_drama, parse_drama, system_prompt as drama_system

router = APIRouter()
_lock = threading.Lock()


def _fail(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": message, "type": "invalid_request_error"}})


def _size(value: object) -> str:
    text = str(value or "")
    parts = text.lower().split("x")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        width, height = int(parts[0]), int(parts[1])
        if 256 <= width <= 4096 and 256 <= height <= 4096:
            return f"{width}x{height}"
    return "1024x1024"


def _message_parts(messages: list) -> tuple[str, bytes | None, str]:
    texts: list[str] = []
    image: tuple[bytes, str] | None = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
            continue
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                texts.append(str(part.get("text") or ""))
            if part.get("type") == "image_url" and image is None:
                url = str((part.get("image_url") or {}).get("url") or "")
                if url.startswith("data:") and "," in url:
                    header, encoded = url.split(",", 1)
                    mime = header.split(";")[0].replace("data:", "") or "image/png"
                    image = (base64.b64decode(encoded), mime)
    return "\n".join(part for part in texts if part.strip()).strip(), *(image or (None, ""))


def _prompt_from_messages(request: Request, messages: list) -> str:
    user_text, raw, mime = _message_parts(messages)
    if not user_text and raw is None:
        raise ModelError("没有要看的文字或图片")
    image_type = "主图" if "主图" in user_text else "场景图"
    client = request.app.state.card_client
    last = "DeepSeek 没有写成提示词"
    for _ in range(2):
        try:
            text = client.complete(raw, mime, user_text or "根据图片写提示词", image_type) if raw else client.complete_text(user_text, image_type)
            return image_prompt(parse_card(text, image_type))
        except ModelError:
            raise
        except Exception:
            last = "DeepSeek 没有写成提示词"
    raise ModelError(last)


def _drama_from_messages(request: Request, messages: list, task: str) -> str:
    """短剧文本。一次只写 task 指定的那一种。"""
    user_text, raw, mime = _message_parts(messages)
    if not user_text and raw is None:
        raise ModelError("没有要看的文字或图片")
    try:
        system = drama_system(task)
    except ValueError as exc:
        raise ModelError("不认识的短剧步骤") from exc
    client = request.app.state.card_client
    last = "DeepSeek 没有写成这一步"
    for _ in range(2):
        try:
            text = client.complete_drama(task, system, raw, mime, user_text or "根据已有内容完成本步")
            return format_drama(task, parse_drama(task, text))
        except ModelError:
            raise
        except Exception:
            last = "DeepSeek 没有写成这一步"
    raise ModelError(last)


def _call(request: Request, fn):
    settings = request.app.state.settings
    keys = settings.sensetime_keys()
    if not keys and not settings.fake_models:
        raise ModelError("还没有配置商汤钥匙")
    with _lock:
        db = request.app.state.factory()
        try:
            state = seed_provider(db)
            key = keys[state.key_index % len(keys)] if keys else ""
            try:
                image = fn(key)
            finally:
                if keys:
                    state.key_index = (state.key_index + 1) % len(keys)
                db.commit()
        finally:
            db.close()
    return image


@router.post("/v1/videos/frames")
async def video_frames(request: Request):
    """短剧视频。前一张分镜图是首帧，后一张是尾帧。没有钥匙时不扣费。"""
    if request.app.state.settings.fake_models:
        return {"task_id": "fake-video", "status": "pending"}
    body = await request.json()
    first_url = str(body.get("first_frame") or "")
    last_url = str(body.get("last_frame") or "")
    if not first_url.startswith("data:image/") or not last_url.startswith("data:image/"):
        return _fail("首帧和尾帧都要是已经生成的分镜图")
    client = AntVideoClient(request.app.state.settings)
    try:
        task_id = client.create_clip(str(body.get("prompt") or ""), first_url, last_url)
    except ModelError as exc:
        return _fail(exc.message, 400 if "钥匙" in exc.message else 502)
    return {"task_id": task_id, "status": "pending"}


@router.post("/v1/videos/concat")
async def video_concat(request: Request):
    """把多段视频按上传顺序接成一条。不调用模型。"""
    form = await request.form()
    blobs = []
    for item in form.getlist("videos"):
        if not hasattr(item, "read"):
            continue
        blobs.append(await item.read())
    try:
        merged = concat_mp4(blobs)
    except ModelError as exc:
        return _fail(exc.message, 400)
    from fastapi.responses import Response

    return Response(content=merged, media_type="video/mp4")


@router.get("/v1/videos/frames/{task_id}")
def video_frame_status(task_id: str, request: Request):
    if request.app.state.settings.fake_models and task_id == "fake-video":
        return {"status": "succeeded", "url": ""}
    client = AntVideoClient(request.app.state.settings)
    try:
        return client.read_clip(task_id)
    except ModelError as exc:
        return _fail(exc.message, 502)


@router.get("/v1/models")
def models(request: Request):
    settings = request.app.state.settings
    names = [settings.sensetime_model]
    if settings.deepseek_model:
        names.append(settings.deepseek_model)
    return {"object": "list", "data": [{"id": name, "object": "model"} for name in names]}


@router.post("/v1/responses")
async def responses(request: Request):
    """画布的「文本生成」。电商写成生图提示词。短剧按 task 一次只写一种。"""
    body = await request.json()
    messages = body.get("input") or body.get("messages") or []
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    workflow = str(body.get("workflow") or "ecommerce")
    if workflow not in {"ecommerce", "drama"}:
        return _fail("不认识的工作流")
    task = str(body.get("task") or "")
    if workflow == "drama" and not task:
        return _fail("请选择短剧的这一步")
    try:
        text = _drama_from_messages(request, messages, task) if workflow == "drama" else _prompt_from_messages(request, messages)
    except ModelError as exc:
        return _fail(exc.message, 502)
    return {"output_text": text, "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


@router.post("/v1/images/generations")
async def generations(request: Request):
    body = await request.json()
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return _fail("缺少画面描述")
    count = max(1, min(int(body.get("n") or 1), 4))
    size = _size(body.get("size"))
    client = request.app.state.image_client
    data = []
    try:
        for _ in range(count):
            image = _call(request, lambda key: client.generate_text(key, prompt, size))
            data.append({"b64_json": base64.b64encode(image).decode()})
    except ModelError as exc:
        return _fail(exc.message, 502)
    return {"created": int(time.time()), "data": data}


@router.post("/v1/images/edits")
async def edits(request: Request):
    form = await request.form()
    prompt = str(form.get("prompt") or "").strip()
    if not prompt:
        return _fail("缺少画面描述")
    uploads = []
    for key in ("image", "image[]"):
        uploads.extend(form.getlist(key))
    files = [item for item in uploads if hasattr(item, "read")]
    if not files:
        return _fail("缺少参考图")
    prepared = []
    for item in files:
        try:
            prepared.append(ensure_min_size(await item.read()))
        except Exception:
            return _fail("这张图打不开")
    client = request.app.state.image_client
    data = []
    try:
        for raw, mime in prepared:
            image = _call(request, lambda key, raw=raw, mime=mime: client.generate(key, prompt, raw, mime))
            data.append({"b64_json": base64.b64encode(image).decode()})
    except ModelError as exc:
        return _fail(exc.message, 502)
    return {"created": int(time.time()), "data": data}


@router.post("/v1/images/sizes")
async def sizes(request: Request):
    """批量改尺寸。只裁切，不调用商汤。"""
    form = await request.form()
    uploads = [item for item in form.getlist("image") if hasattr(item, "read")]
    if not uploads:
        return _fail("缺少图片")
    try:
        packed = pack_sizes(await uploads[0].read())
    except Exception:
        return _fail("这张图打不开")
    return {"created": int(time.time()), "data": [{"b64_json": base64.b64encode(item).decode()} for item in packed]}
