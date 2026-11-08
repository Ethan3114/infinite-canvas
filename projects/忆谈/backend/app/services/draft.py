"""用 DeepSeek 写成回忆。先抽时间节点，再按节点写。审的模型先不调用。钥匙只在服务端。"""

import json
from datetime import timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Chapter, FactItem, MemoryItem, Paragraph, utcnow
from app.services.grounding import elder_text, excerpt_around, keep_grounded, transcripts_disagree
from app.services.memoir import reader_fact
from app.services.redact import redact_sensitive
from app.services.store import new_id, transcripts_for

_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
PROMPT = (_PROMPTS / "chapter.txt").read_text(encoding="utf-8")
TIMELINE_PROMPT = (_PROMPTS / "timeline.txt").read_text(encoding="utf-8")
REVIEW_PROMPT = (_PROMPTS / "review.txt").read_text(encoding="utf-8")
_USER_LIMIT = 60000


class DraftError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _Memory(BaseModel):
    kind: str = "event"
    name: str = ""
    detail: str = ""
    source_quote: str = ""


class _Paragraph(BaseModel):
    text: str = ""
    source_quote: str = ""


class _Uncertain(BaseModel):
    topic: str = ""
    detail: str = ""
    source_quote: str = ""


class _Node(BaseModel):
    when: str = ""
    event: str = ""
    who: str = ""
    source_quote: str = ""


class _Timeline(BaseModel):
    nodes: list[_Node] = Field(default_factory=list)
    uncertain: list[_Uncertain] = Field(default_factory=list)


class _ChapterDraft(BaseModel):
    title: str = "这段回忆"
    paragraphs: list[_Paragraph] = Field(default_factory=list)


class _Book(BaseModel):
    chapters: list[_ChapterDraft] = Field(default_factory=list)
    memories: list[_Memory] = Field(default_factory=list)
    uncertain: list[_Uncertain] = Field(default_factory=list)


class _Draft(BaseModel):
    title: str = "这段回忆"
    memories: list[_Memory] = Field(default_factory=list)
    paragraphs: list[_Paragraph] = Field(default_factory=list)
    uncertain: list[_Uncertain] = Field(default_factory=list)


class _Review(BaseModel):
    accept: bool = False
    title: str = ""
    paragraphs: list[_Paragraph] = Field(default_factory=list)


def _parse(raw: str) -> _Draft:
    data = json.loads(raw)
    return _Draft.model_validate(data)


def _load(raw: str, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise DraftError("draft_failed", "这一段没有整理出来，原话还在，可以再试一次") from exc


async def _complete(settings: Settings, system: str, user: str) -> str:
    last_error: Exception | None = None
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    settings.deepseek_base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                    json={
                        "model": settings.deepseek_model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user[:_USER_LIMIT]},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                        "max_tokens": 8000,
                    },
                )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except DraftError:
            raise
        except Exception as exc:
            last_error = exc
    raise DraftError("draft_failed", "这一段没有整理出来，原话还在，可以再试一次") from last_error


def _node_packet(source: str, timeline: _Timeline) -> list[dict]:
    """只把对得上同一轮原话的节点交给写作，并按抽出的顺序编号。"""
    packet: list[dict] = []
    for node in timeline.nodes:
        quote = node.source_quote.strip()
        if not keep_grounded(node.event or node.when or quote, quote, source):
            continue
        nearby = excerpt_around(source, quote)
        packet.append(
            {
                "order": len(packet) + 1,
                "when": node.when.strip(),
                "event": node.event.strip(),
                "who": node.who.strip() or "我",
                "source_quote": quote,
                "nearby": nearby,
            }
        )
        if len(packet) >= 24:
            break
    return packet


async def compose(settings: Settings, source: str) -> _Book:
    """第一步抽时间节点，第二步按节点写成章。逐字稿只用来核对和补口头说法。"""
    timeline = _load(await _complete(settings, TIMELINE_PROMPT, source), _Timeline)
    if not isinstance(timeline, _Timeline):
        raise DraftError("draft_failed", "这一段没有整理出来，原话还在，可以再试一次")
    nodes = _node_packet(source, timeline)
    if not nodes:
        raise DraftError("not_a_memoir", "这段里还抽不出能对上原话的时间节点。原话还在，可以再试一次")
    packet = json.dumps({"nodes": nodes}, ensure_ascii=False)
    book = _load(await _complete(settings, PROMPT, packet), _Book)
    if not isinstance(book, _Book):
        raise DraftError("draft_failed", "这一段没有整理出来，原话还在，可以再试一次")
    book.uncertain = [*timeline.uncertain, *book.uncertain]
    return book


