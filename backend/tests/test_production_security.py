"""Hermetic direct-API regressions. Real JWT, middleware, parsing and authorization;
only persistence/provider boundaries are isolated from the user's live data.
"""
import base64
from datetime import date, datetime, timezone
import hashlib
import hmac
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.endpoints import auth, claims, comparisons, coverage, policies, portfolio, qa
from app.core.config import Settings, get_settings
from app.core.logging_security import redact_log_text
from app.core.security import COOKIE_ACCESS_TOKEN_KEY, COOKIE_CSRF_TOKEN_KEY, create_access_token, verify_supabase_token
from app.main import create_application
from app.schemas.claim import ClaimRecord
from app.schemas.policy import PolicyExtractionResult


@pytest.fixture
def api(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_issuer", "claimwise-test")
    monkeypatch.setattr(settings, "jwt_secret", "isolated-production-security-test-secret-8137")
    monkeypatch.setattr(settings, "cors_origins", ["https://claimwise.test"])
    monkeypatch.setattr(auth.audit_repo, "record_event", AsyncMock())
    now = datetime.now(timezone.utc)
    records = {
        owner: PolicyExtractionResult(policy_id=owner, user_id=owner, document_name=f"{owner}.pdf",
            document_hash=hashlib.sha256(owner.encode()).hexdigest(), file_size_bytes=30, total_pages=1,
            total_clauses=0, is_scanned=False, has_extractable_text=True, clauses=[],
            uploaded_at=now, status="success", message="OK")
        for owner in ("alice", "bob", "usr-fc94c05944", "usr-demo-policyholder")
    }
    for module in (policies, coverage, qa):
        monkeypatch.setattr(module, "_dev_policy_store", records)
    monkeypatch.setattr(policies, "_policy_pdf_path", lambda digest: tmp_path / f"{digest}.pdf")
    for record in records.values():
        (tmp_path / f"{record.document_hash}.pdf").write_bytes(b"%PDF-1.4\nTest document")
    claim = ClaimRecord(id="bob-claim", user_id="bob", policy_id="bob", incident_date=date.today(),
                        total_billed_cents=0, status="draft", created_at=now, updated_at=now)
    monkeypatch.setattr(claims.claim_repo, "get_claim", lambda _: claim)
    monkeypatch.setattr(claims.claim_repo, "save_claim", AsyncMock())
    monkeypatch.setattr(claims.claim_repo, "get_bill_extraction", lambda _: SimpleNamespace(user_id="bob"))
    monkeypatch.setattr(comparisons.comparison_repo, "get_comparison", lambda _: SimpleNamespace(id="comparison", user_id="bob"))
    monkeypatch.setattr(auth, "_user_db", {
        "alice@example.test": dict(id="alice", email="alice@example.test", full_name="Alice Example",
                                   role="policyholder", tier=1, password_hash=auth._hash_password("secret-password")),
        **{user["email"]: dict(user) for user in auth._DEMO_USERS.values()},
    })
    monkeypatch.setattr(auth, "_save_user_to_db", lambda _: None)
    app = create_application()
    with TestClient(app, base_url="https://claimwise.test") as client:
        yield client, records


def bearer(owner="alice"):
    return {"Authorization": "Bearer " + create_access_token(owner, f"{owner}@example.test")}


def signed(payload, header=None):
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    body = encode(header if header is not None else {"alg": "HS256"}) + "." + encode(payload)
    signature = hmac.new(get_settings().jwt_secret.encode(), body.encode(), hashlib.sha256).digest()
    return body + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


@pytest.mark.parametrize("claim,value", [("exp", None), ("exp", "9999999999"), ("exp", True), ("exp", []),
    ("exp", 1), ("aud", None), ("aud", "other"), ("iss", None), ("iss", "other"),
    ("sub", {}), ("sub", ""), ("tier", "admin"), ("tier", True), ("tier", 5),
    ("iat", None), ("iat", 9999999999), ("nbf", 9999999999), ("email", [])])
def test_malformed_signed_claims_fail_closed(api, claim, value):
    now = int(datetime.now(timezone.utc).timestamp())
    payload = dict(sub="alice", email="alice@example.test", tier=1, exp=now+600, iat=now, aud="authenticated", iss="claimwise-test")
    if value is None:
        payload.pop(claim, None)
    else:
        payload[claim] = value
    response = api[0].get("/api/v1/policies", headers={"Authorization": "Bearer " + signed(payload)})
    assert response.status_code == 401


@pytest.mark.parametrize("payload,header", [([], None), ({}, []), ({}, {"alg": "none"}), ({}, {"alg": "HS512"})])
def test_malformed_jwt_container_and_algorithm(api, payload, header):
    assert api[0].get("/api/v1/policies", headers={"Authorization": "Bearer " + signed(payload, header)}).status_code == 401


def test_jwt_roundtrip_issuer_signature_and_expiry(api):
    token = create_access_token("alice", "alice@example.test")
    assert verify_supabase_token(token).id == "alice"
    for invalid in (token + "x", create_access_token("alice", "alice@example.test", exp_seconds=-1)):
        with pytest.raises(HTTPException) as exc:
            verify_supabase_token(invalid)
        assert exc.value.status_code == 401


@pytest.mark.parametrize("path", ["/policies", "/policies/bob", "/policies/bob/pdf", "/claims", "/claims/bob-claim",
    "/claims/bob-claim/documents/doc", "/comparisons", "/comparisons/foreign", "/qa/status", "/qa/benchmark", "/audit/events", "/auth/me"])
def test_sensitive_gets_require_credentials(api, path):
    assert api[0].get("/api/v1" + path).status_code == 401


def test_policy_listing_rejects_anonymous_development_request(api, monkeypatch):
    client, records = api
    monkeypatch.setattr(get_settings(), "environment", "development")
    records["dev-user-policy"] = records["alice"].model_copy(
        update={"policy_id": "dev-user-policy", "user_id": "dev-user-001"}
    )

    response = client.get("/api/v1/policies")

    assert response.status_code == 401


@pytest.mark.parametrize("owner", ["bob", "usr-fc94c05944", "usr-demo-policyholder"])
def test_policy_allowlist_does_not_bypass_owner(api, owner):
    client, records = api
    for path in (f"/policies/{owner}", f"/policies/{owner}/pdf"):
        assert client.get("/api/v1" + path, headers=bearer()).status_code == 403
    assert client.delete(f"/api/v1/policies/{owner}", headers=bearer()).status_code == 403
    assert owner in records


def test_cookie_owner_can_view_download_and_delete_own_policy(api, monkeypatch):
    client, records = api
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, create_access_token("alice", "alice@example.test"))
    client.cookies.set(COOKIE_CSRF_TOKEN_KEY, "csrf-alice")
    monkeypatch.setattr(policies.hybrid_retrieval_service, "remove_policy", lambda _: None)
    assert [p["policy_id"] for p in client.get("/api/v1/policies").json()] == ["alice"]
    assert client.get("/api/v1/policies/alice").status_code == 200
    response = client.get("/api/v1/policies/alice/pdf")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/policies/bob/pdf").status_code == 403
    assert client.delete("/api/v1/policies/alice", headers={"X-CSRF-Token": "csrf-alice"}).status_code == 204
    assert "alice" not in records and "bob" in records


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/claims/bob-claim", None), ("get", "/claims/bob-claim/documents/doc", None),
    ("get", "/claims/bob-claim/guidance", None),
    ("patch", "/claims/bob-claim/intake", {"incident_description": "Changed by another user"}),
    ("post", "/claims/bob-claim/adjudicate", {}),
    ("post", "/claims/guidance/evaluate", {"policy_id": "bob", "incident_date": "2026-10-12", "incident_category": "other"}),
    ("post", "/claims", {"bill_id": "bill", "policy_id": "alice"}),
    ("get", "/comparisons/foreign", None), ("get", "/comparisons/foreign/pdf", None),
    ("post", "/comparisons", {"policy_ids": ["alice", "bob"]}),
    ("post", "/comparisons/overlaps", {"policy_ids": ["alice", "bob"]}),
    ("post", "/portfolio/analyze", {"policy_ids": ["alice", "bob"]}),
    ("post", "/qa/ask", {"policy_id": "bob", "question": "What is covered?"}),
    ("post", "/coverage/analyze", {"policy_id": "bob", "situation": "My luggage was lost"}),
    ("get", "/coverage/report/bob", None),
])
def test_cross_user_sensitive_operations(api, method, path, payload):
    kwargs = {"headers": bearer()}
    if payload is not None:
        kwargs["json"] = payload
    response = api[0].request(method, "/api/v1" + path, **kwargs)
    assert response.status_code == 403, (path, response.status_code, response.text)


