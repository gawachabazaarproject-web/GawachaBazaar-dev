# ruff: noqa: F811  (pytest fixtures imported from another test module)
"""Refund integrity under concurrency, with real PostgreSQL row locks and real
threads; only Razorpay's REST API is faked. Business rules asserted:
  * however many times / however simultaneously an admin processes a refund,
    Razorpay is asked to refund that payment at most once
  * a paid order cancelled by two actors at once yields exactly one refund
  * a refund can never exceed what was paid
"""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN
from app.models.refund import Refund
from tests.test_razorpay_payments import (  # noqa: F401 - razorpay is a pytest fixture
    FakeRazorpay,
    _start_online_payment,
    _webhook,
    razorpay,
)
from tests.test_phase_18_cancellation_refunds import _staff


def _paid_and_cancelled(client: TestClient, db_session: Session, razorpay: FakeRazorpay, tag: str):
    _user, headers, order, payment = _start_online_payment(client, db_session, tag)
    paid = razorpay.add_payment(payment["gateway_order_id"])
    body, wh = _webhook("payment.captured", paid)
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=wh).status_code == 200
    assert client.post(f"/api/v1/orders/{order.id}/cancel", json={}, headers=headers).status_code == 200
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(payment_id=payment["id"]).one()
    return headers, order, payment, paid, refund


def test_simultaneous_process_clicks_send_one_refund_to_razorpay(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    razorpay.refund_status = "pending"  # stays in flight, as in real life for a while
    _h, _order, _payment, paid, refund = _paid_and_cancelled(client, db_session, razorpay, "RF1")
    _a, admin = _staff(db_session, ADMIN, "RF1")
    assert client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin).status_code == 200

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(client.post, f"/api/v1/payments/refunds/{refund.id}/process", headers=admin)
            for _ in range(4)
        ]
        codes = sorted(f.result().status_code for f in futures)

    assert len(razorpay.refunds) == 1, f"{len(razorpay.refunds)} refunds sent to Razorpay for one payment"
    assert razorpay.refunds[0]["payment_id"] == paid["id"]
    assert codes.count(200) == 1 and all(c in (200, 409) for c in codes), codes


def test_processing_an_already_refunded_refund_never_sends_a_second_one(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _h, _order, _payment, _paid, refund = _paid_and_cancelled(client, db_session, razorpay, "RF2")
    _a, admin = _staff(db_session, ADMIN, "RF2")
    client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin)
    first = client.post(f"/api/v1/payments/refunds/{refund.id}/process", headers=admin)
    assert first.status_code == 200 and first.json()["status"] == "REFUNDED"

    again = client.post(f"/api/v1/payments/refunds/{refund.id}/process", headers=admin)
    assert again.status_code in (409, 422), again.text
    assert len(razorpay.refunds) == 1


def test_concurrent_cancellation_by_customer_and_admin_creates_one_refund(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    from tests.test_phase_14_payments import _customer  # noqa: F401
    from tests.test_razorpay_payments import _start_online_payment as start

    _user, headers, order, payment = start(client, db_session, "RF3")
    paid = razorpay.add_payment(payment["gateway_order_id"])
    body, wh = _webhook("payment.captured", paid)
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=wh).status_code == 200
    _a, admin = _staff(db_session, ADMIN, "RF3")

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(client.post, f"/api/v1/orders/{order.id}/cancel", json={}, headers=headers)
        f2 = pool.submit(client.post, f"/api/v1/orders/admin/{order.id}/cancel", json={}, headers=admin)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code < 500 and r2.status_code < 500, (r1.text, r2.text)
    db_session.expire_all()
    refunds = db_session.query(Refund).filter_by(payment_id=payment["id"]).all()
    assert len(refunds) == 1
    assert refunds[0].amount <= db_session.get(type(refunds[0].payment), payment["id"]).amount
