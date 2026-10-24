"""Tests for Role-Based Access Control (RBAC) permissions matrix and token verification."""
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app.core.security import create_access_token
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_expired_token_rejected(client: TestClient, make_user):
    user = await make_user(role="VIEWER")
    # Generate token that expired 10 minutes ago
    expired_token = create_access_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
        expires_delta=timedelta(minutes=-10),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/v1/dashboard/summary", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_tampered_token_rejected(client: TestClient, make_user):
    user = await make_user(role="VIEWER")
    token = create_access_token(subject=str(user.id), role=user.role, email=user.email)
    tampered = token[:-5] + "XXXXX"
    headers = {"Authorization": f"Bearer {tampered}"}
    response = client.get("/api/v1/dashboard/summary", headers=headers)
    assert response.status_code == 401


def test_unauthenticated_endpoints_rejected(client: TestClient):
    # Verify all protected endpoints reject unauthenticated access with 401
    assert client.get("/api/v1/dashboard/summary").status_code == 401
    assert client.get("/api/v1/risks").status_code == 401
    assert client.get("/api/v1/recommendations").status_code == 401
    assert client.post("/api/v1/recommendations/REC-001/approval", json={"approved": True}).status_code == 401
    assert client.get("/api/v1/users").status_code == 401


@pytest.mark.asyncio
async def test_viewer_role_access(client: TestClient, make_user):
    viewer = await make_user(role="VIEWER")
    headers = get_user_auth_headers(viewer)

    # Permitted: dashboard summary and recommendations read
    assert client.get("/api/v1/dashboard/summary", headers=headers).status_code == 200
    assert client.get("/api/v1/recommendations", headers=headers).status_code == 200

    # Denied: risk intelligence (requires ANALYTICS_READ)
    res_risks = client.get("/api/v1/risks", headers=headers)
    assert res_risks.status_code == 403

    # Denied: approval decisions (requires RECOMMENDATION_DECIDE)
    res_appr = client.post("/api/v1/recommendations/REC-001/approval", json={"approved": True}, headers=headers)
    assert res_appr.status_code == 403

    # Denied: user administration
    res_users = client.get("/api/v1/users", headers=headers)
    assert res_users.status_code == 403


@pytest.mark.asyncio
async def test_analyst_role_access(client: TestClient, make_user):
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    # Permitted: dashboard, recommendations, and risk analytics
    assert client.get("/api/v1/dashboard/summary", headers=headers).status_code == 200
    assert client.get("/api/v1/recommendations", headers=headers).status_code == 200
    assert client.get("/api/v1/risks", headers=headers).status_code == 200

    # Denied: approval decisions
    assert client.post("/api/v1/recommendations/REC-001/approval", json={"approved": True}, headers=headers).status_code == 403

    # Denied: user administration
    assert client.get("/api/v1/users", headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_operations_manager_role_access(client: TestClient, make_user):
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    # Permitted: dashboard, recommendations, risks
    assert client.get("/api/v1/dashboard/summary", headers=headers).status_code == 200
    assert client.get("/api/v1/recommendations", headers=headers).status_code == 200
    assert client.get("/api/v1/risks", headers=headers).status_code == 200

    # Permitted: recording recommendation decisions
    recs = client.get("/api/v1/recommendations", headers=headers).json()["items"]
    assert recs
    appr_res = client.post(
        f"/api/v1/recommendations/{recs[0]['id']}/approval",
        json={"approved": True, "comment": "Manager approved"},
        headers=headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"
    assert appr_res.json()["actor"] == manager.email

    # Denied: user administration
    assert client.get("/api/v1/users", headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_admin_role_access(client: TestClient, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    # Admin has all permissions
    assert client.get("/api/v1/dashboard/summary", headers=headers).status_code == 200
    assert client.get("/api/v1/risks", headers=headers).status_code == 200
    assert client.get("/api/v1/recommendations", headers=headers).status_code == 200
    assert client.get("/api/v1/users", headers=headers).status_code == 200

    recs = client.get("/api/v1/recommendations", headers=headers).json()["items"]
    appr_res = client.post(
        f"/api/v1/recommendations/{recs[0]['id']}/approval",
        json={"approved": False, "comment": "Admin rejected"},
        headers=headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "rejected"
