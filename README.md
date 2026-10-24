# AI Operations Control Tower

A full-stack operations intelligence portfolio project. The system demonstrates the end-to-end workflow:

**Data → Risk detection → Recommendation → Human approval → Audit event**

---

## Architecture & Technology Stack

- **Backend**: Python 3.12, FastAPI, Pydantic 2, Pydantic-Settings
- **Security & Authentication**: Bcrypt 5.0 password hashing, PyJWT 2.15 signed access tokens, SlowAPI rate limiting, HttpOnly SameSite session cookies
- **Database Layer**: SQLAlchemy 2.x async engine (`asyncpg` / `aiosqlite`), Alembic async migrations
- **Frontend**: React 18, TypeScript, Vite, Lucide Icons, Vanilla CSS
- **Testing**: Pytest, Pytest-Asyncio, isolated in-memory test databases

---

## Phase 4: Real Business Operations — Products, Suppliers, Warehouses, Inventory, and Orders

Phase 4 implements real database-backed operations, business invariant safeguards, concurrency control, and interactive frontend operational workflows:

### 1. Business Domains & Endpoints

| Domain | Key Endpoints | RBAC Policy | Business Constraints & Invariants |
|---|---|---|---|
| **Suppliers** | `GET /api/v1/suppliers`<br>`POST /api/v1/suppliers`<br>`GET /api/v1/suppliers/{id}`<br>`PATCH /api/v1/suppliers/{id}`<br>`DELETE /api/v1/suppliers/{id}`<br>`POST /api/v1/suppliers/{id}/deactivate` | Read: `DASHBOARD_READ`<br>Write: `DATA_MANAGE` | • Unique supplier code (case-insensitive)<br>• Deletion prevented if products reference supplier (`400 Bad Request`)<br>• Bounded reliability score (`0.00` - `1.00`) |
| **Products** | `GET /api/v1/products`<br>`POST /api/v1/products`<br>`GET /api/v1/products/{id}`<br>`PATCH /api/v1/products/{id}`<br>`DELETE /api/v1/products/{id}`<br>`POST /api/v1/products/{id}/deactivate` | Read: `DASHBOARD_READ`<br>Write: `DATA_MANAGE` | • Unique SKU enforcement<br>• Supplier reference validation (must exist in DB)<br>• Exact `Decimal` / `Numeric(12, 2)` monetary values<br>• Deletion blocked if active inventory or orders exist |
| **Warehouses** | `GET /api/v1/warehouses`<br>`POST /api/v1/warehouses`<br>`GET /api/v1/warehouses/{id}`<br>`PATCH /api/v1/warehouses/{id}`<br>`DELETE /api/v1/warehouses/{id}`<br>`POST /api/v1/warehouses/{id}/deactivate` | Read: `DASHBOARD_READ`<br>Write: `DATA_MANAGE` | • Unique facility code<br>• Capacity strictly positive (`> 0`)<br>• Deletion blocked if active on-hand inventory exists |
| **Inventory & Movements** | `GET /api/v1/inventory`<br>`GET /api/v1/inventory/{id}`<br>`GET /api/v1/inventory/by-location`<br>`PATCH /api/v1/inventory/{id}`<br>`POST /api/v1/inventory/receipt`<br>`POST /api/v1/inventory/issue`<br>`GET /api/v1/inventory/movements` | Read: `DASHBOARD_READ`<br>Write: `DATA_MANAGE` | • Controlled receipts & issues with `with_for_update()` locking<br>• Invariant: `quantity_reserved <= quantity_on_hand`<br>• Overdraft prevention: available stock check prevents negative stock<br>• Idempotency key prevents duplicate receipts/issues<br>• Ordinary updates only allow adjusting threshold (`reorder_quantity`) |
| **Orders** | `GET /api/v1/orders`<br>`POST /api/v1/orders`<br>`GET /api/v1/orders/{id}`<br>`PATCH /api/v1/orders/{id}/status`<br>`PATCH /api/v1/orders/{id}` | Read: `DASHBOARD_READ`<br>Write: `DATA_MANAGE` | • Server-calculated totals (client prices never trusted)<br>• Multi-item atomic transactional creation<br>• State machine graph: `PENDING` &rarr; `PROCESSING` &rarr; `SHIPPED` &rarr; `DELIVERED`, or `CANCELLED`<br>• Terminal state enforcement (cannot mutate `DELIVERED`/`CANCELLED`) |

### 2. Transactional Audit Trail
Every create, update, deactivate, delete, stock receipt, stock issue, and status transition automatically writes a consistent record to `audit_logs` tracking the authenticated actor ID, action code, timestamp, and sanitized payload.

