"""浏览器和豆包之间的实时通话。"""

import base64
import json

from fastapi import APIRouter, WebSocket
from sqlalchemy.orm import Session

from app.services.brief import latest_opening
from app.services.calls import persist_call
from app.services.doubao import RealtimeSession, VoiceError, transcribe_pcm
from app.services.store import get_call, owner_from_session, COOKIE

router = APIRouter()


def _db(websocket: WebSocket) -> Session:
    return websocket.app.state.db_factory()


@router.websocket("/api/v1/calls/{call_id}/live")
async def live(websocket: WebSocket, call_id: str) -> None:
    await websocket.accept()
    db = _db(websocket)
    try:
        owner = owner_from_session(db, websocket.cookies.get(COOKIE))
        call = get_call(db, owner, call_id) if owner else None
        if call is None or call.status != "live":
            await websocket.send_json({"type": "error", "error": {"code": "not_found", "message": "这通通话不存在或已经结束"}})
            await websocket.close()
            return
        session = RealtimeSession(websocket.app.state.settings)
        opening = latest_opening(db, owner, call.profile_id, call.id)
        try:
            await session.connect(opening)
            if opening:
                try:
                    await session.say(opening)
                except Exception:
                    pass
        except VoiceError as exc:
            await persist_call(db, websocket.app.state.fernet, websocket.app.state.settings.data_path, call, b"", b"", "", "", None, exc)
            await websocket.send_json({"type": "error", "error": {"code": exc.code, "message": exc.message}})
            await websocket.close()
            return
        await websocket.send_json({"type": "ready"})
        user_pcm = bytearray()
        failure: VoiceError | None = None
        try:
            while True:
                raw = await websocket.receive_text()
                message = json.loads(raw)
                if message.get("type") == "stop":
                    break
                if message.get("type") != "audio":
                    continue
                chunk = base64.b64decode(message.get("pcm") or "")
                user_pcm.extend(chunk)
                await session.send_pcm(chunk)
                for event in await session.pull_available():
                    await _forward(websocket, event)
            await session.finish()
        except VoiceError as exc:
            failure = exc
        except Exception as exc:
            print(f"call interrupted: {type(exc).__name__}", flush=True)
            failure = VoiceError("voice_interrupted", "通话中断了，已经录下的声音会留下")
        side = ""
        if user_pcm:
            try:
                side = await transcribe_pcm(websocket.app.state.settings, bytes(user_pcm))
            except VoiceError as exc:
                if failure is None:
                    failure = exc
        await persist_call(
            db,
            websocket.app.state.fernet,
            websocket.app.state.settings.data_path,
            call,
            bytes(user_pcm),
            bytes(session.assistant_pcm),
            "".join(session.user_text),
            "".join(session.assistant_text),
            side,
            failure,
        )
        if failure is None:
            await websocket.send_json({"type": "done"})
        else:
            try:
                await websocket.send_json({"type": "error", "error": {"code": failure.code, "message": failure.message}})
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        db.close()


async def _forward(websocket: WebSocket, event: dict) -> None:
    kind = event.get("type")
    if kind == "conversation.item.input_audio_transcription.delta":
        text = event.get("delta") or event.get("text") or ""
        if text:
            await websocket.send_json({"type": "user_text", "text": text})
    elif kind == "response.output_text.delta":
        text = event.get("delta") or event.get("text") or ""
        if text:
            await websocket.send_json({"type": "assistant_text", "text": text})
    elif kind == "response.output_audio.delta":
        audio = event.get("delta") or event.get("audio") or ""
        if audio:
            await websocket.send_json({"type": "audio", "pcm": audio})
