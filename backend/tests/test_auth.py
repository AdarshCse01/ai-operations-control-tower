"""Tests for user registration, authentication, token lifecycle, and session cookies."""
import pytest
from fastapi.testclient import TestClient
from app.models.user import User
from tests.conftest import get_user_auth_headers


def test_register_success(client: TestClient):
    payload = {
        "email": "operator_new@example.com",
        "password": "Password123",
        "full_name": "Operations Operator",
        "role": "OPERATIONS_MANAGER",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "operator_new@example.com"
    assert data["role"] == "OPERATIONS_MANAGER"
    assert "id" in data
    # Ensure sensitive credentials are never returned
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_email(client: TestClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "Password123",
        "full_name": "First User",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_register_password_validation(client: TestClient):
    # Too short (<8 chars)
    res_short = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "pass1", "full_name": "User"},
    )
    assert res_short.status_code == 422

    # Missing numbers
    res_no_num = client.post(
        "/api/v1/auth/register",
        json={"email": "nonum@example.com", "password": "passwordonly", "full_name": "User"},
    )
    assert res_no_num.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: TestClient, make_user):
    user = await make_user(
        email="login_user@example.com",
        password="MySecretPassword123",
        role="ANALYST",
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login_user@example.com", "password": "MySecretPassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login_user@example.com"
    assert data["user"]["role"] == "ANALYST"
    # Never return password hash
    assert "hashed_password" not in data["user"]
    # Check that access_token cookie was set
    assert "access_token" in response.cookies


def test_login_incorrect_password(client: TestClient):
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrong_pw@example.com", "password": "CorrectPass1", "full_name": "User"},
    )
    # Attempt login with wrong password
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong_pw@example.com", "password": "WrongPassword99"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_nonexistent_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123"},
    )
    assert response.status_code == 401
    # Leaks no details about account nonexistence
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_deactivated_user(client: TestClient, make_user):
    await make_user(
        email="inactive@example.com",
        password="Password123",
        is_active=False,
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "Password123"},
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_user_profile(client: TestClient, make_user):
    user = await make_user(role="OPERATIONS_MANAGER", email="mgr@example.com")
    headers = get_user_auth_headers(user)

    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "mgr@example.com"
    assert data["role"] == "OPERATIONS_MANAGER"
    assert "recommendations:decide" in data["permissions"]
    assert "dashboard:read" in data["permissions"]
    assert "hashed_password" not in data


def test_get_current_user_profile_unauthenticated(client: TestClient):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_logout(client: TestClient):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_config(client: TestClient):
    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert "environment" in data
    assert "demo_logins_enabled" in data
    assert "password_policy" in data
    assert data["password_policy"]["min_length"] == 8
