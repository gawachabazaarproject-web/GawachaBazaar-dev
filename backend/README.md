# Gawacha Bazaar Backend

FastAPI service that owns all business logic for Gawacha Bazaar: catalog, inventory, cart and
orders, payments, fulfillment, promotions, bulk commerce, staff and content. Clients (customer
app, Admin panel) are thin. System-wide picture: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md);
features: [../docs/FEATURES.md](../docs/FEATURES.md). Phase-by-phase deep dives are in
[docs/](docs) (`api/`, `architecture/`, `database/`).

## Stack

- **Framework**: FastAPI (Python 3.11+), served by uvicorn
- **Data**: SQLAlchemy 2.x (synchronous), PostgreSQL 16 via psycopg 3 (`postgresql+psycopg://`)
- **Migrations**: Alembic (35+ revisions in `alembic/versions`)
- **Validation / settings**: Pydantic v2, `pydantic-settings`
- **Identity**: Firebase Authentication (ID tokens verified with the Firebase Admin SDK);
  Argon2 only for migrating legacy passwords
- **Payments**: Razorpay (COD also supported) - signed webhooks, server-side verification
- **Images**: Cloudinary
- **Routing**: Google Distance Matrix or OSRM for road distance (via `httpx`)
- **Realtime**: in-process WebSocket hub for staff events
- **Rate limiting**: slowapi (in-memory, per process)
- **Quality**: pytest + httpx/TestClient, Ruff

## Layout

```text
backend/
├── app/
│   ├── main.py              app factory, lifespan (captures event loop, starts reservation sweep)
│   ├── api/v1/              routers, one file per domain, registered in router.py:
│   │                        auth, addresses, wishlist, catalog, inventory, packaging, cart,
│   │                        orders, payments (+ webhooks), fulfillments, suppliers, bulk_orders,
│   │                        promotions, customers, staff, dashboard, ads, home_slides, bazaar, realtime
│   ├── core/                config.py, firebase.py, roles.py, permissions.py, rate_limit.py,
│   │                        realtime.py, security.py, security_headers.py, request_id.py, logging.py
│   ├── dependencies/        get_current_user, require_permission, require_roles, get_db
│   ├── services/            business logic; *_state.py = state machines; delivery.py + bazaar.py =
│   │                        delivery pricing and Bazaar+; razorpay_gateway.py, image_upload.py
│   ├── models/              SQLAlchemy models (~50)
│   ├── schemas/             Pydantic request/response models
│   ├── exceptions/          AppException types -> uniform JSON errors
│   └── db/                  declarative base, engine, session
├── alembic/                 env.py + versions/
├── scripts/                 create_admin.py, activate_user.py, check_admin.py, seed_dummy_data.py
├── tests/                   ~36 test modules (models, state machines, API flows, delivery fee, auth)
├── docs/                    api/ architecture/ database/ phase documents
├── Dockerfile               python:3.11-slim, non-root, single uvicorn worker
├── start.sh                 container entrypoint
└── requirements*.txt, pyproject.toml, alembic.ini, .env.example
```

Request flow: `router -> dependency (auth / permission / db) -> service -> models`. Keep routers
thin; put every rule in a service; express lifecycles in the matching `*_state.py`.

## Setup

```bash
# 1. Virtual environment + dependencies
python -m venv venv
.\venv\Scripts\Activate.ps1            # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 2. Configuration
cp .env.example .env                    # then edit; never commit .env

# 3. Database schema
alembic upgrade head

# 4. First admin (fresh database)
python scripts/create_admin.py

# 5. Run
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger UI: http://127.0.0.1:8000/docs - Health: `/health` - DB probe: `/health/db`
- Tests: `python -m pytest -v` (needs a reachable test database) - Lint: `python -m ruff check .`
- New migration: `alembic revision -m "message"`, then edit it; one head only
  (`alembic heads`). Latest additions: order delivery fee, inventory-location packing point,
  ad card text.

## Configuration reference

All values are environment variables (see `.env.example`; production template is
`../.env.production.example`).

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `development` | `development` / `testing` / `staging` / `production`. Production **refuses to start** without `FIREBASE_PROJECT_ID`, or with Razorpay half-configured |
| `DATABASE_URL` | local Postgres | `postgres://` and `postgresql://` are rewritten to `postgresql+psycopg://` |
| `FIREBASE_PROJECT_ID` | - | Required in production (token verification) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | - | Service-account JSON or file path; needed for staff creation, password resets, legacy migration |
| `RAZORPAY_KEY_ID` / `_KEY_SECRET` / `_WEBHOOK_SECRET` | - | Empty key id = COD only |
| `CLOUDINARY_CLOUD_NAME` / `_API_KEY` / `_API_SECRET` | - | Image uploads (unset = clear error) |
| `ALLOWED_ORIGINS` | localhost dev origins | CORS allow-list (JSON array or comma list) |
| `FREE_DELIVERY_MIN_ITEMS` | `15` | Distinct products needed for free delivery |
| `DELIVERY_BASE_FEE` | `20` | Rs, always charged below the threshold |
| `DELIVERY_PER_KM` | `10` | Rs per road km |
| `DELIVERY_MAX_CHARGED_KM` | `30` | Distance cap |
| `PACKING_POINT_LATITUDE` / `_LONGITUDE` | - | **Fallback** origin; the warehouse chosen in Admin -> Settings wins |
| `GOOGLE_MAPS_API_KEY` | - | Enables Google Distance Matrix (otherwise OSRM) |
| `OSRM_BASE_URL` | public demo server | Use your own router in production |
| `ROUTING_TIMEOUT_SECONDS` | `3` | Router timeout before falling back |
| `DELIVERY_ROAD_FACTOR` | `1.4` | Straight-line multiplier used when routing fails |
| `BAZAAR_PLUS_ORDERS_REQUIRED` | `6` | Bazaar orders per month for Bazaar+ |
| `BAZAAR_TIMEZONE` | `Asia/Kolkata` | Defines the calendar month |

## Delivery pricing in code

`services/delivery.py::calculate_delivery_fee(item_count, lat, lon, origin=None)` is pure and
shared by the cart quote (`services/bazaar.py`) and checkout (`services/order.py`).
`get_packing_point(db)` returns the active warehouse flagged `is_packing_point`
(`inventory_locations`), else the env fallback. `road_distance_km` tries Google/OSRM, caches per
rounded coordinate pair, and falls back to straight-line x `DELIVERY_ROAD_FACTOR`.
Admins set the packing point with `POST /inventory/locations/{id}/packing-point` (ADMIN only);
a location needs coordinates and `ACTIVE` status.

## Operating notes

- Run **one worker**: rate limiting, the WebSocket registry and the reservation sweep are
  in-process. Scaling out needs Redis first (see ARCHITECTURE section 10).
- Unpaid online orders expire and release stock through a sweep every 120 seconds.
- Order items in API responses include the product's current primary `image_url`.
- Error responses are always `{ "code", "message", "details" }`; clients branch on `code`.