### 3. Frontend Operations Views
- **Suppliers Directory**: Search, active filters, "+ New Supplier" modal, deactivation.
- **Product Catalog**: SKU search, category filter, sorting, "+ New Product" modal with supplier selection.
- **Warehouses**: Search, capacity indicators, "+ New Warehouse" modal.
- **Inventory & Stock Movements**: Sub-tab toggle between Live Balances and Stock Movement Audit History. Inbound receipt modal (PO) and Outbound issue modal (Dispatch) with live idempotency key generation.
- **Orders View**: Search, status filter, order creation modal with line items builder and live computed subtotals. Order detail view with state machine progression buttons.
- **Role Awareness**: Write actions are disabled with clear lock indicators for `VIEWER` and `ANALYST` roles, while backend permissions strictly return `403 Forbidden` on unauthorized mutation attempts.

---

## Phase 3: Secure Authentication and Role-Based Access Control (RBAC)

Phase 3 introduces comprehensive authentication and server-enforced authorization:

### 1. Authentication Engine
- **Registration**: `POST /api/v1/auth/register` validates email and password strength (min 8 chars, letter + digit), hashes passwords via `bcrypt` (12 rounds), and persists users in the database.
- **Login**: `POST /api/v1/auth/login` verifies credentials and issues short-lived signed JWT access tokens with required claims (`sub`, `email`, `role`, `exp`, `iat`, `nbf`, `iss`, `aud`, `jti`).
- **Session Security**: The login endpoint sets an `HttpOnly`, `SameSite=Lax` cookie (`access_token`) and returns the Bearer token for API consumers. This avoids vulnerable token storage in browser `localStorage`.
- **Profile & Permissions**: `GET /api/v1/auth/me` returns the authenticated user profile with resolved permissions.
- **Credential Protection**: Password hashes are never returned in any response, printed, or logged.

### 2. Role-Based Access Control (RBAC)
Server-side permissions matrix enforced via reusable FastAPI dependencies (`require_permission`, `require_roles`):

| Role | Role Code | Permitted Operations | Restricted Operations |
|---|---|---|---|
| **ADMIN** | `ADMIN` | User administration, decision approvals, analytics, and dashboard | None (Full System Privileges) |
| **OPERATIONS MANAGER** | `OPERATIONS_MANAGER` | Recommendation decision approval/rejection, audit recording, analytics, dashboard | User administration |
| **ANALYST** | `ANALYST` | Risk intelligence detection, operational analytics, dashboard read | Recommendation decisions, User administration |
| **VIEWER** | `VIEWER` | Core dashboard summary and read-only recommendation inspection | Risk intelligence, Recommendation decisions, User administration |

### 3. Frontend Experience
- **Login & Registration View**: Dark operations-themed login screen matching the Control Tower aesthetic with validation and real-time backend error banners.
- **Quick Evaluator Demo Chips**: One-click login buttons for **Admin**, **Operations Manager**, **Analyst**, and **Viewer** with automatic provisioning for seamless testing.
- **Role-Aware UI**:
  - Sidebar displays user avatar, email, and color-coded role badge (`ADMIN`, `OPERATIONS_MANAGER`, `ANALYST`, `VIEWER`).
  - Read-only users (Viewer/Analyst) see locked indicators on decision buttons with clear explanations: *"🔒 Read-only view. Approval decisions require Operations Manager or Admin role."*
  - Backend strictly enforces HTTP 403 Forbidden on unauthorized operations regardless of UI state.
  - One-click logout clears session cookies and resets the application state.

---

## Phase 2: Database Foundation

### Domain Models (`app/models`)
- **`User`**: System operators with role constraints (`ADMIN`, `OPERATIONS_MANAGER`, `ANALYST`, `VIEWER`).
- **`Supplier`**: Supply chain vendors with lead-time tracking and bounded reliability scores (`0.00` – `1.00`).
- **`Product`**: Catalog SKUs with exact `Numeric(12, 2)` pricing/costs, safety stock, and reorder points.
- **`Warehouse`**: Distribution centers and fulfillment capacity.
- **`Inventory`**: Stock tracking per facility with over-reservation check constraints.
- **`Order`**: Purchase orders with priority levels and lifecycle states (`PENDING`, `PROCESSING`, `SHIPPED`, etc.).
- **`OrderItem`**: Line items with positive quantities and exact `Numeric` pricing.
- **`AuditLog`**: Immutable audit trail capturing operator decisions, automated recommendations, and payload snapshots.

---

## Phase 7: Production Readiness, Security Hardening & Deployment Audit

Phase 7 implements production-grade security hardening, fail-fast reliability controls, audit logging, multi-stage deployment configurations, and automated verification:

