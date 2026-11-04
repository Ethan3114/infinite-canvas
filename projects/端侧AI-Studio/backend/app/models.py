"""本地数据库表。每条业务记录都带 owner_id，查询时只看当前登录的人。"""

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column()


class Work(Base):
    __tablename__ = "works"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    relpath: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    image_type: Mapped[str] = mapped_column(String(10))
    user_text: Mapped[str] = mapped_column(Text)
    card_json: Mapped[str] = mapped_column(Text, default="")
    upload_asset_id: Mapped[str] = mapped_column(String(32))
    result_asset_id: Mapped[str] = mapped_column(String(32), default="")
    error_code: Mapped[str] = mapped_column(String(40), default="")
    error_message: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class ProviderState(Base):
    """商汤全局锁和钥匙序号。同一时间 lock_job_id 只能有一个。"""

    __tablename__ = "provider_state"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    key_index: Mapped[int] = mapped_column(Integer, default=0)
    lock_job_id: Mapped[str] = mapped_column(String(32), default="")
