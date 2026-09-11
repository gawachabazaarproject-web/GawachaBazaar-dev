"""Packaging domain service: operations, inputs, outputs, and atomic completion.

TRANSACTION DESIGN: identical rule to app/services/inventory.py - every route
here is protected by `require_roles`, which composes `get_current_user` and
therefore always autobegins the session's transaction via its own reads
before any service method runs. `complete_operation` never calls
`db.begin()`; it performs the locking SELECTs, validation, and writes
directly against the already-open transaction, then calls `db.commit()`
exactly once at the very end.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictError, NotFoundError
from app.models.batch import Batch
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.packaging_input import PackagingInput
from app.models.packaging_operation import PackagingOperation
from app.models.packaging_output import PackagingOutput
from app.models.product_variant import ProductVariant
from app.schemas.packaging import (
    CreatePackagingInputRequest,
    CreatePackagingOperationRequest,
    CreatePackagingOutputRequest,
    PackagingInputResponse,
    PackagingOperationDetailResponse,
    PackagingOperationListResponse,
    PackagingOperationResponse,
    PackagingOutputResponse,
)
from app.services.inventory import InventoryService

_DRAFT = "DRAFT"
_IN_PROGRESS = "IN_PROGRESS"
_COMPLETED = "COMPLETED"
_CANCELLED = "CANCELLED"

_REFERENCE_TYPE = "PACKAGING_OPERATION"


class PackagingService:
    """PackagingOperation/Input/Output business logic and the atomic
    completion transaction.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def get_operation_or_404(self, operation_id: int) -> PackagingOperation:
        operation = (
            self.db.query(PackagingOperation)
            .filter(PackagingOperation.id == operation_id)
            .first()
        )
        if not operation:
            raise NotFoundError("Packaging operation not found.")
        return operation

    def create_operation(
        self, data: CreatePackagingOperationRequest, performed_by_user_id: int
    ) -> PackagingOperationResponse:
        location = (
            self.db.query(InventoryLocation)
            .filter(InventoryLocation.id == data.location_id)
            .first()
        )
        if not location:
            raise NotFoundError("Inventory location not found.")

        now = datetime.now(UTC)
        operation = PackagingOperation(
            packaging_code=data.packaging_code,
            name=data.name,
            location_id=data.location_id,
            status=_DRAFT,
            # started_at is NOT NULL on this (frozen, Phase 5) table with no
            # server default, so it is set at creation time rather than at
            # the /start transition - see docs/api/PHASE_12_PACKAGING_API.md.
            started_at=now,
            performed_by_user_id=performed_by_user_id,
            remarks=data.remarks,
        )
        self.db.add(operation)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A packaging operation with this packaging_code already exists."
            ) from exc
        self.db.refresh(operation)
        return PackagingOperationResponse.model_validate(operation)

    def list_operations(
        self,
        status: str | None,
        location_id: int | None,
        page: int,
        page_size: int,
    ) -> PackagingOperationListResponse:
        query = self.db.query(PackagingOperation)
        if status is not None:
            query = query.filter(PackagingOperation.status == status)
        if location_id is not None:
            query = query.filter(PackagingOperation.location_id == location_id)

        total = query.count()
        items = (
            query.order_by(PackagingOperation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PackagingOperationListResponse(
            items=[PackagingOperationResponse.model_validate(op) for op in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_operation_detail(
        self, operation_id: int
    ) -> PackagingOperationDetailResponse:
        operation = self.get_operation_or_404(operation_id)
        inputs = (
            self.db.query(PackagingInput)
            .filter(PackagingInput.packaging_operation_id == operation_id)
            .order_by(PackagingInput.id)
            .all()
        )
        outputs = (
            self.db.query(PackagingOutput)
            .filter(PackagingOutput.packaging_operation_id == operation_id)
            .order_by(PackagingOutput.id)
            .all()
        )
        return PackagingOperationDetailResponse(
            **PackagingOperationResponse.model_validate(operation).model_dump(),
            inputs=[PackagingInputResponse.model_validate(i) for i in inputs],
            outputs=[PackagingOutputResponse.model_validate(o) for o in outputs],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_operation(self, operation_id: int) -> PackagingOperationResponse:
        operation = self.get_operation_or_404(operation_id)
        if operation.status != _DRAFT:
            raise ConflictError(
                f"Cannot start a packaging operation in status {operation.status}."
            )
        operation.status = _IN_PROGRESS
        self.db.commit()
        self.db.refresh(operation)
        return PackagingOperationResponse.model_validate(operation)

    def cancel_operation(self, operation_id: int) -> PackagingOperationResponse:
        operation = self.get_operation_or_404(operation_id)
        if operation.status not in (_DRAFT, _IN_PROGRESS):
            raise ConflictError(
                f"Cannot cancel a packaging operation in status {operation.status}."
            )
        operation.status = _CANCELLED
        self.db.commit()
        self.db.refresh(operation)
        return PackagingOperationResponse.model_validate(operation)

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------

    def add_input(
        self, operation_id: int, data: CreatePackagingInputRequest
    ) -> PackagingInputResponse:
        operation = self.get_operation_or_404(operation_id)
        if operation.status not in (_DRAFT, _IN_PROGRESS):
            raise ConflictError(
                f"Cannot modify inputs on a packaging operation in status "
                f"{operation.status}."
            )

        lot = (
            self.db.query(InventoryLot)
            .filter(InventoryLot.id == data.inventory_lot_id)
            .first()
        )
        if not lot:
            raise NotFoundError("Inventory lot not found.")
        if lot.location_id != operation.location_id:
            raise ConflictError(
                "Input inventory lot does not belong to the operation's location."
            )

        duplicate = (
            self.db.query(PackagingInput)
            .filter(
                PackagingInput.packaging_operation_id == operation_id,
                PackagingInput.inventory_lot_id == data.inventory_lot_id,
            )
            .first()
        )
        if duplicate:
            raise ConflictError(
                "This inventory lot is already recorded as an input for this "
                "operation. Remove it first to change the quantity."
            )

        packaging_input = PackagingInput(
            packaging_operation_id=operation_id,
            inventory_lot_id=data.inventory_lot_id,
            quantity=data.quantity,
        )
        self.db.add(packaging_input)
        self.db.commit()
        self.db.refresh(packaging_input)
        return PackagingInputResponse.model_validate(packaging_input)

    def remove_input(self, operation_id: int, input_id: int) -> None:
        operation = self.get_operation_or_404(operation_id)
        if operation.status not in (_DRAFT, _IN_PROGRESS):
            raise ConflictError(
                f"Cannot modify inputs on a packaging operation in status "
                f"{operation.status}."
            )

        packaging_input = (
            self.db.query(PackagingInput)
            .filter(
                PackagingInput.id == input_id,
                PackagingInput.packaging_operation_id == operation_id,
            )
            .first()
        )
        if not packaging_input:
            raise NotFoundError("Packaging input not found.")

        self.db.delete(packaging_input)
        self.db.commit()

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------

    def add_output(
        self, operation_id: int, data: CreatePackagingOutputRequest
    ) -> PackagingOutputResponse:
        operation = self.get_operation_or_404(operation_id)
        if operation.status not in (_DRAFT, _IN_PROGRESS):
            raise ConflictError(
                f"Cannot modify outputs on a packaging operation in status "
                f"{operation.status}."
            )

        variant = (
            self.db.query(ProductVariant)
            .filter(ProductVariant.id == data.variant_id)
            .first()
        )
        if not variant:
            raise NotFoundError("Product variant not found.")
        batch = self.db.query(Batch).filter(Batch.id == data.batch_id).first()
        if not batch:
            raise NotFoundError("Batch not found.")

        input_batch_ids = self._input_batch_ids(operation_id)
        if not input_batch_ids:
            raise ConflictError(
                "This operation has no inputs yet. Add at least one input "
                "before declaring an output."
            )
        if data.batch_id not in input_batch_ids:
            raise ConflictError(
                "Output batch_id must match one of this operation's input "
                "batches. Outputs cannot be traced to a batch that was not "
                "actually consumed."
            )

        inventory_service = InventoryService(self.db)
        lot = inventory_service.get_or_create_lot_no_commit(
            data.batch_id, data.variant_id, operation.location_id
        )

        duplicate = (
            self.db.query(PackagingOutput)
            .filter(
                PackagingOutput.packaging_operation_id == operation_id,
                PackagingOutput.inventory_lot_id == lot.id,
            )
            .first()
        )
        if duplicate:
            raise ConflictError(
                "An output for this batch/variant is already recorded for "
                "this operation. Remove it first to change the quantities."
            )

        packaging_output = PackagingOutput(
            packaging_operation_id=operation_id,
            inventory_lot_id=lot.id,
            package_count=data.package_count,
            total_quantity=data.total_quantity,
        )
        self.db.add(packaging_output)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not record packaging output due to a conflicting update."
            ) from exc
        self.db.refresh(packaging_output)
        return PackagingOutputResponse.model_validate(packaging_output)

    def remove_output(self, operation_id: int, output_id: int) -> None:
        operation = self.get_operation_or_404(operation_id)
        if operation.status not in (_DRAFT, _IN_PROGRESS):
            raise ConflictError(
                f"Cannot modify outputs on a packaging operation in status "
                f"{operation.status}."
            )

        packaging_output = (
            self.db.query(PackagingOutput)
            .filter(
                PackagingOutput.id == output_id,
                PackagingOutput.packaging_operation_id == operation_id,
            )
            .first()
        )
        if not packaging_output:
            raise NotFoundError("Packaging output not found.")

        self.db.delete(packaging_output)
        self.db.commit()

    # ------------------------------------------------------------------
    # Completion (the atomic business transaction)
    # ------------------------------------------------------------------

    def complete_operation(
        self, operation_id: int, performed_by_user_id: int
    ) -> PackagingOperationDetailResponse:
        """Atomically: lock operation -> lock all input+output lots in one
        consistent order -> validate stock/traceability -> apply
        ADJUSTMENT_OUT to each input lot and RECEIPT to each output lot ->
        mark COMPLETED -> commit once. See module docstring for why no
        explicit db.begin() is used.
        """
        operation = (
            self.db.query(PackagingOperation)
            .filter(PackagingOperation.id == operation_id)
            .with_for_update()
            .first()
        )
        if not operation:
            raise NotFoundError("Packaging operation not found.")

        # Locking the operation row first serializes concurrent completion
        # attempts: the second request blocks here, then sees COMPLETED
        # (or CANCELLED) once it acquires the lock, and is rejected cleanly
        # - no duplicate movements are ever created.
        if operation.status != _IN_PROGRESS:
            raise ConflictError(
                f"Cannot complete a packaging operation in status "
                f"{operation.status}. Only IN_PROGRESS operations can be "
                f"completed."
            )

        inputs = (
            self.db.query(PackagingInput)
            .filter(PackagingInput.packaging_operation_id == operation_id)
            .all()
        )
        outputs = (
            self.db.query(PackagingOutput)
            .filter(PackagingOutput.packaging_operation_id == operation_id)
            .all()
        )
        if not inputs:
            raise ConflictError(
                "Cannot complete a packaging operation with no inputs."
            )
        if not outputs:
            raise ConflictError(
                "Cannot complete a packaging operation with no outputs."
            )

        total_input = sum((i.quantity for i in inputs), Decimal("0"))
        total_output = sum((o.total_quantity for o in outputs), Decimal("0"))
        if total_output > total_input:
            raise ConflictError(
                "Total output quantity cannot exceed total input quantity."
            )

        # Re-validate traceability at completion time, not just at add_output
        # time - an input consumed by an output could have been removed
        # since. See docs/api/PHASE_12_PACKAGING_API.md.
        input_batch_ids = self._input_batch_ids(operation_id)
        for output in outputs:
            output_lot = self.db.get(InventoryLot, output.inventory_lot_id)
            if output_lot.batch_id not in input_batch_ids:
                raise ConflictError(
                    "Output batch traceability is no longer valid - the "
                    "source input for this batch was removed since the "
                    "output was added."
                )

        # Lock every input and output lot in one query, ordered by id, so
        # concurrent operations touching overlapping lots always acquire
        # locks in the same global order (deadlock avoidance).
        lot_ids = sorted(
            {i.inventory_lot_id for i in inputs} | {o.inventory_lot_id for o in outputs}
        )
        locked_lots = {
            lot.id: lot
            for lot in (
                self.db.query(InventoryLot)
                .filter(InventoryLot.id.in_(lot_ids))
                .order_by(InventoryLot.id)
                .with_for_update()
                .all()
            )
        }

        inventory_service = InventoryService(self.db)

        for packaging_input in inputs:
            lot = locked_lots[packaging_input.inventory_lot_id]
            inventory_service.apply_movement(
                lot,
                "ADJUSTMENT_OUT",
                packaging_input.quantity,
                performed_by_user_id,
                reference_type=_REFERENCE_TYPE,
                reference_id=operation.id,
                remarks=f"Consumed by packaging operation {operation.packaging_code}",
            )

        for packaging_output in outputs:
            lot = locked_lots[packaging_output.inventory_lot_id]
            inventory_service.apply_movement(
                lot,
                "RECEIPT",
                packaging_output.total_quantity,
                performed_by_user_id,
                reference_type=_REFERENCE_TYPE,
                reference_id=operation.id,
                remarks=f"Produced by packaging operation {operation.packaging_code}",
            )

        operation.status = _COMPLETED
        operation.completed_at = datetime.now(UTC)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not complete packaging operation due to a "
                "conflicting update."
            ) from exc

        return self.get_operation_detail(operation_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _input_batch_ids(self, operation_id: int) -> set[int]:
        rows = (
            self.db.query(InventoryLot.batch_id)
            .join(PackagingInput, PackagingInput.inventory_lot_id == InventoryLot.id)
            .filter(PackagingInput.packaging_operation_id == operation_id)
            .all()
        )
        return {row[0] for row in rows}
