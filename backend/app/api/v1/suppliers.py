"""Supplier domain routes: internal staff only.

Suppliers are never customer-facing and never authenticate - there is no
public or customer route in this file. Basic supplier/product-link
management is ADMIN, HUB_STAFF, OPERATIONS (matching the existing
inventory.py convention for staff-wide operational data). Performance
evaluations are ADMIN-only per the spec ("supplier ratings are internal
procurement data... Admin-only") - HUB_STAFF/OPERATIONS can see and
maintain the supplier record itself but not rate it.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, HUB_STAFF, OPERATIONS
from app.dependencies.auth import require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.supplier import (
    MAX_PAGE_SIZE,
    CreateSupplierEvaluationRequest,
    CreateSupplierRequest,
    LinkSupplierProductRequest,
    SupplierEvaluationListResponse,
    SupplierEvaluationResponse,
    SupplierListResponse,
    SupplierPerformanceResponse,
    SupplierProductListResponse,
    SupplierProductResponse,
    SupplierResponse,
    UpdateSupplierProductRequest,
    UpdateSupplierRequest,
)
from app.services.supplier import SupplierService

router = APIRouter(
    dependencies=[Depends(require_roles(ADMIN, HUB_STAFF, OPERATIONS))]
)

_ADMIN_ONLY = Depends(require_roles(ADMIN))


# ---------------------------------------------------------------------------
# Supplier CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=SupplierResponse, status_code=201, summary="Create a supplier")
def create_supplier(
    payload: CreateSupplierRequest, db: Session = Depends(get_db)
) -> SupplierResponse:
    return SupplierService(db).create_supplier(payload)


@router.get("", response_model=SupplierListResponse, summary="List suppliers")
def list_suppliers(
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> SupplierListResponse:
    return SupplierService(db).list_suppliers(status_, page, page_size)


@router.get("/{supplier_id}", response_model=SupplierResponse, summary="Get a supplier")
def get_supplier(supplier_id: int, db: Session = Depends(get_db)) -> SupplierResponse:
    supplier = SupplierService(db).get_supplier_or_404(supplier_id)
    return SupplierResponse.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierResponse, summary="Update a supplier")
def update_supplier(
    supplier_id: int, payload: UpdateSupplierRequest, db: Session = Depends(get_db)
) -> SupplierResponse:
    return SupplierService(db).update_supplier(supplier_id, payload)


# ---------------------------------------------------------------------------
# Supplier <-> Product
# ---------------------------------------------------------------------------


@router.post(
    "/{supplier_id}/products",
    response_model=SupplierProductResponse,
    status_code=201,
    summary="Link a product this supplier can supply",
)
def link_supplier_product(
    supplier_id: int, payload: LinkSupplierProductRequest, db: Session = Depends(get_db)
) -> SupplierProductResponse:
    return SupplierService(db).link_product(supplier_id, payload)


@router.get(
    "/{supplier_id}/products",
    response_model=SupplierProductListResponse,
    summary="List products linked to a supplier",
)
def list_supplier_products(
    supplier_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> SupplierProductListResponse:
    return SupplierService(db).list_products(supplier_id, page, page_size)


@router.patch(
    "/{supplier_id}/products/{supplier_product_id}",
    response_model=SupplierProductResponse,
    summary="Update a supplier's product link (e.g. deactivate)",
)
def update_supplier_product(
    supplier_id: int,
    supplier_product_id: int,
    payload: UpdateSupplierProductRequest,
    db: Session = Depends(get_db),
) -> SupplierProductResponse:
    return SupplierService(db).update_product_link(supplier_id, supplier_product_id, payload)


# ---------------------------------------------------------------------------
# Evaluations (ADMIN-only)
# ---------------------------------------------------------------------------


@router.post(
    "/{supplier_id}/evaluations",
    response_model=SupplierEvaluationResponse,
    status_code=201,
    summary="Record a supplier performance evaluation (ADMIN only)",
)
def create_supplier_evaluation(
    supplier_id: int,
    payload: CreateSupplierEvaluationRequest,
    current_user: User = _ADMIN_ONLY,
    db: Session = Depends(get_db),
) -> SupplierEvaluationResponse:
    return SupplierService(db).create_evaluation(supplier_id, payload, current_user.id)


@router.get(
    "/{supplier_id}/evaluations",
    response_model=SupplierEvaluationListResponse,
    summary="List a supplier's evaluation history (ADMIN only)",
)
def list_supplier_evaluations(
    supplier_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    _current_user: User = _ADMIN_ONLY,
    db: Session = Depends(get_db),
) -> SupplierEvaluationListResponse:
    return SupplierService(db).list_evaluations(supplier_id, page, page_size)


@router.get(
    "/{supplier_id}/performance",
    response_model=SupplierPerformanceResponse,
    summary="Supplier performance dashboard data (products, supply history, ratings)",
)
def get_supplier_performance(
    supplier_id: int, db: Session = Depends(get_db)
) -> SupplierPerformanceResponse:
    return SupplierService(db).get_performance(supplier_id)
