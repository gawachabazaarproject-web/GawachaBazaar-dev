"""Admin and mobile carry a copy of the conversion table; it must never drift from
the backend's (app/services/units.py), and the two copies must be identical."""

import re
from pathlib import Path

from app.services.units import UNITS

ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / "Admin" / "lib" / "units.ts"
MOBILE = ROOT / "mobile" / "src" / "utils" / "units.ts"

_ROW = re.compile(
    r'(\w+): \{ dimension: "(\w+)", factor: (\d+), baseLabel: "([^"]+)", label: "([^"]+)", inputLabel: "([^"]+)" \}'
)


def _table(path: Path) -> dict[str, tuple[str, int, str, str]]:
    return {m[1]: (m[2], int(m[3]), m[4], m[5]) for m in _ROW.finditer(path.read_text(encoding="utf-8"))}


def test_the_two_client_copies_are_identical() -> None:
    assert ADMIN.read_text(encoding="utf-8") == MOBILE.read_text(encoding="utf-8")


def test_client_table_matches_the_backend_exactly() -> None:
    backend = {u: (i.dimension, i.factor, i.base_label, i.label) for u, i in UNITS.items()}
    assert _table(ADMIN) == backend
    assert len(backend) >= 8
