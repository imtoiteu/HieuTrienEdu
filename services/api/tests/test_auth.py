"""Authentication, authorisation and role boundaries."""

from __future__ import annotations

import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from tests.conftest import TEST_PASSWORD


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("correct horse battery")
        assert hashed != "correct horse battery"
        assert verify_password("correct horse battery", hashed)
        assert not verify_password("wrong password", hashed)

    def test_hashes_are_salted(self):
        """Two hashes of one password must differ, or the database leaks shared passwords."""
        assert hash_password("same") != hash_password("same")

    def test_rejects_overlong_password(self):
        # bcrypt silently truncates past 72 bytes; truncating would make two different long
        # passwords interchangeable, so we reject instead.
        with pytest.raises(ValueError):
            hash_password("x" * 73)

    def test_verify_survives_malformed_hash(self):
        assert not verify_password("anything", "not-a-bcrypt-hash")


class TestTokens:
    def test_access_token_roundtrip(self):
        token = create_access_token("42", "student")
        payload = decode_token(token, "access")
        assert payload["sub"] == "42"
        assert payload["role"] == "student"

    def test_refresh_token_is_not_accepted_as_access(self):
        """The whole point of short-lived access tokens is lost if a refresh token works too."""
        refresh = create_refresh_token("42")
        with pytest.raises(InvalidTokenError):
            decode_token(refresh, "access")

    def test_garbage_token_rejected(self):
        with pytest.raises(InvalidTokenError):
            decode_token("not.a.token", "access")


class TestRegistration:
    def test_student_can_register(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "GoodPass123",
                "full_name": "New Student",
                "role": "student",
                "grade": 8,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == "new@example.com"
        assert body["user"]["student_profile"]["grade"] == 8
        assert body["tokens"]["access_token"]

    def test_email_is_normalised(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "MiXeD@Example.Com",
                "password": "GoodPass123",
                "full_name": "Case Test",
            },
        )
        # Registering the same address in a different case must collide, not create a second
        # account that can never log in consistently.
        duplicate = client.post(
            "/api/v1/auth/register",
            json={
                "email": "mixed@example.com",
                "password": "GoodPass123",
                "full_name": "Case Test",
            },
        )
        assert duplicate.status_code == 409

    def test_cannot_self_register_as_teacher(self, client):
        """Otherwise anyone could grant themselves access to every student's data."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "sneaky@example.com",
                "password": "GoodPass123",
                "full_name": "Sneaky",
                "role": "teacher",
            },
        )
        assert response.status_code == 422

    def test_cannot_self_register_as_admin(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "sneaky2@example.com",
                "password": "GoodPass123",
                "full_name": "Sneaky",
                "role": "admin",
            },
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("password", ["short", "12345678", "onlyletters"])
    def test_weak_passwords_rejected(self, client, password):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"weak-{password}@example.com",
                "password": password,
                "full_name": "Weak",
            },
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_succeeds(self, client, student):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": TEST_PASSWORD},
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "student"

    def test_wrong_password_rejected(self, client, student):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_unknown_email_rejected(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": TEST_PASSWORD},
        )
        assert response.status_code == 401

    def test_error_message_does_not_reveal_whether_account_exists(self, client, student):
        wrong_password = client.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": "wrong"},
        )
        unknown_user = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        assert wrong_password.json()["detail"] == unknown_user.json()["detail"]

    def test_refresh_issues_new_tokens(self, client, student):
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": TEST_PASSWORD},
        ).json()
        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login["tokens"]["refresh_token"]}
        )
        assert response.status_code == 200
        assert response.json()["access_token"]


class TestAuthorisation:
    def test_me_requires_a_token(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_returns_the_caller(self, client, student_headers):
        response = client.get("/api/v1/auth/me", headers=student_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "student@example.com"

    def test_student_cannot_reach_teacher_routes(self, client, student_headers):
        assert client.get("/api/v1/teacher/students", headers=student_headers).status_code == 403

    def test_student_cannot_reach_admin_routes(self, client, student_headers):
        assert client.get("/api/v1/admin/overview", headers=student_headers).status_code == 403

    def test_teacher_cannot_reach_admin_routes(self, client, teacher_headers):
        assert client.get("/api/v1/admin/overview", headers=teacher_headers).status_code == 403

    def test_teacher_can_reach_teacher_routes(self, client, teacher_headers, curriculum):
        assert client.get("/api/v1/teacher/students", headers=teacher_headers).status_code == 200

    def test_admin_can_reach_teacher_routes(self, client, admin_headers, curriculum):
        """Admins support teachers, so locking them out of teacher tools helps nobody."""
        assert client.get("/api/v1/teacher/students", headers=admin_headers).status_code == 200

    def test_change_password_requires_the_current_one(self, client, student_headers):
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrong", "new_password": "NewPass123"},
            headers=student_headers,
        )
        assert response.status_code == 400

    def test_change_password_works(self, client, student, student_headers):
        assert (
            client.post(
                "/api/v1/auth/change-password",
                json={"current_password": TEST_PASSWORD, "new_password": "NewPass123"},
                headers=student_headers,
            ).status_code
            == 204
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "student@example.com", "password": "NewPass123"},
            ).status_code
            == 200
        )