async def _ask(settings: Settings, source: str) -> _Draft:
    book = await compose(settings, source)
    paragraphs: list[_Paragraph] = []
    title = "这段回忆"
    for chapter in book.chapters:
        title = chapter.title or title
        paragraphs.extend(chapter.paragraphs)
    return _Draft(title=title, memories=book.memories, paragraphs=paragraphs, uncertain=book.uncertain)


async def _review(settings: Settings, source: str, draft: _Draft) -> _Review:
    packet = json.dumps(
        {
            "source": source,
            "draft_title": draft.title,
            "paragraphs": [item.model_dump() for item in draft.paragraphs],
        },
        ensure_ascii=False,
    )
    return _Review.model_validate(json.loads(await _complete(settings, REVIEW_PROMPT, packet)))


def _clear_previous(db: Session, owner_id: str, call_id: str) -> None:
    chapter_ids = list(db.scalars(select(Chapter.id).where(Chapter.owner_id == owner_id, Chapter.call_id == call_id)))
    if chapter_ids:
        db.execute(delete(Paragraph).where(Paragraph.chapter_id.in_(chapter_ids)))
        db.execute(delete(Chapter).where(Chapter.id.in_(chapter_ids)))
    db.execute(delete(MemoryItem).where(MemoryItem.owner_id == owner_id, MemoryItem.call_id == call_id))
    db.execute(delete(FactItem).where(FactItem.owner_id == owner_id, FactItem.call_id == call_id))
    db.commit()


async def build_draft(db: Session, settings: Settings, owner_id: str, call_id: str, profile_id: str) -> Chapter:
    if not settings.writing_ready:
        raise DraftError("model_not_configured", "还没有配置写章节用的 DeepSeek 钥匙")
    rows = transcripts_for(db, owner_id, call_id)
    texts = {row.track: row.text for row in rows}
    raw_source = elder_text(texts)
    source = redact_sensitive(raw_source)
    card_removed = source != raw_source.strip()
    if not source:
        raise DraftError("no_transcript", "这通通话还没有老人的原话，不能写章节")
    book = await compose(settings, source)
    saved: list[tuple[str, list[tuple[str, str]]]] = []
    dropped: list[tuple[str, str]] = []
    for chapter_draft in book.chapters[:2]:
        kept_lines: list[tuple[str, str]] = []
        for item in chapter_draft.paragraphs[:4]:
            text = redact_sensitive(item.text).strip()
            quote = redact_sensitive(item.source_quote).strip()
            if text != (item.text or "").strip() or quote != (item.source_quote or "").strip():
                card_removed = True
            if keep_grounded(text, quote, source):
                kept_lines.append((text, quote))
            elif text:
                dropped.append((text, quote))
        if kept_lines:
            title = (redact_sensitive(chapter_draft.title).strip() or "这段回忆")[:80]
            saved.append((title, kept_lines))
    if not saved:
        raise DraftError("not_a_memoir", "这通还写不成一段能给家人读的回忆。原话还在，可以再试一次")
    _clear_previous(db, owner_id, call_id)
    started = utcnow()
    chapter: Chapter | None = None
    for index, (title, lines) in enumerate(saved):
        chapter = Chapter(
            id=new_id(),
            owner_id=owner_id,
            call_id=call_id,
            title=title,
            created_at=started + timedelta(seconds=index),
        )
        db.add(chapter)
        for position, (text, quote) in enumerate(lines):
            db.add(
                Paragraph(
                    id=new_id(),
                    owner_id=owner_id,
                    chapter_id=chapter.id,
                    position=position,
                    text=text,
                    source_quote=quote,
                )
            )
    for text, quote in dropped:
        db.add(
            FactItem(
                id=new_id(),
                owner_id=owner_id,
                call_id=call_id,
                topic="无法对上原话",
                detail="这句在原话里找不到出处，没有写进正文",
                source_quote=redact_sensitive(quote)[:500],
            )
        )
    allowed = {"person", "place", "time", "event"}
    for item in book.memories[:20]:
        name = redact_sensitive(item.name or "未命名")[:80]
        detail = redact_sensitive(item.detail)[:500]
        quote = redact_sensitive(item.source_quote).strip()
        if not keep_grounded(name or detail, quote, source):
            continue
        db.add(
            MemoryItem(
                id=new_id(),
                owner_id=owner_id,
                profile_id=profile_id,
                call_id=call_id,
                kind=item.kind if item.kind in allowed else "event",
                name=name or "未命名",
                detail=detail,
                source_quote=quote,
            )
        )
    if card_removed:
        db.add(
            FactItem(
                id=new_id(),
                owner_id=owner_id,
                call_id=call_id,
                topic="银行卡号已略去",
                detail="原话里有一串银行卡号，没有写进正文，也没有记进记忆",
                source_quote="",
            )
        )
    if transcripts_disagree(texts):
        db.add(
            FactItem(
                id=new_id(),
                owner_id=owner_id,
                call_id=call_id,
                topic="两路转写不一致",
                detail="两遍听写不完全一样，正文按更完整的那遍来写",
                source_quote=source[:180],
            )
        )
    for item in book.uncertain[:12]:
        db.add(
            FactItem(
                id=new_id(),
                owner_id=owner_id,
                call_id=call_id,
                topic=(item.topic or "待核对")[:80],
                detail=redact_sensitive(item.detail)[:500],
                source_quote=redact_sensitive(item.source_quote)[:500],
            )
        )
    db.commit()
    if chapter is None:
        raise DraftError("not_a_memoir", "这通还写不成一段能给家人读的回忆。原话还在，可以再试一次")
    db.refresh(chapter)
    return chapter


