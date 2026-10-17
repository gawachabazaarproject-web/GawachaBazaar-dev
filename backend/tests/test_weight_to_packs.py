"""Receiving stock by weight: 1 kg of a 250 g variant is 4 packs."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.exceptions.base import BusinessValidationError
from app.schemas.admin_inventory import ReceiveStockRequest
from app.services.stock_pool import weight_to_packs


def _variant(quantity: str, unit: str):
    return SimpleNamespace(quantity=Decimal(quantity), unit=unit)


def test_one_kg_of_250g_packs_is_four_packs():
    assert weight_to_packs(_variant("250", "G"), Decimal("1"), "KG") == Decimal("4.000")


def test_kg_into_a_kg_variant_and_grams_into_a_kg_variant():
    assert weight_to_packs(_variant("1", "KG"), Decimal("5"), "KG") == Decimal("5.000")
    assert weight_to_packs(_variant("1", "KG"), Decimal("500"), "G") == Decimal("0.500")


def test_partial_pack_is_kept_as_a_fraction():
    assert weight_to_packs(_variant("250", "G"), Decimal("1.1"), "KG") == Decimal("4.400")


def test_unit_family_mismatch_is_rejected():
    with pytest.raises(BusinessValidationError):
        weight_to_packs(_variant("250", "G"), Decimal("1"), "L")
    with pytest.raises(BusinessValidationError):
        weight_to_packs(_variant("1", "BOX"), Decimal("1"), "KG")


def test_request_needs_packs_or_amount_not_both():
    base = {"variant_id": 1, "location_id": 1}
    assert ReceiveStockRequest(**base, quantity="4").quantity == Decimal("4")
    assert ReceiveStockRequest(**base, amount="1", amount_unit="KG").amount_unit == "KG"
    with pytest.raises(ValidationError):
        ReceiveStockRequest(**base)
    with pytest.raises(ValidationError):
        ReceiveStockRequest(**base, quantity="4", amount="1", amount_unit="KG")
    with pytest.raises(ValidationError):
        ReceiveStockRequest(**base, amount="1")
