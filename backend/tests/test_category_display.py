"""Category storefront display settings: tile colour, badge, homepage/catalog
visibility, admin summary counts and duplication."""

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, CUSTOMER
from app.models.category import Category
from app.models.product import Product
from app.schemas.catalog import CreateCategoryRequest, UpdateCategoryRequest, validate_tile_color
from tests.test_phase_10_catalog import _auth_headers, _create_category, _create_user_with_role

CAT = "/api/v1/catalog/categories"


def _admin(db_session: Session) -> dict[str, str]:
    return _auth_headers(db_session, _create_user_with_role(db_session, ADMIN, "cat-admin@example.com"))


# ---------------------------------------------------------------- validation


@pytest.mark.parametrize("value", ["#E4EEDC", "#fff7e6", "#F6F0E0"])
def test_light_tile_colours_are_accepted_and_normalised(value: str) -> None:
    assert validate_tile_color(value) == value.upper()


@pytest.mark.parametrize("value", ["#0B2D20", "#000000", "#143326", "#3A3A3A"])
def test_dark_tile_colours_are_rejected_for_contrast(value: str) -> None:
    with pytest.raises(ValueError, match="too dark"):
        validate_tile_color(value)


@pytest.mark.parametrize("value", ["red", "#12345", "#GGGGGG", "123456"])
def test_malformed_colours_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="#RRGGBB"):
        validate_tile_color(value)


def test_blank_colour_and_badge_clear_the_setting() -> None:
    req = UpdateCategoryRequest(background_color="", badge_text="   ")
    assert req.background_color is None and req.badge_text is None


def test_visibility_flags_cannot_be_nulled() -> None:
    with pytest.raises(ValueError):
        UpdateCategoryRequest(show_on_homepage=None)


def test_create_defaults_keep_existing_behaviour() -> None:
    req = CreateCategoryRequest(name="Dairy", slug="dairy")
    assert req.show_on_homepage is True and req.show_in_catalog is True and req.is_featured is False


# ---------------------------------------------------------------- admin API