def _fact_for_reader(row: FactItem) -> dict:
    topic, detail = reader_fact(row.topic, row.detail)
    return {"id": row.id, "topic": topic, "detail": detail, "status": row.status}


def chapter_views(db: Session, owner_id: str, call_id: str) -> list[dict]:
    """一通可以有前后两章。核对事项只挂在前一章上，避免页面重复。"""
    chapters = list(
        db.scalars(
            select(Chapter)
            .where(Chapter.owner_id == owner_id, Chapter.call_id == call_id)
            .order_by(Chapter.created_at, Chapter.id)
        )
    )
    if not chapters:
        return []
    facts = list(db.scalars(select(FactItem).where(FactItem.owner_id == owner_id, FactItem.call_id == call_id)))
    memories = list(db.scalars(select(MemoryItem).where(MemoryItem.owner_id == owner_id, MemoryItem.call_id == call_id)))
    fact_rows = [_fact_for_reader(row) for row in facts]
    memory_rows = [{"kind": row.kind, "name": row.name, "detail": row.detail} for row in memories]
    views: list[dict] = []
    for index, chapter in enumerate(chapters):
        paragraphs = list(
            db.scalars(
                select(Paragraph)
                .where(Paragraph.owner_id == owner_id, Paragraph.chapter_id == chapter.id)
                .order_by(Paragraph.position)
            )
        )
        views.append(
            {
                "id": chapter.id,
                "title": chapter.title,
                "paragraphs": [
                    {"id": row.id, "text": row.text, "source_quote": row.source_quote} for row in paragraphs
                ],
                "facts": fact_rows if index == 0 else [],
                "memories": memory_rows if index == 0 else [],
            }
        )
    return views


def chapter_view(db: Session, owner_id: str, call_id: str) -> dict | None:
    """开场提起的是后一章，下一次从人生后半接着说。"""
    views = chapter_views(db, owner_id, call_id)
    return views[-1] if views else None


def update_fact(db: Session, owner_id: str, fact_id: str, status: str, detail: str) -> bool:
    row = db.get(FactItem, fact_id)
    if row is None or row.owner_id != owner_id or status not in {"open", "confirmed", "rejected"}:
        return False
    row.status = status
    if detail.strip():
        row.detail = redact_sensitive(detail)[:500]
    db.commit()
    return True


def score_paragraph(db: Session, owner_id: str, paragraph_id: str, score: int) -> bool:
    row = db.get(Paragraph, paragraph_id)
    if row is None or row.owner_id != owner_id or score not in {1, 2, 3}:
        return False
    row.score = score
    db.commit()
    return True
