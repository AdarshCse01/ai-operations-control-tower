"""Regression tests for core API endpoints and health checks."""
import pytest
from fastapi.testclient import TestClient
from tests.conftest import get_user_auth_headers


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_connected(client: TestClient, monkeypatch):
    """Verifies that /ready returns 200 and 'ready' status when database is reachable."""
    async def mock_check_ok(timeout_seconds=1.5):
        return True, None

    monkeypatch.setattr("app.main.check_database_connection", mock_check_ok)
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["dependencies"]["database"] == "connected"


def test_ready_unavailable_when_unreachable(client: TestClient, monkeypatch):
    """Verifies that /ready returns HTTP 503 Service Unavailable when database is down and no fallback is active."""
    async def mock_check_fail(timeout_seconds=1.5):
        return False, "Database connection refused"

    monkeypatch.setattr("app.main.check_database_connection", mock_check_fail)
    monkeypatch.setattr("app.main.is_fallback_active", lambda: False)
    response = client.get("/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["dependencies"]["database"] == "unreachable"


def test_health_diagnostics(client: TestClient):
    """Verifies that /health/diagnostics provides safe metadata without secrets."""
    response = client.get("/health/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert "environment" in data
    assert "database" in data
    assert "rate_limiter" in data
    assert "security" in data
    assert "backend" in data["database"]
    assert "fallback_active" in data["database"]


def test_security_headers(client: TestClient):
    """Verifies that defense-in-depth OWASP security headers and CSP are returned."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    # Modern OWASP standard: legacy buggy XSS auditor is explicitly disabled
    assert response.headers.get("x-xss-protection") == "0"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
async def test_cookie_csrf_protection_rejects_missing_header(client: TestClient, make_user):
    """Verifies that state-changing requests using cookie authentication require X-Requested-With header."""
    user = await make_user(role="OPERATIONS_MANAGER")
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user.id), role=user.role, email=user.email)

    # Set cookie without X-Requested-With header on mutating request
    client.cookies.set("access_token", token)
    try:
        response = client.post(
            "/api/v1/recommendations/00000000-0000-0000-0000-000000000001/approval",
            json={"approved": True, "comment": "CSRF test"},
        )
        assert response.status_code == 403
        assert "CSRF protection" in response.json()["detail"]
        assert "X-Requested-With" in response.json()["detail"]
    finally:
        client.cookies.clear()


@pytest.mark.asyncio
async def test_cookie_csrf_protection_permits_with_header(client: TestClient, make_user):
    """Verifies that state-changing requests using cookie authentication succeed with X-Requested-With header."""
    user = await make_user(role="OPERATIONS_MANAGER")
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user.id), role=user.role, email=user.email)

    client.cookies.set("access_token", token)
    try:
        # Calling non-existent recommendation returns 404 (passed authentication and CSRF guard!)
        response = client.post(
            "/api/v1/recommendations/00000000-0000-0000-0000-000000000001/approval",
            json={"approved": True, "comment": "Legitimate with CSRF header"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        # Should NOT be 403 CSRF forbidden
        assert response.status_code == 404
    finally:
        client.cookies.clear()


@pytest.mark.asyncio
async def test_cookie_csrf_protection_allows_safe_reads(client: TestClient, make_user):
    """Verifies that safe idempotent read requests (GET) via cookie do not require X-Requested-With."""
    user = await make_user(role="VIEWER")
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user.id), role=user.role, email=user.email)

    client.cookies.set("access_token", token)
    try:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["email"] == user.email
    finally:
        client.cookies.clear()


@pytest.mark.asyncio
async def test_bearer_token_not_blocked_by_csrf_check(client: TestClient, make_user):
    """Verifies that API clients authenticating via Bearer header do not require X-Requested-With."""
    user = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(user)

    response = client.post(
        "/api/v1/recommendations/00000000-0000-0000-0000-000000000001/approval",
        json={"approved": True, "comment": "Bearer client"},
        headers=headers,
    )
    # Passes authentication and CSRF guard; reaches domain validation
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_summary_shape(client: TestClient, make_user):
    user = await make_user(role="VIEWER")
    headers = get_user_auth_headers(user)

    response = client.get("/api/v1/dashboard/summary", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["orders_today"] > 0
    assert len(payload["trend"]) >= 1


@pytest.mark.asyncio
async def test_risks_have_scores(client: TestClient, make_user):
    user = await make_user(role="ANALYST")
    headers = get_user_auth_headers(user)

    response = client.get("/api/v1/risks", headers=headers)
    assert response.status_code == 200
    assert all(0 <= risk["score"] <= 100 for risk in response.json()["items"])


@pytest.mark.asyncio
async def test_approval_flow(client: TestClient, make_user):
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    recommendations = client.get("/api/v1/recommendations", headers=headers).json()["items"]
    assert recommendations
    response = client.post(
        f"/api/v1/recommendations/{recommendations[0]['id']}/approval",
        json={"approved": True, "comment": "Reviewed"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_cors_preflight_trusted_origins(client: TestClient):
    """Verifies that localhost and 192.168.31.146 origins succeed in CORS preflight."""
    for origin in ["http://localhost:5173", "http://192.168.31.146:5173", "http://127.0.0.1:5173"]:
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_disallowed_origin(client: TestClient):
    """Verifies that untrusted origins are strictly rejected with 400 Disallowed CORS origin."""
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://malicious-attacker.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 400
    assert "Disallowed CORS origin" in response.text