def test_admin_can_set_display_fields_and_they_round_trip(client: TestClient, db_session: Session) -> None:
    headers = _admin(db_session)
    created = client.post(
        CAT,
        headers=headers,
        json={"name": "Dairy", "slug": "dairy", "background_color": "#fff7e6", "badge_text": " New ", "is_featured": True},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["background_color"] == "#FFF7E6"
    assert body["badge_text"] == "New"
    assert body["is_featured"] is True and body["show_on_homepage"] is True

    patched = client.patch(f"{CAT}/{body['id']}", headers=headers, json={"show_on_homepage": False})
    assert patched.status_code == 200
    assert patched.json()["show_on_homepage"] is False
    assert patched.json()["background_color"] == "#FFF7E6"  # untouched by a partial update

    detail = client.get(f"{CAT}/admin/{body['id']}", headers=headers).json()
    assert detail["show_on_homepage"] is False and detail["badge_text"] == "New"


def test_api_rejects_a_dark_background(client: TestClient, db_session: Session) -> None:
    res = client.post(CAT, headers=_admin(db_session), json={"name": "X", "slug": "x", "background_color": "#000000"})
    assert res.status_code == 422


def test_customer_cannot_change_display_settings(client: TestClient, db_session: Session) -> None:
    category = _create_category(db_session)
    customer = _auth_headers(db_session, _create_user_with_role(db_session, CUSTOMER, "cust-cat@example.com"))
    res = client.patch(f"{CAT}/{category.id}", headers=customer, json={"show_on_homepage": False})
    assert res.status_code == 403
    assert client.post(f"{CAT}/{category.id}/duplicate", headers=customer).status_code == 403
    assert client.get(f"{CAT}/admin/summary", headers=customer).status_code == 403
    assert client.post(f"{CAT}/{category.id}/duplicate").status_code in (401, 403)


# ---------------------------------------------------------------- public visibility


def test_homepage_flag_controls_the_home_grid_only(client: TestClient, db_session: Session) -> None:
    _create_category(db_session, name="Fruits", slug="fruits")
    hidden = _create_category(db_session, name="Clothing", slug="clothing")
    hidden.show_on_homepage = False
    db_session.commit()

    home = client.get(CAT, params={"homepage": "true"}).json()
    assert [c["slug"] for c in home["items"]] == ["fruits"]
    full = client.get(CAT).json()
    assert {c["slug"] for c in full["items"]} == {"fruits", "clothing"}


def test_catalog_flag_hides_from_view_all_and_inactive_never_shows(client: TestClient, db_session: Session) -> None:
    _create_category(db_session, name="A", slug="a")
    off = _create_category(db_session, name="B", slug="b")
    off.show_in_catalog = False
    draft = _create_category(db_session, name="C", slug="c", status="INACTIVE")
    draft.show_on_homepage = True
    db_session.commit()

    assert {c["slug"] for c in client.get(CAT).json()["items"]} == {"a"}
    assert {c["slug"] for c in client.get(CAT, params={"homepage": "true"}).json()["items"]} == {"a", "b"}


def test_homepage_order_follows_admin_sort_order(client: TestClient, db_session: Session) -> None:
    headers = _admin(db_session)
    a = _create_category(db_session, name="A", slug="a")
    b = _create_category(db_session, name="B", slug="b")
    assert client.put(f"{CAT}/reorder", headers=headers, json={"ids": [b.id, a.id]}).status_code == 204
    items = client.get(CAT, params={"homepage": "true"}).json()["items"]
    assert [c["slug"] for c in items] == ["b", "a"]


def test_change_is_visible_without_stale_cache(client: TestClient, db_session: Session) -> None:
    headers = _admin(db_session)
    cat = _create_category(db_session, name="Fruits", slug="fruits")
    assert len(client.get(CAT, params={"homepage": "true"}).json()["items"]) == 1
    client.patch(f"{CAT}/{cat.id}", headers=headers, json={"show_on_homepage": False})
    assert client.get(CAT, params={"homepage": "true"}).json()["items"] == []


# ---------------------------------------------------------------- summary / filter / duplicate


def test_summary_counts_come_from_the_database(client: TestClient, db_session: Session) -> None:
    headers = _admin(db_session)
    _create_category(db_session, name="A", slug="a")
    b = _create_category(db_session, name="B", slug="b")
    b.show_on_homepage = False
    _create_category(db_session, name="C", slug="c", status="INACTIVE")
    _create_category(db_session, name="D", slug="d", status="ARCHIVED")
    db_session.commit()

    s = client.get(f"{CAT}/admin/summary", headers=headers).json()
    assert s == {"total": 3, "active": 2, "homepage": 1, "inactive": 1, "without_products": 3}


def test_admin_list_filters_by_homepage_flag(client: TestClient, db_session: Session) -> None:
    headers = _admin(db_session)
    _create_category(db_session, name="A", slug="a")
    b = _create_category(db_session, name="B", slug="b")
    b.show_on_homepage = False
    db_session.commit()
    on = client.get(f"{CAT}/admin", headers=headers, params={"show_on_homepage": "true"}).json()
    off = client.get(f"{CAT}/admin", headers=headers, params={"show_on_homepage": "false"}).json()
    assert [c["slug"] for c in on["items"]] == ["a"]
    assert [c["slug"] for c in off["items"]] == ["b"]
    assert off["items"][0]["show_on_homepage"] is False


def test_duplicate_makes_a_hidden_draft_without_products(client: TestClient, db_session: Session) -> None:
    headers = _admin(db_session)
    src = _create_category(db_session, name="Dairy", slug="dairy")
    src.background_color = "#FFF7E6"
    src.badge_text = "New"
    product = Product(name="Milk", slug="milk", category_id=src.id, status="ACTIVE")
    db_session.add(product)
    db_session.commit()

    first = client.post(f"{CAT}/{src.id}/duplicate", headers=headers)
    second = client.post(f"{CAT}/{src.id}/duplicate", headers=headers)
    assert first.status_code == second.status_code == 201
    a, b = first.json(), second.json()
    assert a["slug"] == "dairy-copy" and b["slug"] == "dairy-copy-2"  # unique slugs
    assert a["status"] == "INACTIVE" and a["show_on_homepage"] is False and a["show_in_catalog"] is False
    assert a["background_color"] == "#FFF7E6" and a["badge_text"] == "New"
    assert db_session.query(Product).filter(Product.category_id == a["id"]).count() == 0
    assert db_session.query(Product).filter(Product.category_id == src.id).count() == 1
    assert db_session.get(Category, src.id).status == "ACTIVE"  # source untouched
    # a hidden draft never reaches customers
    assert {c["slug"] for c in client.get(CAT).json()["items"]} == {"dairy"}


def test_duplicate_of_missing_category_is_404(client: TestClient, db_session: Session) -> None:
    assert client.post(f"{CAT}/999999/duplicate", headers=_admin(db_session)).status_code == 404
