"""Push sending: Expo ticket errors must be logged (not silently dropped) and
only genuinely dead tokens removed. Expo's HTTP API is faked."""

import httpx
import pytest
from sqlalchemy.orm import Session

from app.models.push_token import PushToken
from app.services import push
from tests.test_phase_13_cart_orders import _customer

TOKEN = "ExponentPushToken[abcdefghijklmnopqrstuv]"


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture
def captured(monkeypatch):
    logs = []
    monkeypatch.setattr(push.logger, "warning", lambda msg, *a, **k: logs.append(("warning", msg % a)))
    monkeypatch.setattr(push.logger, "info", lambda msg, *a, **k: logs.append(("info", msg % a)))
    return logs


def _register(db: Session, user_id: int) -> None:
    db.add(PushToken(user_id=user_id, token=TOKEN, platform="android"))
    db.commit()


def test_credential_error_is_logged_and_token_is_kept(db_session: Session, monkeypatch, captured) -> None:
    user, _ = _customer(db_session, "PS1")
    _register(db_session, user.id)
    ticket = {"data": [{"status": "error", "message": "Unable to retrieve the FCM server key", "details": {"error": "InvalidCredentials"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(ticket))

    push._send(user.id, "t", "b", {"orderId": 1})

    assert any("PUSH_TICKET_ERROR" in m and "InvalidCredentials" in m for _l, m in captured), captured
    db_session.expire_all()
    assert db_session.query(PushToken).count() == 1  # a credentials problem must not delete the token


def test_device_not_registered_removes_only_that_token(db_session: Session, monkeypatch, captured) -> None:
    user, _ = _customer(db_session, "PS2")
    _register(db_session, user.id)
    ticket = {"data": [{"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(ticket))

    push._send(user.id, "t", "b", {"orderId": 1})

    db_session.expire_all()
    assert db_session.query(PushToken).count() == 0
    assert any("DeviceNotRegistered" in m for _l, m in captured)


def test_missing_registration_is_reported(db_session: Session, monkeypatch, captured) -> None:
    user, _ = _customer(db_session, "PS3")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("must not call Expo without tokens"))

    push._send(user.id, "t", "b", {"orderId": 1})

    assert any("PUSH_NO_TOKENS" in m for _l, m in captured)


def test_ok_ticket_logs_no_error(db_session: Session, monkeypatch, captured) -> None:
    user, _ = _customer(db_session, "PS4")
    _register(db_session, user.id)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp({"data": [{"status": "ok", "id": "x"}]}))

    push._send(user.id, "t", "b", {"orderId": 1})

    assert not any("PUSH_TICKET_ERROR" in m for _l, m in captured)
    db_session.expire_all()
    assert db_session.query(PushToken).count() == 1