def test_claim_owner_can_read_and_update_own_record(api):
    client, _ = api
    assert client.get("/api/v1/claims/bob-claim", headers=bearer("bob")).status_code == 200
    response = client.patch("/api/v1/claims/bob-claim/intake", headers=bearer("bob"), json={"incident_description": "Updated incident notes"})
    assert response.status_code == 200 and response.json()["incident_description"] == "Updated incident notes"


@pytest.mark.parametrize("header", [None, "incorrect", "\u00e9"])
def test_missing_invalid_non_ascii_csrf_rejected(api, header):
    client, _ = api
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, create_access_token("alice", "alice@example.test"))
    client.cookies.set(COOKIE_CSRF_TOKEN_KEY, "correct")
    headers = {} if header is None else {"x-csrf-token": header.encode("utf-8")}
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 403


def test_untrusted_host_cannot_whitelist_origin(api):
    response = api[0].post("/api/v1/auth/login", headers={"Origin": "https://evil.test", "Host": "evil.test"}, json={"email": "alice@example.test", "password": "secret-password"})
    assert response.status_code == 403
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["strict-transport-security"].startswith("max-age=")


def test_production_login_restore_cookie_flags_logout(api, monkeypatch):
    client, _ = api
    response = client.post("/api/v1/auth/login", json={"email": "alice@example.test", "password": "secret-password"})
    assert response.status_code == 200
    cookie = next(c for c in response.headers.get_list("set-cookie") if c.startswith(COOKIE_ACCESS_TOKEN_KEY + "="))
    assert all(flag in cookie.lower() for flag in ("httponly", "secure", "samesite=lax", "path=/"))
    assert client.get("/api/v1/auth/me").json()["id"] == "alice"
    csrf = response.json()["csrf_token"]
    monkeypatch.setattr(auth.audit_repo, "record_event", AsyncMock(side_effect=RuntimeError("storage unavailable")))
    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert len(response.headers.get_list("set-cookie")) == 2
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_can_clear_cookies(api):
    client, _ = api
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, create_access_token("alice", "alice@example.test", exp_seconds=-1))
    client.cookies.set(COOKIE_CSRF_TOKEN_KEY, "expired-session-csrf")
    assert client.get("/api/v1/auth/me").status_code == 401
    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "expired-session-csrf"})
    assert response.status_code == 200
    assert all("max-age=0" in c.lower() for c in response.headers.get_list("set-cookie"))


