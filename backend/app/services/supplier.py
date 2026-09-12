"""Supplier domain service: supplier CRUD, supplier<->product links,
performance evaluations, and dashboard aggregation.

TRANSACTION DESIGN: same autobegin/no-explicit-begin rule as every other
service in this codebase - every route here is protected by
`require_roles`, which composes `get_current_user` and therefore always
autobegins the session's transaction via its own reads before any
service method runs.

Suppliers are staff-managed business records with no login concept -
nothing here ever authenticates "as" a supplier.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictError, NotFoundError
from app.models.batch import Batch
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_evaluation import SupplierEvaluation
from app.models.supplier_product import SupplierProduct
from app.schemas.supplier import (
    CreateSupplierEvaluationRequest,
    CreateSupplierRequest,
    LinkSupplierProductRequest,
    SupplierAverageRatings,
    SupplierEvaluationListResponse,
    SupplierEvaluationResponse,
    SupplierListResponse,
    SupplierPerformanceResponse,
    SupplierProductListResponse,
    SupplierProductResponse,
    SupplierProductSupplySummary,
    SupplierResponse,
    UpdateSupplierProductRequest,
    UpdateSupplierRequest,
)


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Supplier CRUD
    # ------------------------------------------------------------------

    def get_supplier_or_404(self, supplier_id: int) -> Supplier:
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            raise NotFoundError("Supplier not found.")
        return supplier

    def _lock_supplier_or_404(self, supplier_id: int) -> Supplier:
        """Read-modify-write updates must lock the row first - an
        unlocked read-then-write here would let two concurrent PATCH
        requests race and silently lose one's changes (classic
        lost-update), never surfaced until this phase's own concurrency
        tests specifically exercised it.
        """
        supplier = (
            self.db.query(Supplier)
            .filter(Supplier.id == supplier_id)
            .with_for_update()
            .first()
        )
        if not supplier:
            raise NotFoundError("Supplier not found.")
        return supplier

    def create_supplier(self, data: CreateSupplierRequest) -> SupplierResponse:
        supplier = Supplier(**data.model_dump())
        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return SupplierResponse.model_validate(supplier)

    def update_supplier(
        self, supplier_id: int, data: UpdateSupplierRequest
    ) -> SupplierResponse:
        supplier = self._lock_supplier_or_404(supplier_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(supplier, field, value)
        self.db.commit()
        self.db.refresh(supplier)
        return SupplierResponse.model_validate(supplier)

    def list_suppliers(
        self, status: str | None, page: int, page_size: int
    ) -> SupplierListResponse:
        query = self.db.query(Supplier)
        if status is not None:
            query = query.filter(Supplier.status == status)
        total = query.count()
        items = (
            query.order_by(Supplier.business_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return SupplierListResponse(
            items=[SupplierResponse.model_validate(s) for s in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    # ------------------------------------------------------------------
    # Supplier <-> Product
    # ------------------------------------------------------------------

    def link_product(
        self, supplier_id: int, data: LinkSupplierProductRequest
    ) -> SupplierProductResponse:
        self.get_supplier_or_404(supplier_id)
        product = self.db.query(Product).filter(Product.id == data.product_id).first()
        if not product:
            raise NotFoundError("Product not found.")

        link = SupplierProduct(
            supplier_id=supplier_id,
            product_id=data.product_id,
            active=data.active,
            supplier_reference=data.supplier_reference,
            notes=data.notes,
        )
        self.db.add(link)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "This supplier is already linked to this product."
            ) from exc
        self.db.refresh(link)
        return self._to_supplier_product_response(link, product.name)

    def update_product_link(
        self, supplier_id: int, supplier_product_id: int, data: UpdateSupplierProductRequest
    ) -> SupplierProductResponse:
        link = (
            self.db.query(SupplierProduct)
            .filter(
                SupplierProduct.id == supplier_product_id,
                SupplierProduct.supplier_id == supplier_id,
            )
            .with_for_update()
            .first()
        )
        if not link:
            raise NotFoundError("Supplier product link not found.")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(link, field, value)
        self.db.commit()
        self.db.refresh(link)
        product = self.db.query(Product).filter(Product.id == link.product_id).first()
        return self._to_supplier_product_response(link, product.name)

    def list_products(
        self, supplier_id: int, page: int, page_size: int
    ) -> SupplierProductListResponse:
        self.get_supplier_or_404(supplier_id)
        query = (
            self.db.query(SupplierProduct, Product.name)
            .join(Product, SupplierProduct.product_id == Product.id)
            .filter(SupplierProduct.supplier_id == supplier_id)
        )
        total = query.count()
        rows = (
            query.order_by(Product.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return SupplierProductListResponse(
            items=[self._to_supplier_product_response(link, name) for link, name in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    @staticmethod
    def _to_supplier_product_response(
        link: SupplierProduct, product_name: str
    ) -> SupplierProductResponse:
        return SupplierProductResponse(
            id=link.id,
            supplier_id=link.supplier_id,
            product_id=link.product_id,
            product_name=product_name,
            active=link.active,
            supplier_reference=link.supplier_reference,
            notes=link.notes,
            created_at=link.created_at,
            updated_at=link.updated_at,
        )

    # ------------------------------------------------------------------
    # Evaluations (ADMIN-only, append-only)
    # ------------------------------------------------------------------

    def create_evaluation(
        self, supplier_id: int, data: CreateSupplierEvaluationRequest, evaluated_by_user_id: int
    ) -> SupplierEvaluationResponse:
        self.get_supplier_or_404(supplier_id)
        evaluation = SupplierEvaluation(
            supplier_id=supplier_id,
            evaluated_by_user_id=evaluated_by_user_id,
            **data.model_dump(),
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return SupplierEvaluationResponse.model_validate(evaluation)

    def list_evaluations(
        self, supplier_id: int, page: int, page_size: int
    ) -> SupplierEvaluationListResponse:
        self.get_supplier_or_404(supplier_id)
        query = self.db.query(SupplierEvaluation).filter(
            SupplierEvaluation.supplier_id == supplier_id
        )
        total = query.count()
        items = (
            query.order_by(SupplierEvaluation.created_at.desc(), SupplierEvaluation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return SupplierEvaluationListResponse(
            items=[SupplierEvaluationResponse.model_validate(e) for e in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    # ------------------------------------------------------------------
    # Performance dashboard aggregation
    # ------------------------------------------------------------------

    def get_performance(self, supplier_id: int) -> SupplierPerformanceResponse:
        supplier = self.get_supplier_or_404(supplier_id)

        products_supplied = [
            name
            for (name,) in self.db.query(Product.name)
            .join(SupplierProduct, SupplierProduct.product_id == Product.id)
            .filter(SupplierProduct.supplier_id == supplier_id, SupplierProduct.active.is_(True))
            .order_by(Product.name)
            .all()
        ]

        supply_rows = (
            self.db.query(
                Batch.product_id,
                Product.name,
                Batch.unit,
                func.count(Batch.id),
                func.coalesce(func.sum(Batch.quantity), Decimal("0")),
            )
            .join(Product, Batch.product_id == Product.id)
            .filter(Batch.supplier_id == supplier_id)
            .group_by(Batch.product_id, Product.name, Batch.unit)
            .order_by(Product.name)
            .all()
        )
        supply_summary = [
            SupplierProductSupplySummary(
                product_id=product_id,
                product_name=name,
                unit=unit,
                batch_count=count,
                total_quantity_supplied=total_qty,
            )
            for product_id, name, unit, count, total_qty in supply_rows
        ]
        total_batches_supplied = sum(row.batch_count for row in supply_summary)

        last_supply_date: date | None = (
            self.db.query(func.max(func.coalesce(Batch.received_date, Batch.harvest_date)))
            .filter(Batch.supplier_id == supplier_id)
            .scalar()
        )

        evaluation_count = (
            self.db.query(func.count(SupplierEvaluation.id))
            .filter(SupplierEvaluation.supplier_id == supplier_id)
            .scalar()
        ) or 0

        latest_evaluation_row = (
            self.db.query(SupplierEvaluation)
            .filter(SupplierEvaluation.supplier_id == supplier_id)
            .order_by(SupplierEvaluation.created_at.desc(), SupplierEvaluation.id.desc())
            .first()
        )
        latest_evaluation = (
            SupplierEvaluationResponse.model_validate(latest_evaluation_row)
            if latest_evaluation_row
            else None
        )

        averages = (
            self.db.query(
                func.avg(SupplierEvaluation.quality_rating),
                func.avg(SupplierEvaluation.delivery_rating),
                func.avg(SupplierEvaluation.price_rating),
                func.avg(SupplierEvaluation.reliability_rating),
                func.avg(SupplierEvaluation.responsiveness_rating),
                func.avg(SupplierEvaluation.overall_rating),
            )
            .filter(SupplierEvaluation.supplier_id == supplier_id)
            .first()
        )
        average_ratings = SupplierAverageRatings(
            quality=_round1(averages[0]) if averages else None,
            delivery=_round1(averages[1]) if averages else None,
            price=_round1(averages[2]) if averages else None,
            reliability=_round1(averages[3]) if averages else None,
            responsiveness=_round1(averages[4]) if averages else None,
            overall=_round1(averages[5]) if averages else None,
        )

        return SupplierPerformanceResponse(
            supplier=SupplierResponse.model_validate(supplier),
            products_supplied=products_supplied,
            supply_summary=supply_summary,
            total_batches_supplied=total_batches_supplied,
            last_supply_date=last_supply_date,
            evaluation_count=evaluation_count,
            latest_evaluation=latest_evaluation,
            average_ratings=average_ratings,
        )


def _round1(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.1"))
