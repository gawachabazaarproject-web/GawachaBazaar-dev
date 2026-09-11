# Wholesaler Supply Model Architecture (Phase 8.1)

## 1. Executive Summary

This architecture document freezes the business model correction applied prior to Phase 9.

In the current operating model of Gawacha Bazaar, fresh produce batches are supplied directly by **Wholesalers** rather than directly by individual smallholder farmers. To reflect this reality without losing architectural investments, the data layer has been updated to require a wholesaler supplier for every active produce batch (`wholesaler_user_id`), while retaining full structural support for direct farmer/farm sourcing as a future capability (`farm_id` made nullable).

---

## 2. Current Active Business Actors

The current operational and business actors within the Gawacha Bazaar platform are:

1. **CUSTOMER**: Consumers browsing catalog products, creating carts, placing orders, and making payments.
2. **WHOLESALER**: Supply partners who aggregate fresh agricultural produce and provide lots/batches into the supply chain.
3. **ADMIN**: Superusers overseeing business operations, catalog management, pricing, and system configurations.
4. **HUB_STAFF / OPERATIONS**: Facility staff handling sorting, grading, quality inspection, inventory lots, packaging, and internal stock movements.
5. **DELIVERY_PARTNER**: Logistics personnel handling final order packaging pickup and last-mile dispatch to customers.

---

## 3. Farmer & Farm: Future Capabilities (Preserved)

**FARMER** and **FARM** remain first-class architectural concepts in the system:
- The `farms` table remains intact with its full schema (owner FK, location coordinates, address, status, timestamps).
- The `batches.farm_id` foreign key constraint referencing `farms(id)` with `ON DELETE RESTRICT` is preserved.
- The `Farm.batches` and `Batch.farm` ORM relationships remain structurally valid and operational.
- Farmer and farm entities are **NOT deleted**, mocked, or faked.
- Wholesalers are **NOT** represented as farms or farmers.

---

## 4. Supply Relationships

### Current Active Relationship

```text
WHOLESALER
    ↓
  BATCH
    ↓
PRODUCT / VARIANT
    ↓
INVENTORY LOT
    ↓
PACKAGING
    ↓
DELIVERY
    ↓
CUSTOMER
```

### Future Direct-Sourcing Relationship

```text
FARMER
    ↓
 FARM
    ↓
 BATCH
```

Both models can coexist cleanly because `wholesaler_user_id` is mandatory for the active business model, while `farm_id` is optional/nullable.

---

## 5. Why `farm_id` is Nullable

In earlier phases, `batches.farm_id` was strictly non-nullable (`NOT NULL`), forcing every batch to originate from a farm registered in the `farms` table.

Because active supply operations source produce directly from commercial wholesalers who may source from disparate regional mandis or unmapped farm networks, forcing a `farm_id` would require either:
1. Creating fake "farms" for wholesalers, or
2. Misrepresenting wholesalers as farmers.

To avoid data corruption and architectural distortion, `farm_id` is now **`NULLABLE`**. When direct farm sourcing is enabled in the future, batches can link directly to legitimate `Farm` records.

---

## 6. Why `wholesaler_user_id` is Required

Every active batch entering the Gawacha Bazaar supply chain must have an unambiguous, legally and operationally responsible supplier.

- `batches.wholesaler_user_id` is `BIGINT NOT NULL`.
- Foreign key: `FOREIGN KEY (wholesaler_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- Index: `ix_batches_wholesaler_user_id` for efficient indexing and lookup.
- If a batch has quality issues, delivery discrepancies, or recall events, the sourcing wholesaler is immediately traceable through the database FK.

---

## 7. Why No `wholesalers` Table Exists

The platform adheres to a unified identity model:
- All human and business actors have account identities in `users`.
- Actor roles are modeled via `user_roles` linking `users` to `roles`.
- A wholesaler is represented by a `User` record associated with the `WHOLESALER` role.

Creating a separate `wholesalers` table at this stage would introduce:
- Duplicate identity records (names, contact details, authentication credentials).
- Redundant synchronization logic between user identity and wholesaler profiles.
- Unnecessary schema complexity before dedicated wholesaler profile fields are requested.

If dedicated business-to-business supplier profile attributes (e.g., GSTIN, APMC license numbers, bank mandates) are required in future phases, a specialized `wholesaler_profiles` extension table can be added without altering the core `users` identity or `batches.wholesaler_user_id` foreign key.

---

## 8. Wholesaler Role Membership as an Application-Level Rule

- **Database Responsibility**: The database strictly enforces entity integrity—ensuring that `batches.wholesaler_user_id` references a valid, existing `users.id` with `ON DELETE RESTRICT`.
- **Application Responsibility**: The application and service layers enforce authorization and business semantics—ensuring that the referenced `User` possesses the `WHOLESALER` role in `user_roles`.
- We deliberately avoid cross-table database triggers or complex subquery CHECK constraints for role membership, maintaining high transaction throughput, standard PostgreSQL portability, and clear separation between storage integrity and application authorization.

---

## 9. End-to-End Batch Traceability Path

The traceability path from produce origin through to customer fulfillment is maintained without introducing duplicate foreign keys downstream:

```text
WHOLESALER (users.id)
    │
    ▼
BATCH (batches.wholesaler_user_id, batches.product_id, [optional: batches.farm_id])
    │
    ├─────────────────────────────┬─────────────────────────────┐
    ▼                             ▼                             ▼
QUALITY CHECK                INVENTORY LOT                 FARM (future)
(qc.batch.wholesaler)       (lot.batch.wholesaler)        (batch.farm)
                                  │
                                  ▼
                            STOCK MOVEMENT
                        (movement.lot.batch.wholesaler)
                                  │
                                  ▼
                           PACKAGING INPUT
                       (input.source_lot.batch.wholesaler)
                                  │
                                  ▼
                           PACKAGING OUTPUT
                                  │
                                  ▼
                        PACKAGED INVENTORY LOT
                                  │
                                  ▼
                             ORDER ITEM
                                  │
                                  ▼
                               CUSTOMER
```

Any inspection, recall, or auditing operation at the inventory, packaging, or order stage can trace produce lineage back to the originating `Batch` and its supplying `Wholesaler` via clean ORM relationship traversal.

---

## 10. Alignment with Phase 9 Authorization

This architectural correction directly prepares the system for **Phase 9: Role-Based Access Control (RBAC) and Domain Authorization**:
- Sourcing and batch intake workflows can authorize wholesalers using standard `user_roles` membership.
- Batch creation endpoints will ensure `current_user.id` matches or is authorized on behalf of the `wholesaler_user_id`.
- Operations and Hub Staff can verify incoming batches and record quality checks without role ambiguities.