def test_production_demo_token_password_and_route_rejected(api):
    client, _ = api
    assert client.post("/api/v1/auth/demo", json={"role": "policyholder"}).status_code == 403
    response = client.post("/api/v1/auth/login", json={"email": "alex.morgan@claimwise-demo.com", "password": "password123"})
    assert response.status_code == 401
    assert client.get("/api/v1/policies", headers=bearer("usr-demo-policyholder")).status_code == 401
    assert client.get("/api/v1/qa/benchmark?live=true", headers=bearer()).status_code == 403


def test_signup_cannot_self_assign_admin_or_tier(api):
    client, _ = api
    payload = dict(email="new@example.test", full_name="New User", password="secret-password", role="admin", tier=4, user_id="bob")
    assert client.post("/api/v1/auth/signup", json=payload).status_code == 422
    payload["role"] = "policyholder"
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    assert response.json()["user"]["tier"] == 1
    assert verify_supabase_token(response.json()["access_token"]).id != "bob"


def test_password_work_factor_upgrades_at_login(api):
    client, _ = api
    password = "secret-password"
    old = hashlib.pbkdf2_hmac("sha256", password.encode(), b"old-salt", 100_000).hex()
    record = auth._user_db["alice@example.test"]
    record["password_hash"] = "pbkdf2:sha256:100000:old-salt:" + old
    assert client.post("/api/v1/auth/login", json={"email": record["email"], "password": password}).status_code == 200
    assert record["password_hash"].startswith("pbkdf2:sha256:600000:")
    assert auth._verify_password(password, record["password_hash"])


