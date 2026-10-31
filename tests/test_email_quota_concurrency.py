"""Real SQLite connections exercise quota reservations across scheduler workers."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier, Event, Lock, local
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app import announcements, digest, email_quota, for_you, models, review_spotlight
from app.database import Base


@pytest.fixture
def quota_store(tmp_path, monkeypatch):
    """A file database and fresh connections, unlike the shared test StaticPool."""
    path = tmp_path / "email-quota.sqlite"
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    now = datetime(2026, 10, 10, 12)
    monkeypatch.setenv("SHARED_DAILY_CAP", "1")
    monkeypatch.setenv("DIGEST_DAILY_LIMIT", "10")
    monkeypatch.setenv("ANNOUNCEMENT_DAILY_LIMIT", "10")
    monkeypatch.setattr(for_you, "radar_pool", lambda *args, **kwargs: [])
    report = {
        "matches": [{"title": "Arrival", "label": "Movie", "url": "/release-radar",
                     "date": None, "reason": "A title from your library"}],
        "popular": [],
    }
    monkeypatch.setattr(for_you, "coming_up", lambda *args, **kwargs: report)
    monkeypatch.setattr(digest, "coming_up", lambda *args, **kwargs: report)
    monkeypatch.setattr(review_spotlight, "build", lambda *args, **kwargs: None)
    with factory() as db:
        users = [models.User(username=f"concurrent_{i}", email=f"concurrent_{i}@example.test",
                             hashed_password="unused-test-hash", is_active=True, is_verified=True)
                 for i in range(2)]
        db.add_all(users)
        db.flush()
        user_ids = [user.id for user in users]
        emails = [user.email for user in users]
        db.add_all(models.EmailDigestSubscription(user_id=user.id, token=f"concurrent-token-{i}")
                   for i, user in enumerate(users))
        db.add(models.EmailCampaign(key=announcements.CAMPAIGN_KEY, status="sending", started_at=now))
        db.commit()
    try:
        yield SimpleNamespace(factory=factory, now=now, user_ids=user_ids, emails=emails)
    finally:
        engine.dispose()


def run_scheduler(kind, store, sender, now=None):
    scheduler = digest.send_due_digests if kind == "digest" else announcements.send_due
    return asyncio.run(scheduler(store.factory, now=now or store.now, sender=sender))


def reserved_counts(store):
    since = store.now - timedelta(hours=24)
    with store.factory() as db:
        return (
            db.query(models.EmailDigestSubscription).filter(
                models.EmailDigestSubscription.last_sent_at >= since).count(),
            db.query(models.EmailCampaignSend).filter(models.EmailCampaignSend.sent_at >= since).count(),
        )


@pytest.mark.parametrize("first_kind,second_kind", [
    ("digest", "digest"), ("digest", "campaign"),
    ("campaign", "digest"), ("campaign", "campaign"),
])
def test_inflight_delivery_reserves_shared_quota_across_connections(quota_store, first_kind, second_kind):
    """A second worker cannot spend the reservation while the provider awaits."""
    started, release = Event(), Event()
    attempts = []

    async def holding_sender(to, *args):
        attempts.append((first_kind, to))
        started.set()
        if not release.wait(10):
            raise TimeoutError("Test provider was not released")

    async def other_sender(to, *args):
        attempts.append((second_kind, to))

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(run_scheduler, first_kind, quota_store, holding_sender)
        try:
            assert started.wait(10), "The first scheduler never reached the provider"
            # Query with a third connection while the first sender is still waiting.
            assert sum(reserved_counts(quota_store)) == 1
            second = workers.submit(run_scheduler, second_kind, quota_store, other_sender)
            second_stats = second.result(timeout=10)
            assert second_stats["sent"] == 0
            assert second_stats["limited"]
            assert len(attempts) == 1
        finally:
            release.set()
        assert first.result(timeout=10)["sent"] == 1
    assert sum(reserved_counts(quota_store)) == 1


@pytest.mark.parametrize("kinds", [("digest", "digest"), ("digest", "campaign")])
def test_simultaneous_budget_reservations_cannot_overspend_sqlite(quota_store, monkeypatch, kinds):
    """Both workers observe initial allowance before competing for the writer lock."""
    barrier = Barrier(2)
    state = local()
    real_lock = email_quota.lock_email_budget
    attempts = []
    attempts_lock = Lock()

    def synchronized_lock(db):
        if not getattr(state, "reached_budget", False):
            state.reached_budget = True
            barrier.wait(timeout=10)
        real_lock(db)

    monkeypatch.setattr(email_quota, "lock_email_budget", synchronized_lock)

    async def sender(to, *args):
        with attempts_lock:
            attempts.append(to)

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(run_scheduler, kind, quota_store, sender) for kind in kinds]
        stats = [future.result(timeout=15) for future in futures]
    assert sum(item["sent"] for item in stats) == len(attempts) == 1
    assert sum(reserved_counts(quota_store)) == 1


def test_failed_digest_releases_reservation_for_campaign_after_overlap(quota_store):
    """A failed provider attempt restores digest history and opens the shared slot."""
    previous_sent = quota_store.now - timedelta(days=14)
    with quota_store.factory() as db:
        db.query(models.EmailDigestSubscription).filter_by(user_id=quota_store.user_ids[1]).delete()
        subscription = db.query(models.EmailDigestSubscription).filter_by(user_id=quota_store.user_ids[0]).one()
        subscription.last_sent_at = previous_sent
        db.commit()
    started, release = Event(), Event()
    attempts = []

    async def failing_sender(to, *args):
        attempts.append(("failed-digest", to))
        started.set()
        if not release.wait(10):
            raise TimeoutError("Test provider was not released")
        raise RuntimeError("Simulated provider rejection")

    async def campaign_sender(to, *args):
        attempts.append(("campaign", to))

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(run_scheduler, "digest", quota_store, failing_sender)
        try:
            assert started.wait(10)
            assert reserved_counts(quota_store) == (1, 0)
            blocked = workers.submit(run_scheduler, "campaign", quota_store, campaign_sender).result(timeout=10)
            assert blocked["limited"] and blocked["sent"] == 0
        finally:
            release.set()
        failed = first.result(timeout=10)
    assert failed["failed"] == 1 and failed["sent"] == 0
    with quota_store.factory() as db:
        subscription = db.query(models.EmailDigestSubscription).one()
        assert subscription.last_sent_at == previous_sent
        # Preserve the weekly check cadence; an SMTP failure does not trigger an immediate resend.
        assert subscription.last_checked_at == quota_store.now
        assert announcements.allowance(db, quota_store.now) == 1
    delivered = run_scheduler("campaign", quota_store, campaign_sender)
    assert delivered["sent"] == 1
    assert [kind for kind, _ in attempts] == ["failed-digest", "campaign"]
    assert reserved_counts(quota_store) == (0, 1)


def test_failed_digest_does_not_consume_next_subscribers_slot(quota_store):
    delivered = []

    async def sender(to, *args):
        if to == quota_store.emails[0]:
            raise RuntimeError("Simulated provider rejection")
        delivered.append(to)

    stats = run_scheduler("digest", quota_store, sender)
    assert stats["failed"] == stats["sent"] == 1
    assert delivered == [quota_store.emails[1]]
    with quota_store.factory() as db:
        subscriptions = db.query(models.EmailDigestSubscription).order_by(models.EmailDigestSubscription.id).all()
        assert subscriptions[0].last_sent_at is None
        assert subscriptions[1].last_sent_at == quota_store.now
    assert reserved_counts(quota_store) == (1, 0)


def test_failed_campaign_remains_recorded_without_retrying_recipient(quota_store):
    """Campaign failures retain the existing once-per-recipient/attempt-budget behavior."""
    attempted = []

    async def failing_sender(to, *args):
        attempted.append(to)
        raise RuntimeError("Simulated provider rejection")

    stats = run_scheduler("campaign", quota_store, failing_sender)
    assert stats["failed"] == 1 and stats["sent"] == 0
    with quota_store.factory() as db:
        failed = db.query(models.EmailCampaignSend).one()
        assert failed.user_id == quota_store.user_ids[0]
        assert failed.status == "failed"
        assert announcements.allowance(db, quota_store.now) == 0
    assert run_scheduler("digest", quota_store, failing_sender)["sent"] == 0
    assert attempted == [quota_store.emails[0]]

    async def successful_sender(to, *args):
        attempted.append(to)

    later = run_scheduler("campaign", quota_store, successful_sender, now=quota_store.now + timedelta(hours=25))
    assert later["sent"] == 1
    assert attempted == quota_store.emails
