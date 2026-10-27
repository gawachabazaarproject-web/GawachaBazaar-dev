"""The single backend conversion layer (app/services/units.py): exhaustive and
pure. Nothing here touches the database."""

from decimal import Decimal as D

import pytest

from app.exceptions.base import BusinessValidationError
from app.services import units as U

MASS_G = [1, 5, 10, 50, 100, 250, 500, 750, 1000, 1500, 3000, 5000]
VOLUME_ML = MASS_G
COUNT = [1, 2, 5, 6, 10, 12, 24, 36, 100]

MASS_SIZES = [("G", "1"), ("G", "10"), ("G", "50"), ("G", "100"), ("G", "250"), ("G", "500"),
              ("KG", "1"), ("KG", "1.5"), ("KG", "3"), ("KG", "5")]
VOLUME_SIZES = [("ML", "10"), ("ML", "50"), ("ML", "100"), ("ML", "250"), ("ML", "500"),
                ("L", "1"), ("L", "1.5"), ("L", "3"), ("L", "5")]
COUNT_SIZES = [("UNIT", "1"), ("UNIT", "2"), ("UNIT", "6"), ("UNIT", "12"), ("DOZEN", "1"), ("DOZEN", "2"), ("DOZEN", "3")]


@pytest.mark.parametrize(
    "unit, qty, dimension, base",
    [
        ("G", "1", "MASS", 1), ("KG", "1", "MASS", 1000), ("KG", "1.5", "MASS", 1500), ("KG", "0.25", "MASS", 250),
        ("ML", "250", "VOLUME", 250), ("L", "1", "VOLUME", 1000), ("L", "1.5", "VOLUME", 1500),
        ("UNIT", "1", "COUNT", 1), ("UNIT", "6", "COUNT", 6), ("DOZEN", "1", "COUNT", 12),
        ("DOZEN", "2", "COUNT", 24), ("DOZEN", "0.5", "COUNT", 6),
        ("BOX", "1", "BOX", 1), ("PACK", "6", "PACK", 6),
    ],
)
def test_size_and_dimension(unit, qty, dimension, base) -> None:
    assert U.dimension_of(unit) == dimension
    assert U.size_base(D(qty), unit) == base


@pytest.mark.parametrize("sizes", [MASS_SIZES, VOLUME_SIZES, COUNT_SIZES])
def test_every_listed_size_is_a_positive_whole_number_of_base_units(sizes) -> None:
    for unit, qty in sizes:
        size = U.size_base(D(qty), unit)
        assert isinstance(size, int) and size > 0


@pytest.mark.parametrize("amount", MASS_G)
@pytest.mark.parametrize("size", MASS_SIZES)
def test_mass_matrix_packs_are_floor_and_never_exceed_the_stock(amount, size) -> None:
    sz = U.size_base(D(size[1]), size[0])
    packs = U.packs_for(amount, sz)
    assert packs * sz <= amount < (packs + 1) * sz


@pytest.mark.parametrize("amount", VOLUME_ML)
@pytest.mark.parametrize("size", VOLUME_SIZES)
def test_volume_matrix(amount, size) -> None:
    sz = U.size_base(D(size[1]), size[0])
    packs = U.packs_for(amount, sz)
    assert packs * sz <= amount < (packs + 1) * sz


@pytest.mark.parametrize("amount", COUNT)
@pytest.mark.parametrize("size", COUNT_SIZES)
def test_count_matrix(amount, size) -> None:
    sz = U.size_base(D(size[1]), size[0])
    packs = U.packs_for(amount, sz)
    assert packs * sz <= amount < (packs + 1) * sz


@pytest.mark.parametrize("unit", ["KG", "G", "L", "ML", "UNIT", "DOZEN"])
@pytest.mark.parametrize("amount", ["1", "2", "5", "7", "12", "100", "1.5", "0.5", "0.25"])
def test_to_base_round_trips_exactly_or_refuses(unit, amount) -> None:
    value = D(amount)
    scaled = value * U.UNITS[unit].factor
    if scaled == scaled.to_integral_value():
        base = U.to_base(value, unit)
        assert U.base_to_amount(base, unit) == value  # no information lost either way
    else:
        with pytest.raises(BusinessValidationError):
            U.to_base(value, unit)  # never silently rounded


def test_dozen_conversions_are_exact_in_both_directions() -> None:
    assert U.to_base(D("1"), "DOZEN") == 12
    assert U.to_base(D("2"), "DOZEN") == 24
    assert U.to_base(D("0.5"), "DOZEN") == 6
    assert U.base_to_amount(24, "DOZEN") == D("2")
    assert U.to_base(D("5"), "UNIT") == 5  # 5 pieces is 5, never 0.416 dozen
    with pytest.raises(BusinessValidationError):
        U.to_base(D("0.4"), "DOZEN")  # 4.8 pieces


@pytest.mark.parametrize("a, b", [("KG", "L"), ("G", "ML"), ("KG", "UNIT"), ("DOZEN", "ML"), ("L", "DOZEN"),
                                  ("BOX", "KG"), ("PACK", "BOX"), ("UNIT", "PACK")])
def test_cross_dimension_conversion_is_refused(a, b) -> None:
    with pytest.raises(BusinessValidationError):
        U.ensure_same_dimension(a, b)


@pytest.mark.parametrize("a, b", [("KG", "G"), ("L", "ML"), ("DOZEN", "UNIT"), ("BOX", "BOX")])
def test_same_dimension_conversion_is_allowed(a, b) -> None:
    U.ensure_same_dimension(a, b)


def test_box_and_pack_are_their_own_unit_with_no_invented_conversion() -> None:
    assert U.UNITS["BOX"].factor == 1 and U.UNITS["PACK"].factor == 1
    assert U.dimension_of("BOX") != U.dimension_of("PACK")
    assert U.size_base(D("12"), "BOX") == 12


def test_unknown_unit_and_non_positive_size_are_refused() -> None:
    with pytest.raises(BusinessValidationError):
        U.dimension_of("BUSHEL")
    with pytest.raises(BusinessValidationError):
        U.size_base(D("0"), "KG")


def test_display_text_is_for_humans_not_for_accounting() -> None:
    assert U.amount_text(68999, "MASS") == "68.999 kg"
    assert U.amount_text(12, "COUNT") == "12 pcs"
    assert U.amount_text(2500, "VOLUME") == "2.5 L"
    assert U.packs_exact(2750, 3000) == D("0.917")  # display only; the lot holds 2750


def test_the_exact_cases_from_the_brief() -> None:
    assert U.packs_for(68999, 250) == 275 and U.packs_for(68999, 1000) == 68  # case D
    assert [U.packs_for(1000, s) for s in (250, 500, 1000)] == [4, 2, 1]  # case E
