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


def test_same_event_key_sends_once(db_session: Session, monkeypatch, captured) -> None:
    user, _ = _customer(db_session, "PS5")
    _register(db_session, user.id)
    calls = []

    def fake_post(*a, **k):
        calls.append(k["json"])
        return _Resp({"data": [{"status": "ok", "id": "x"}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    push._send(user.id, "t", "b", {"type": "ORDER_CONFIRMED", "orderId": 1}, "order:1:CONFIRMED")
    push._send(user.id, "t", "b", {"type": "ORDER_CONFIRMED", "orderId": 1}, "order:1:CONFIRMED")
    push._send(user.id, "t", "b", {"type": "ORDER_PACKED", "orderId": 1}, "fulfillment:1:PACKED")

    assert len(calls) == 2  # the repeated key was skipped, a different event still goes out
    assert any("PUSH_DUPLICATE_SKIPPED" in m for _l, m in captured)


def test_notify_user_status_payload_has_type_and_order_id(monkeypatch) -> None:
    started = []

    class _T:
        def __init__(self, target, args, daemon):
            started.append(args)

        def start(self):
            pass

    monkeypatch.setattr(push.threading, "Thread", _T)
    push.notify_user_status(resource="fulfillment", order_id=7, user_id=3, new_status="OUT_FOR_DELIVERY")
    push.notify_user_status(resource="fulfillment", order_id=7, user_id=3, new_status="ASSIGNED")  # no message

    assert len(started) == 1
    _uid, _title, _body, data, key = started[0]
    assert data == {"type": "OUT_FOR_DELIVERY", "orderId": 7}
    assert key == "fulfillment:7:OUT_FOR_DELIVERY"


def test_register_reassigns_token_without_duplicating(db_session: Session) -> None:
    a, _ = _customer(db_session, "PS6")
    b, _ = _customer(db_session, "PS7")
    push.register_token(db_session, a.id, TOKEN, "android")
    push.register_token(db_session, a.id, TOKEN, "android")  # same user, same device
    assert db_session.query(PushToken).count() == 1
    push.register_token(db_session, b.id, TOKEN, "android")  # device now used by another account
    rows = db_session.query(PushToken).all()
    assert len(rows) == 1 and rows[0].user_id == b.id


@pytest.mark.parametrize(
    ("resource", "status", "expected"),
    [
        ("order", "PENDING", "ORDER_PLACED"),
        ("payment", "PAID", "PAYMENT_RECEIVED"),
        ("order", "CONFIRMED", "ORDER_CONFIRMED"),
        ("fulfillment", "PACKED", "ORDER_PACKED"),
        ("fulfillment", "OUT_FOR_DELIVERY", "OUT_FOR_DELIVERY"),
        ("order", "COMPLETED", "ORDER_DELIVERED"),
        ("order", "CANCELLED", "ORDER_CANCELLED"),
        ("refund", "APPROVED", "REFUND_INITIATED"),
        ("refund", "REFUNDED", "REFUND_COMPLETED"),
    ],
)
def test_every_customer_lifecycle_event_has_a_push(monkeypatch, resource, status, expected) -> None:
    started = []
    monkeypatch.setattr(push.threading, "Thread", lambda target, args, daemon: type("T", (), {"start": lambda s: started.append(args)})())
    push.notify_user_status(resource=resource, order_id=5, user_id=1, new_status=status)
    assert [a[3]["type"] for a in started] == [expected]


def test_firebase_uses_render_secret_file_when_env_is_empty(monkeypatch, tmp_path) -> None:
    from app.core import firebase
    from app.core.config import settings

    key_file = tmp_path / "google-services-account.json"
    key_file.write_text("{}")
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "demo-project")
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setattr(firebase, "RENDER_SECRET_FILE", str(key_file))
    loaded = []

    import firebase_admin
    from firebase_admin import credentials

    monkeypatch.setattr(credentials, "Certificate", lambda src: loaded.append(src) or object())
    monkeypatch.setattr(firebase_admin, "get_app", lambda name: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda cred, options, name: "app")

    assert firebase.FirebaseAdminGateway()._get_app() == "app"
    assert loaded == [str(key_file)]