@pytest.mark.parametrize("name,mime,content", [("fake.pdf", "application/pdf", b"hello"),
    ("fake.png", "image/png", b"%PDF-1.4"), ("bad.exe", "application/pdf", b"%PDF-1.4"),
    ("empty.pdf", "application/pdf", b""), ("wrong.pdf", "text/html", b"%PDF-1.4")])
def test_upload_content_extension_mime_validation(api, name, mime, content):
    assert api[0].post("/api/v1/claims/bob-claim/documents", headers=bearer("bob"), files={"file": (name, content, mime)}).status_code in {400, 415}


def test_claim_document_upload_cannot_write_to_other_owner(api):
    assert api[0].post("/api/v1/claims/bob-claim/documents", headers=bearer(), files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")}).status_code == 403


def test_policy_path_requires_sha256():
    for digest in ("../private", "hash/../../secret", "not-a-hash"):
        with pytest.raises(HTTPException):
            policies._policy_pdf_path(digest)


def test_logging_redacts_credentials_and_exception_values(caplog):
    synthetic = "this-is-a-synthetic-secret-value"
    text = redact_log_text("password=" + synthetic + " postgresql://user:fake@host/db alice@example.test", (synthetic,))
    assert synthetic not in text and "fake" not in text and "alice@example" not in text
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("full private medical document")
        except RuntimeError:
            logging.getLogger("claimwise.test").exception("Synthetic failure")
    assert "full private medical document" not in caplog.text


def production_settings(**overrides):
    values = dict(_env_file=None, environment="production", debug=False,
                  jwt_secret="b59cf8d610274ef398b5d260741fac03f4bc122ea9a302af5a4868d3269c8f41",
                  database_url="postgresql://test_user:synthetic-credential@db.example.test/test?sslmode=require",
                  cors_origins=["https://claimwise.test"], jwt_issuer="claimwise-test")
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize("overrides", [{"jwt_secret": "a"*40}, {"jwt_secret": "CHANGE-ME-"*8},
    {"jwt_secret": ""}, {"jwt_issuer": None}, {"jwt_audience": ""}, {"debug": True},
    {"cors_origins": ["*"]}, {"cors_origins": ["http://claimwise.test"]},
    {"cors_origins": ["https://claimwise.test/path"]}, {"database_url": "placeholder"},
    {"environment": "prodution"}])
def test_invalid_production_settings_fail_without_echoing_secrets(overrides):
    with pytest.raises(ValueError) as error:
        production_settings(**overrides)
    assert "synthetic-credential" not in str(error.value)


def test_valid_production_configuration():
    assert production_settings().environment == "production"


def test_validation_does_not_echo_password(api):
    password = "x" * 129
    response = api[0].post("/api/v1/auth/login", json={"email": "alice@example.test", "password": password})
    assert response.status_code == 422 and password not in response.text


def test_audit_records_are_scoped_and_nested_metadata_redacted(api, monkeypatch):
    from app.services.audit_service import audit_service
    data = audit_service.sanitize_metadata({"items": [{"password": "private-pass"}, {"email": "bob@example.test"}, ["SSN 123-45-6789"]]})
    assert "private-pass" not in json.dumps(data) and "bob@example.test" not in json.dumps(data) and "123-45-6789" not in json.dumps(data)
    events = [audit_service.build_event(action="test", resource_type="policy", resource_id=owner, user_id=owner,
                sequence_number=i+1, previous_hash="0"*64) for i, owner in enumerate(("alice", "bob"))]
    monkeypatch.setattr(auth.audit_repo, "_sync_events", lambda: None)
    monkeypatch.setattr(auth.audit_repo, "_events", events)
    response = api[0].get("/api/v1/audit/events?user_id=bob", headers=bearer())
    assert response.status_code == 200
    assert [event["user_id"] for event in response.json()] == ["alice"]


def test_sandbox_idempotency_is_scoped_to_owner_and_claim():
    from app.services.sandbox_service import MockInsurerSandboxService
    from app.schemas.claim import SandboxSubmitRequest
    service = MockInsurerSandboxService()
    now = datetime.now(timezone.utc)
    request = SandboxSubmitRequest(user_confirmed=True, idempotency_key="same-client-key", requested_scenario="approve")
    first = ClaimRecord(id="first", user_id="alice", policy_id="alice", incident_date=date.today(),
                        total_billed_cents=0, status="analyzed", created_at=now, updated_at=now)
    second = first.model_copy(update={"id": "second", "user_id": "bob", "policy_id": "bob"})
    one = service.simulate_submission(first, request)
    assert service.simulate_submission(first, request).submission_id == one.submission_id
    assert service.simulate_submission(second, request).submission_id != one.submission_id


def test_cookie_owner_can_read_saved_comparison(api, monkeypatch):
    from app.schemas.comparison import ComparisonCreateRequest
    client, records = api
    record = comparisons.comparison_service.create_comparison(
        ComparisonCreateRequest(policy_ids=["alice", "bob"]), user_id="alice", authorized_policy_store=records)
    monkeypatch.setattr(comparisons.comparison_repo, "get_comparison", lambda _: record)
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, create_access_token("alice", "alice@example.test"))
    assert client.get("/api/v1/comparisons/owned").status_code == 200


