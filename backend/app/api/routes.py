"""页面能调用的接口。每个接口都校验登录和归属，错误格式固定。"""

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Asset, Job, SessionRow, User, Work, utc_now
from app.services.files import FileRejected, read_asset, save_bytes, sniff_image
from app.services.runner import run_card, run_image, seed_provider

router = APIRouter(prefix="/api/v1")


class LoginBody(BaseModel):
    invite_code: str = Field(min_length=1, max_length=80)


class WorkBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class JobBody(BaseModel):
    work_id: str
    upload_asset_id: str
    image_type: str
    user_text: str = Field(min_length=1, max_length=500)


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def db_session(request: Request) -> Session:
    return request.app.state.factory()


def owner_id(request: Request, db: Session) -> str | None:
    sid = request.cookies.get("session")
    if not sid:
        return None
    row = db.get(SessionRow, sid)
    if row is None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < utc_now():
        return None
    return row.owner_id


def job_dict(job: Job) -> dict:
    card = json.loads(job.card_json) if job.card_json else None
    return {
        "id": job.id,
        "work_id": job.work_id,
        "status": job.status,
        "image_type": job.image_type,
        "user_text": job.user_text,
        "card": card,
        "upload_asset_id": job.upload_asset_id,
        "result_asset_id": job.result_asset_id or None,
        "error": {"code": job.error_code, "message": job.error_message} if job.error_code else None,
    }


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.post("/auth/login")
def login(body: LoginBody, request: Request):
    settings = request.app.state.settings
    if body.invite_code != settings.invite_code:
        return error(401, "bad_invite", "邀请码不对")
    db = db_session(request)
    try:
        user = User(id=uuid.uuid4().hex)
        sid = uuid.uuid4().hex
        db.add(user)
        db.add(
            SessionRow(
                id=sid,
                owner_id=user.id,
                expires_at=utc_now() + timedelta(days=settings.session_days),
            )
        )
        db.commit()
    finally:
        db.close()
    response = JSONResponse({"ok": True})
    response.set_cookie("session", sid, httponly=True, samesite="lax", path="/", max_age=settings.session_days * 86400)
    return response


@router.post("/auth/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("session", path="/")
    return response


@router.get("/auth/me")
def me(request: Request):
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        return {"owner_id": uid}
    finally:
        db.close()


@router.post("/works")
def create_work(body: WorkBody, request: Request):
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        work = Work(id=uuid.uuid4().hex, owner_id=uid, title=body.title)
        db.add(work)
        db.commit()
        return {"id": work.id, "title": work.title}
    finally:
        db.close()


@router.get("/works/{work_id}")
def get_work(work_id: str, request: Request):
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        work = db.get(Work, work_id)
        if work is None or work.owner_id != uid:
            return error(404, "not_found", "找不到这张画布")
        return {"id": work.id, "title": work.title}
    finally:
        db.close()


@router.post("/uploads")
async def upload(request: Request, file: UploadFile = File(...)):
    raw = await file.read()
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        try:
            mime = sniff_image(raw, request.app.state.settings.max_upload_bytes)
            rel = save_bytes(request.app.state.settings.resolved_data_dir(), uid, raw, mime)
        except FileRejected as exc:
            return error(400, "bad_file", exc.message)
        asset = Asset(id=uuid.uuid4().hex, owner_id=uid, kind="upload", relpath=rel, mime=mime, size=len(raw))
        db.add(asset)
        db.commit()
        return {"id": asset.id, "mime": mime}
    finally:
        db.close()


@router.post("/jobs")
def create_job(body: JobBody, request: Request, background: BackgroundTasks):
    if body.image_type not in {"主图", "场景图"}:
        return error(400, "invalid", "图类型只能是主图或场景图")
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        work = db.get(Work, body.work_id)
        asset = db.get(Asset, body.upload_asset_id)
        if work is None or work.owner_id != uid or asset is None or asset.owner_id != uid:
            return error(404, "not_found", "找不到要用来出图的内容")
        job = Job(
            id=uuid.uuid4().hex,
            owner_id=uid,
            work_id=work.id,
            status="card_pending",
            image_type=body.image_type,
            user_text=body.user_text.strip(),
            upload_asset_id=asset.id,
        )
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()
    background.add_task(run_card, request.app.state.factory, job_id, request.app.state.settings, request.app.state.card_client)
    return JSONResponse(status_code=202, content={"id": job_id, "status": "card_pending"})


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        job = db.get(Job, job_id)
        if job is None or job.owner_id != uid:
            return error(404, "not_found", "找不到这个任务")
        return job_dict(job)
    finally:
        db.close()


@router.post("/jobs/{job_id}/confirm")
def confirm_job(job_id: str, request: Request, background: BackgroundTasks):
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        job = db.get(Job, job_id)
        if job is None or job.owner_id != uid:
            return error(404, "not_found", "找不到这个任务")
        if job.status != "card_ready":
            return error(409, "invalid_state", "要等生成卡出来之后才能确认")
        seed_provider(db)
        job.status = "queued"
        job.updated_at = utc_now()
        db.commit()
    finally:
        db.close()
    background.add_task(
        run_image,
        request.app.state.factory,
        job_id,
        request.app.state.settings,
        request.app.state.image_client,
    )
    return JSONResponse(status_code=202, content={"id": job_id, "status": "queued"})


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, request: Request):
    db = db_session(request)
    try:
        uid = owner_id(request, db)
        if not uid:
            return error(401, "unauthorized", "请先输入邀请码")
        asset = db.get(Asset, asset_id)
        if asset is None or asset.owner_id != uid:
            return error(404, "not_found", "找不到这张图")
        try:
            path = read_asset(request.app.state.settings.resolved_data_dir(), asset.relpath)
        except FileRejected:
            return error(404, "not_found", "找不到这张图")
        return FileResponse(path, media_type=asset.mime)
    finally:
        db.close()
