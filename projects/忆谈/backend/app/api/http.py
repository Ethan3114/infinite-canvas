"""HTTP 接口。"""

import asyncio
from collections.abc import Generator

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import error_response
from app.schemas import CallIn, FactIn, LoginIn, ProfileIn, ScoreIn
from app.services import store
from app.services.draft import DraftError, build_draft, chapter_views, score_paragraph, update_fact
from app.services.tingwu import TingwuError, ensure_full_transcript

router = APIRouter(prefix="/api/v1")


def db_session(request: Request) -> Generator[Session, None, None]:
    db = request.app.state.db_factory()
    try:
        yield db
    finally:
        db.close()


def current_owner(request: Request, db: Session = Depends(db_session)) -> str | None:
    return store.owner_from_session(db, request.cookies.get(store.COOKIE))


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(db_session)):
    settings: Settings = request.app.state.settings
    if body.code != settings.invite_code:
        return error_response(401, "invite_invalid", "邀请码不正确")
    row = store.login_owner(db, settings.session_days)
    response = Response(content='{"ok":true}', media_type="application/json")
    response.set_cookie(store.COOKIE, row.id, httponly=True, samesite="lax", max_age=settings.session_days * 86400)
    return response


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(db_session)):
    store.delete_session(db, request.cookies.get(store.COOKIE))
    response = Response(content='{"ok":true}', media_type="application/json")
    response.delete_cookie(store.COOKIE)
    return response


@router.get("/me")
def me(request: Request, owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    settings: Settings = request.app.state.settings
    return {"owner_id": owner, "voice_ready": settings.voice_ready, "writing_ready": settings.writing_ready}


@router.post("/profiles")
def create_profile(body: ProfileIn, request: Request, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    row = store.create_profile(db, owner, body.model_dump())
    return {"id": row.id, "elder_name": row.elder_name}


@router.get("/profiles")
def profiles(db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    return {"items": [{"id": row.id, "elder_name": row.elder_name, "hometown": row.hometown} for row in store.list_profiles(db, owner)]}


@router.get("/profiles/{profile_id}")
def profile_detail(profile_id: str, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    row = store.get_profile(db, owner, profile_id)
    if row is None:
        return error_response(404, "not_found", "找不到这位老人的档案")
    calls = []
    for call in store.list_calls(db, owner, row.id):
        texts = {item.track: item.text for item in store.transcripts_for(db, owner, call.id)}
        views = chapter_views(db, owner, call.id)
        calls.append(
            {
                "id": call.id,
                "status": call.status,
                "failure_code": call.failure_code,
                "texts": texts,
                "chapter": views[0] if views else None,
                "chapters": views,
            }
        )
    return {
        "id": row.id,
        "elder_name": row.elder_name,
        "birth_year": row.birth_year,
        "hometown": row.hometown,
        "family_names": row.family_names,
        "topics_want": row.topics_want,
        "topics_avoid": row.topics_avoid,
        "calls": calls,
    }


@router.post("/profiles/{profile_id}/photos")
async def upload_photo(profile_id: str, request: Request, file: UploadFile = File(...), db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    row = store.get_profile(db, owner, profile_id)
    if row is None:
        return error_response(404, "not_found", "找不到这位老人的档案")
    data = await file.read()
    if len(data) > store.MAX_PHOTO:
        return error_response(400, "file_too_large", "照片不能超过 10 MB")
    kind = store.sniff_image(data)
    if kind is None:
        return error_response(400, "file_type", "只接收 jpg、png 或 webp 照片")
    saved = store.save_photo(db, request.app.state.fernet, request.app.state.settings.data_path, owner, profile_id, file.filename or "photo", data, kind)
    return {"id": saved.id, "content_type": saved.content_type}


@router.post("/calls")
def open_call(body: CallIn, request: Request, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    profile = store.get_profile(db, owner, body.profile_id)
    if profile is None:
        return error_response(404, "not_found", "找不到这位老人的档案")
    if not body.consent:
        store.add_audit(db, owner, "consent", "denied")
        return error_response(400, "consent_required", "老人还没有同意录音")
    settings: Settings = request.app.state.settings
    if not settings.voice_ready:
        return error_response(409, "voice_not_configured", "还没有配置豆包语音钥匙，通话暂时不能开始")
    call = store.create_call(db, owner, profile.id)
    return {"id": call.id, "status": call.status}


@router.get("/calls/{call_id}")
def call_detail(call_id: str, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    call = store.get_call(db, owner, call_id)
    if call is None:
        return error_response(404, "not_found", "找不到这通通话")
    texts = {item.track: item.text for item in store.transcripts_for(db, owner, call.id)}
    return {"id": call.id, "status": call.status, "failure_code": call.failure_code, "texts": texts}


@router.get("/calls/{call_id}/audio/{kind}")
def call_audio(call_id: str, kind: str, request: Request, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    if kind not in {"user", "assistant"}:
        return error_response(400, "audio_kind", "只能播放老人原声或 AI 回话")
    call = store.get_call(db, owner, call_id)
    if call is None:
        return error_response(404, "not_found", "找不到这通通话")
    pcm = store.read_audio(db, request.app.state.fernet, request.app.state.settings.data_path, owner, call_id, kind)
    if pcm is None:
        return error_response(404, "not_found", "这通通话还没有这段录音")
    rate = 16000 if kind == "user" else 24000
    return Response(content=store.pcm16_to_wav(pcm, rate), media_type="audio/wav")


@router.post("/calls/{call_id}/draft")
async def draft_call(call_id: str, request: Request, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    call = store.get_call(db, owner, call_id)
    if call is None:
        return error_response(404, "not_found", "找不到这通通话")
    if call.status not in {"ready", "failed"}:
        return error_response(409, "call_not_ready", "这通通话还没结束，不能整理成章")
    try:
        await asyncio.to_thread(
            ensure_full_transcript,
            db,
            request.app.state.settings,
            request.app.state.fernet,
            request.app.state.settings.data_path,
            owner,
            call.id,
        )
        chapter = await build_draft(db, request.app.state.settings, owner, call.id, call.profile_id)
    except (DraftError, TingwuError) as exc:
        return error_response(409, exc.code, exc.message)
    views = chapter_views(db, owner, call.id)
    return {"id": chapter.id, "chapters": views}


@router.post("/facts/{fact_id}")
def revise_fact(fact_id: str, body: FactIn, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    if not update_fact(db, owner, fact_id, body.status, body.detail):
        return error_response(404, "not_found", "找不到这一条核对")
    return {"ok": True}


@router.post("/paragraphs/{paragraph_id}/score")
def score(paragraph_id: str, body: ScoreIn, db: Session = Depends(db_session), owner: str | None = Depends(current_owner)):
    if owner is None:
        return error_response(401, "unauthorized", "请先登录")
    if not score_paragraph(db, owner, paragraph_id, body.score):
        return error_response(404, "not_found", "找不到这一段")
    return {"ok": True}