### 1. Database Reliability & Fallback Architecture
- **Fail-Fast Production Startup**: Startup halts with a fatal exception (`RuntimeError`) if the primary PostgreSQL instance is unreachable in production (`APP_ENV=production` or `ALLOW_SQLITE_FALLBACK=false`), preventing silent database switching and dataset divergence.
- **Explicit Backend Diagnostics**: `/ready` and `/health/diagnostics` explicitly identify the active database backend (`postgresql` vs `sqlite`), pool sizing, and fallback state.
- **Accurate Readiness Probes**: `/ready` returns HTTP 503 Service Unavailable when dependencies are unreachable, preventing premature traffic routing.
- **Safe Development Fallback**: In local development (`APP_ENV=development` with `ALLOW_SQLITE_FALLBACK=true`), the system continues to support persistent local SQLite fallback with prominent operational log warnings.

### 2. Security Hardening
- **Strict Production Secrets Validation**: Startup validates that `SECRET_KEY` is not a default development string, is provided via environment variable, and is at least 32 characters.
- **Demo Login Isolation**: Quick one-click demo login buttons are dynamically hidden in production builds and forbidden when `ENABLE_DEMO_LOGINS=false`.
- **Defense-in-Depth Security Headers**: Applied to all responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **Host Header & CSRF Mitigation**: Added `TrustedHostMiddleware` configuration and `X-Requested-With: XMLHttpRequest` custom headers.
- **Sanitized Request Logging**: Structured HTTP logging records method, route path, status code, duration, and client IP without leaking sensitive query parameters, authorization headers, or request bodies.
- **Cookie Security**: Enforced `HttpOnly`, `SameSite=Lax`, and `Secure` cookie attributes with synchronized deletion on logout.

### 3. Container & Operational Hardening
- **Backend Container**: Upgraded Dockerfile with non-root user (`appuser` UID 1000), healthcheck instructions, and included Alembic migration scripts.
- **Frontend Container**: Implemented multi-stage build (`node:22-alpine` builder & runtime static serving) with non-root user (`node`) and healthcheck.
- **Docker Compose**: Synchronized credentials between PostgreSQL service and backend configuration; added Redis and backend health checks.
- **CI Pipeline**: Added live PostgreSQL 16 and Redis 7 service containers in GitHub Actions to continuously test migrations and database integration alongside frontend build validation.

---

## Native Windows Development Workflow

### 1. Prerequisites
- Python 3.12 (check with `python --version`)
- Node.js 18+ (for frontend)
- Optional: PostgreSQL 14+ installed locally (e.g. `postgresql-x64-18` service on Windows)

### 2. Backend Setup (PowerShell)

```powershell
cd backend

# Copy environment template
Copy-Item ..\.env.example ..\.env

# Run development server (with SQLite fallback in dev mode)
$env:PYTHONPATH="."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Readiness Probe: http://localhost:8000/ready
- Safe Diagnostics: http://localhost:8000/health/diagnostics

### 3. Frontend Setup (PowerShell)

```powershell
cd frontend
npm install
npm run dev
```

- Command Center UI: http://localhost:5173

---

## Production Deployment & Operational Guidance

### 1. Production Environment Setup

Generate a secure 64-character secret key and create `.env.production`:

```powershell
# Generate secret key
python -c "import secrets; print(secrets.token_hex(32))"
```

Configure production environment variables:
```ini
APP_ENV=production
SECRET_KEY=<your-generated-64-character-hex-secret>
ALLOW_SQLITE_FALLBACK=false
ENABLE_DEMO_LOGINS=false
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
DATABASE_URL=postgresql+asyncpg://ops_user:<strong-password>@db.internal:5432/ops_control
REDIS_URL=redis://redis.internal:6379/0
CORS_ORIGINS=https://control-tower.yourdomain.com
ALLOWED_HOSTS=control-tower.yourdomain.com
```

### 2. Backup and Restore Procedures

#### Database Backup (PostgreSQL):
```bash
# Full logical database dump with custom format (compressed)
pg_dump -h <host> -U <user> -d ops_control -Fc -f ops_control_backup_$(date +%Y%m%d_%H%M%S).dump

# Plain SQL schema-only dump (for auditing)
pg_dump -h <host> -U <user> -d ops_control --schema-only -f ops_control_schema_$(date +%Y%m%d).sql
```

#### Database Restore (PostgreSQL):
```bash
# Restore to a clean target database
pg_restore -h <host> -U <user> -d ops_control_target --clean --if-exists ops_control_backup_YYYYMMDD_HHMMSS.dump
```

### 3. Safe Migration & Rollback Procedure

Always backup before running database migrations in production:

```bash
# 1. Verify current database head
alembic current

# 2. Dry-run SQL statements before executing
alembic upgrade head --sql > migration_dryrun.sql

# 3. Apply migrations transactionally
alembic upgrade head

# 4. Emergency rollback (revert last revision)
alembic downgrade -1
```

---

## Automated Verification & Testing

Run all unit, API regression, model, and configuration tests:

```powershell
# From project root
$env:PYTHONPATH="backend"
python -m pytest backend/tests -v
```

Build frontend production bundle:

```powershell
cd frontend
npm run build
```
