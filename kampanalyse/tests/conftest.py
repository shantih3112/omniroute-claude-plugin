from datetime import date, datetime, time
from types import SimpleNamespace

import pytest

from kampanalyse.__main__ import build
from kampanalyse.config import Config
from kampanalyse.db import DB
from kampanalyse.timeutil import FixedClock, local_at


class FakeSender:
    def __init__(self):
        self.sent: list[tuple[int, str, list | None]] = []

    async def send(self, chat_id, text, markup):
        self.sent.append((chat_id, text, markup))
        return len(self.sent)

    async def pin(self, chat_id, mid):
        pass


def make_engine(db_path=":memory:", at: datetime | None = None, **cfg_over):
    clock = FixedClock(at or local_at(date(2026, 10, 20), time(6, 0)))
    cfg = Config()
    cfg.data_provider = "demo"
    cfg.owner_telegram_id = 1
    for k, v in cfg_over.items():
        setattr(cfg, k, v)
    db = DB(str(db_path))
    eng = build(cfg, db, clock)
    eng.ensure_owner()
    eng.sender = FakeSender()
    return eng, clock


async def run_until(eng, clock, until: datetime, step_minutes: int = 1):
    while clock.now() < until:
        await eng.tick()
        clock.advance(minutes=step_minutes)


@pytest.fixture
def engine():
    return make_engine()


def fake_update(chat_id: int, args=None, data=None):
    replies = []

    async def reply_html(text, **kw):
        replies.append(text)
        return SimpleNamespace(message_id=len(replies))

    async def reply_text(text, **kw):
        replies.append(text)

    async def answer(*a, **kw):
        replies.append(("answer", a, kw))

    msg = SimpleNamespace(reply_html=reply_html, reply_text=reply_text)
    cq = SimpleNamespace(data=data, answer=answer, message=msg) if data is not None else None
    upd = SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id), effective_message=msg, callback_query=cq)
    ctx = SimpleNamespace(args=args or [], bot=SimpleNamespace(pin_chat_message=_noop))
    return upd, ctx, replies


async def _noop(*a, **kw):
    return None
