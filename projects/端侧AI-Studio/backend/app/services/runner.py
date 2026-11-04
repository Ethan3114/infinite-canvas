"""生成卡和出图的后台步骤。商汤同一时间只跑一个任务，钥匙用完或失败后换下一把。"""

import threading
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import Asset, Job, ProviderState
from app.services.cards import image_prompt, parse_card
from app.services.files import ensure_min_size, read_asset, save_bytes
from app.services.providers import DeepSeekClient, ModelError, SenseTimeClient

_thread_lock = threading.Lock()


def seed_provider(db: Session) -> ProviderState:
    state = db.get(ProviderState, "sensetime")
    if state is None:
        state = ProviderState(name="sensetime", key_index=0, lock_job_id="")
        db.add(state)
        db.commit()
    return state


def recover_lock(db: Session) -> None:
    """进程中断后，把占着的锁放开，没出完的图回到排队。"""
    state = seed_provider(db)
    if not state.lock_job_id:
        return
    job = db.get(Job, state.lock_job_id)
    if job is not None and job.status == "running":
        job.status = "queued"
    state.lock_job_id = ""
    db.commit()


def run_card(factory: sessionmaker, job_id: str, settings: Settings, client: DeepSeekClient) -> None:
    db = factory()
    try:
        job = db.get(Job, job_id)
        if job is None or job.status != "card_pending":
            return
        asset = db.get(Asset, job.upload_asset_id)
        if asset is None:
            _fail(db, job, "bad_file", "上传的图找不到了")
            return
        raw = read_asset(Path(settings.resolved_data_dir()), asset.relpath).read_bytes()
        last = "生成卡没有按格式返回，请换种说法再试一次"
        for _ in range(2):
            try:
                text = client.complete(raw, asset.mime, job.user_text, job.image_type)
                card = parse_card(text, job.image_type)
                job.card_json = card.model_dump_json()
                job.status = "card_ready"
                job.error_code = ""
                job.error_message = ""
                db.commit()
                return
            except ModelError as exc:
                last = exc.message
                break
            except Exception:
                last = "生成卡没有按格式返回，请换种说法再试一次"
        _fail(db, job, "model_failed", last)
    finally:
        db.close()


def run_image(
    factory: sessionmaker,
    job_id: str,
    settings: Settings,
    client: SenseTimeClient,
) -> None:
    db = factory()
    try:
        job = db.get(Job, job_id)
        if job is None or job.status not in {"queued", "running"}:
            return
        keys = settings.sensetime_keys()
        with _thread_lock:
            state = seed_provider(db)
            if state.lock_job_id and state.lock_job_id != job_id:
                job.status = "queued"
                db.commit()
                return
            if not keys and not settings.fake_models:
                _fail(db, job, "model_unconfigured", "还没有配置商汤钥匙")
                return
            state.lock_job_id = job_id
            job.status = "running"
            key = ""
            if keys:
                key = keys[state.key_index % len(keys)]
            db.commit()
        try:
            asset = db.get(Asset, job.upload_asset_id)
            card_text = job.card_json
            from app.services.cards import GenerationCard

            card = GenerationCard.model_validate_json(card_text)
            raw = read_asset(Path(settings.resolved_data_dir()), asset.relpath).read_bytes()
            raw, mime = ensure_min_size(raw)
            image = client.generate(key, image_prompt(card), raw, mime)
            rel = save_bytes(Path(settings.resolved_data_dir()), job.owner_id, image, "image/png")
            saved = Asset(
                id=_new_id(),
                owner_id=job.owner_id,
                kind="result",
                relpath=rel,
                mime="image/png",
                size=len(image),
            )
            db.add(saved)
            job.result_asset_id = saved.id
            job.status = "succeeded"
            job.error_code = ""
            job.error_message = ""
            db.commit()
        except ModelError as exc:
            _fail(db, job, "model_failed", exc.message)
        except Exception:
            _fail(db, job, "model_failed", "出图没有完成，请再试一次")
        finally:
            with _thread_lock:
                state = seed_provider(db)
                if state.lock_job_id == job_id:
                    state.lock_job_id = ""
                    if keys:
                        state.key_index = (state.key_index + 1) % len(keys)
                db.commit()
    finally:
        db.close()
    kick_next(factory, settings, client)


def kick_next(factory: sessionmaker, settings: Settings, client: SenseTimeClient) -> None:
    db = factory()
    try:
        state = seed_provider(db)
        if state.lock_job_id:
            return
        nxt = db.query(Job).filter(Job.status == "queued").order_by(Job.created_at.asc()).first()
        nxt_id = nxt.id if nxt else ""
    finally:
        db.close()
    if nxt_id:
        run_image(factory, nxt_id, settings, client)


def _fail(db: Session, job: Job, code: str, message: str) -> None:
    job.status = "failed"
    job.error_code = code
    job.error_message = message[:300]
    db.commit()


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex
