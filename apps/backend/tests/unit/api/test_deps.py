"""Unit tests for app.api.deps."""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.api.deps import get_db


def test_get_db_yields_session_and_closes_after_consumption():
    """The dependency yields a Session and closes it once the generator is exhausted."""
    fake_session = MagicMock(spec=Session)
    with patch("app.api.deps.SessionLocal", return_value=fake_session):
        gen = get_db()
        yielded = next(gen)
        assert yielded is fake_session
        fake_session.close.assert_not_called()
        # Drain the generator — simulates FastAPI ending the request.
        next(gen, None)
        fake_session.close.assert_called_once()


def test_get_db_closes_session_when_consumer_raises():
    """Session.close() runs even if the consumer raises mid-request (finally clause)."""
    fake_session = MagicMock(spec=Session)
    with patch("app.api.deps.SessionLocal", return_value=fake_session):
        gen = get_db()
        next(gen)
        try:
            gen.throw(RuntimeError("handler failed"))
        except RuntimeError:
            pass
        fake_session.close.assert_called_once()


def test_get_db_creates_new_session_per_call():
    """Each invocation builds its own session — no shared state across requests."""
    sessions = [MagicMock(spec=Session), MagicMock(spec=Session)]
    with patch("app.api.deps.SessionLocal", side_effect=sessions):
        first = next(get_db())
        second = next(get_db())
        assert first is sessions[0]
        assert second is sessions[1]
        assert first is not second
