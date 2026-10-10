"""Shared email quota and overlapping scheduler regressions."""
import asyncio
from datetime import datetime, timedelta

import pytest

from app import digest, for_you, models
from tests.conftest import TestingSessionLocal


@pytest.fixture
def digest_members(db_session, monkeypatch):
    now = datetime(2026, 10, 10, 12)
    monkeypatch.setenv("SHARED_DAILY_CAP", "3")
    monkeypatch.setenv("DIGEST_DAILY_LIMIT", "50")
    monkeypatch.setattr(for_you, "radar_pool", lambda *args: [])
    monkeypatch.setattr(digest, "coming_up", lambda *args, **kwargs: {
        "matches": [], "popular": [{"title": "Arrival", "label": "Movie", "url": "/release-radar", "date": None}],
    })
    users = []
    for index in range(3):
        user = models.User(username=f"quota{index}", email=f"quota{index}@example.com",
                           hashed_password="x", is_active=True, is_verified=True)
        db_session.add(user)
        db_session.flush()
        db_session.add(models.EmailDigestSubscription(user_id=user.id, token=f"quota-token-{index}"))
        users.append(user.id)
    db_session.commit()
    return now, users


def test_digests_respect_recent_campaign_sends(db_session, digest_members):
    now, users = digest_members
    for uid in users[:2]:
        db_session.add(models.EmailCampaignSend(campaign_key="quota", user_id=uid, status="sent", sent_at=now))
    db_session.commit()
    sent = []
    async def sender(to, *args):
        sent.append(to)
    result = asyncio.run(digest.send_due_digests(TestingSessionLocal, now=now, sender=sender))
    assert len(sent) == result["sent"] == 1
    assert result["limited"] == 2


def test_campaign_sends_outside_rolling_window_do_not_reduce_quota(db_session, digest_members):
    now, users = digest_members
    for uid in users:
        db_session.add(models.EmailCampaignSend(campaign_key="old", user_id=uid, status="sent",
                                               sent_at=now - timedelta(hours=25)))
    db_session.commit()
    sent = []
    async def sender(to, *args):
        sent.append(to)
    result = asyncio.run(digest.send_due_digests(TestingSessionLocal, now=now, sender=sender))
    assert len(sent) == result["sent"] == 3


def test_overlapping_digest_runs_do_not_send_from_stale_due_list(db_session, digest_members, monkeypatch):
    now, _ = digest_members
    monkeypatch.setenv("SHARED_DAILY_CAP", "80")
    sent = []
    async def second_sender(to, *args):
        sent.append(to)
    async def first_sender(to, *args):
        sent.append(to)
        if len(sent) == 1:
            await digest.send_due_digests(TestingSessionLocal, now=now, sender=second_sender)
    asyncio.run(digest.send_due_digests(TestingSessionLocal, now=now, sender=first_sender))
    assert len(sent) == len(set(sent)) == 3


def test_overlapping_digest_runs_cannot_overspend_shared_quota(db_session, digest_members, monkeypatch):
    now, _ = digest_members
    monkeypatch.setenv("SHARED_DAILY_CAP", "1")
    sent = []
    async def nested_sender(to, *args):
        sent.append(to)
    async def sender(to, *args):
        sent.append(to)
        if len(sent) == 1:
            await digest.send_due_digests(TestingSessionLocal, now=now, sender=nested_sender)
    asyncio.run(digest.send_due_digests(TestingSessionLocal, now=now, sender=sender))
    assert len(sent) == 1
