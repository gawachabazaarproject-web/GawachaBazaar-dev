"""Domain services package.

Architecture Conventions:
1. Services encapsulate business rules, domain workflows, and multi-step transaction boundaries.
2. Services receive the SQLAlchemy Session (db: Session) via FastAPI dependency injection.
3. Transaction Ownership:
   - Simple read operations do not require explicit transaction contexts.
   - Multi-write operations (e.g. checkout, inventory allocation) MUST define their transaction boundary explicitly using `with db.begin():` or explicit commit/rollback.
   - Lower-level helpers must never commit independently.
4. Dependency Direction:
   API -> Dependencies / Schemas -> Services -> Models -> Database.
   Lower layers must never import or depend on higher layers.
5. No generic abstractions:
   Avoid GenericRepository, BaseService, UnitOfWork abstractions, or generic CRUD wrappers.
   Keep domain logic explicit and maintainable.
"""
