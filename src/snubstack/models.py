from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class DomainState(StrEnum):
    RED = "red"
    GREEN = "green"
    PENDING = "pending"
    PENDING_REVIEW = "pending_review"
    UNKNOWN = "unknown"


class Domain(Base):
    __tablename__ = "domains"

    host: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    signals: Mapped[dict | None] = mapped_column(JSONB)
    detector_version: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_changed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FetchQueue(Base):
    __tablename__ = "fetch_queue"

    host: Mapped[str] = mapped_column(Text, primary_key=True)
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class PendingPost(Base):
    __tablename__ = "pending_posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_uri: Mapped[str] = mapped_column(Text, nullable=False)
    post_cid: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_pending_posts_host", "host"),)


class ShortenerResolution(Base):
    __tablename__ = "shortener_resolutions"

    short_url: Mapped[str] = mapped_column(Text, primary_key=True)
    resolved_url: Mapped[str | None] = mapped_column(Text)
    resolved_host: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_shortener_resolutions_resolved_host", "resolved_host"),
    )


class ShortenerQueue(Base):
    __tablename__ = "shortener_queue"

    short_url: Mapped[str] = mapped_column(Text, primary_key=True)
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class ShortenerPending(Base):
    __tablename__ = "shortener_pending"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_uri: Mapped[str] = mapped_column(Text, nullable=False)
    post_cid: Mapped[str] = mapped_column(Text, nullable=False)
    short_url: Mapped[str] = mapped_column(Text, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_shortener_pending_short_url", "short_url"),)


class LabelEmitted(Base):
    __tablename__ = "labels_emitted"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    post_uri: Mapped[str] = mapped_column(Text, nullable=False)
    post_cid: Mapped[str] = mapped_column(Text, nullable=False)
    val: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(Text, nullable=False)
    neg: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shadow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    ozone_error: Mapped[str | None] = mapped_column(Text)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ux_labels_emitted_uri_val_neg",
            "post_uri",
            "val",
            "neg",
            unique=True,
        ),
    )