@pytest.mark.asyncio
async def test_audit_write_failure_does_not_create_uncommitted_chain(monkeypatch):
    from app.core.exceptions import DatabaseConnectionException
    from app.db.audit_repo import AuditRepository
    from app.db.local_store import local_store
    from app.schemas.audit import AuditEventCreate
    repo = AuditRepository()

    def unavailable(_):
        raise RuntimeError("synthetic unavailable database")

    monkeypatch.setattr(local_store, "record_audit_event_transactional", unavailable)
    with pytest.raises(DatabaseConnectionException):
        await repo.record_event(AuditEventCreate(action="test", resource_type="test", user_id="alice"))
    assert repo._events == []


def test_provider_failure_does_not_return_exception_body(api, monkeypatch):
    from app.schemas.qa import RetrievedClause
    from app.services.qa_service import QAService
    service = QAService()
    monkeypatch.setattr(service, "is_configured", lambda: True)

    def unavailable(*args):
        raise RuntimeError("sensitive-provider-response-secret")

    monkeypatch.setattr(service, "_call_gemini_api", unavailable)
    evidence = RetrievedClause(clause_id="A", policy_id="alice", document_hash="a"*64,
        page_number=1, clause_heading="Evidence", text="The policy covers emergency care.", fused_rank=1, rrf_score=0.1)
    result = service.generate_grounded_answer(question="What emergency care is covered?", retrieved_clauses=[evidence],
        authorized_policy_ids=["alice"], retrieval_mode="degraded_bm25_only")
    assert result.evidence_sufficient is False
    assert "sensitive-provider-response-secret" not in result.model_dump_json()


def test_operational_status_only_lists_current_users_policy_ids(api, monkeypatch):
    monkeypatch.setattr(qa.hybrid_retrieval_service._bm25, "get_indexed_policy_ids", lambda: ["alice", "bob"])
    response = api[0].get("/api/v1/qa/status", headers=bearer())
    assert response.status_code == 200
    assert response.json()["bm25_lexical"]["active_indexed_policies"] == ["alice"]


def test_cors_preflight_allows_only_explicit_origin_and_headers(api):
    client, _ = api
    headers = {"Origin": "https://claimwise.test", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type,X-CSRF-Token"}
    response = client.options("/api/v1/claims", headers=headers)
    assert response.status_code == 200 and response.headers["access-control-allow-origin"] == "https://claimwise.test"
    headers["Origin"] = "https://evil.test"
    assert client.options("/api/v1/claims", headers=headers).status_code == 400
