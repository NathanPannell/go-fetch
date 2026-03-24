import io
import time
import requests
import uuid

BASE_URL = "http://app:8080"


def test_authentication_workflow():
    username = f"alice_{uuid.uuid4().hex[:8]}"
    password = "securepassword123"

    # 1. POST /auth/signup - Success
    response = requests.post(f"{BASE_URL}/auth/signup", json={
        "username": username,
        "password": password
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data == {
        "message": "User created successfully",
        "user_id": data.get("user_id")
    }
    user_id = data.get("user_id")
    assert user_id is not None

    # 2. POST /auth/signup - Conflict
    response = requests.post(f"{BASE_URL}/auth/signup", json={
        "username": username,
        "password": password
    })
    assert response.status_code == 409
    assert response.json() == {
        "error": "Username already exists"
    }

    # 3. POST /auth/login - Success
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": password
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert "token" in data
    assert data["user_id"] == user_id

    # 4. POST /auth/login - Invalid Credentials (wrong password)
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert response.json() == {
        "error": "Invalid credentials"
    }

    # 5. POST /auth/login - Invalid Credentials (non-existent user)
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": f"not_{username}",
        "password": password
    })
    assert response.status_code == 401
    assert response.json() == {
        "error": "Invalid credentials"
    }


def _signup_and_login(suffix=""):
    username = f"user_{uuid.uuid4().hex[:8]}{suffix}"
    password = "testpass123"
    requests.post(f"{BASE_URL}/auth/signup", json={"username": username, "password": password})
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    token = resp.json()["token"]
    return token


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _minimal_pdf():
    """Return bytes for a minimal valid PDF with one page of text."""
    content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Hello World) Tj ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000370 00000 n
trailer << /Size 6 /Root 1 0 R >>
startxref
441
%%EOF"""
    return content


def test_document_upload_and_list():
    token = _signup_and_login()
    headers = _auth_headers(token)

    # Upload a PDF
    pdf_bytes = _minimal_pdf()
    response = requests.post(
        f"{BASE_URL}/documents",
        headers=headers,
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 202, response.text
    data = response.json()
    assert data["message"] == "PDF uploaded, processing started"
    assert "document_id" in data
    assert data["status"] == "processing"
    document_id = data["document_id"]

    # List documents
    response = requests.get(f"{BASE_URL}/documents", headers=headers)
    assert response.status_code == 200, response.text
    docs = response.json()
    assert isinstance(docs, list)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["document_id"] == document_id
    assert doc["filename"] == "test.pdf"
    assert "upload_date" in doc
    assert doc["status"] in ("processing", "ready", "failed")
    assert "page_count" in doc


def test_document_user_isolation():
    """Alice cannot see Bob's documents."""
    token_alice = _signup_and_login("_alice")
    token_bob = _signup_and_login("_bob")

    pdf_bytes = _minimal_pdf()
    # Alice uploads
    requests.post(
        f"{BASE_URL}/documents",
        headers=_auth_headers(token_alice),
        files={"file": ("alice.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )

    # Bob lists - should see no documents
    response = requests.get(f"{BASE_URL}/documents", headers=_auth_headers(token_bob))
    assert response.status_code == 200
    assert response.json() == []


def test_document_delete():
    token = _signup_and_login()
    headers = _auth_headers(token)

    pdf_bytes = _minimal_pdf()
    upload_resp = requests.post(
        f"{BASE_URL}/documents",
        headers=headers,
        files={"file": ("del.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code == 202
    document_id = upload_resp.json()["document_id"]

    # Delete it
    response = requests.delete(f"{BASE_URL}/documents/{document_id}", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["message"] == "Document and all associated data deleted"
    assert data["document_id"] == document_id

    # Confirm gone from list
    list_resp = requests.get(f"{BASE_URL}/documents", headers=headers)
    ids = [d["document_id"] for d in list_resp.json()]
    assert document_id not in ids

    # Delete again → 404
    response = requests.delete(f"{BASE_URL}/documents/{document_id}", headers=headers)
    assert response.status_code == 404
    assert response.json() == {"error": "Document not found or not owned by user"}


def test_delete_other_users_document():
    """User cannot delete another user's document."""
    token_alice = _signup_and_login("_a2")
    token_bob = _signup_and_login("_b2")

    pdf_bytes = _minimal_pdf()
    upload_resp = requests.post(
        f"{BASE_URL}/documents",
        headers=_auth_headers(token_alice),
        files={"file": ("private.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    document_id = upload_resp.json()["document_id"]

    response = requests.delete(f"{BASE_URL}/documents/{document_id}", headers=_auth_headers(token_bob))
    assert response.status_code == 404


def test_search():
    token = _signup_and_login()
    headers = _auth_headers(token)

    pdf_bytes = _minimal_pdf()
    requests.post(
        f"{BASE_URL}/documents",
        headers=headers,
        files={"file": ("search_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )

    # Wait for async processing
    time.sleep(10)

    response = requests.get(f"{BASE_URL}/search?q=hello+world", headers=headers)
    assert response.status_code == 200, response.text
    results = response.json()
    assert isinstance(results, list)
    assert len(results) <= 5
    for r in results:
        assert "text" in r
        assert "score" in r
        assert "document_id" in r
        assert "filename" in r


def test_search_user_isolation():
    """Search only returns current user's results."""
    token_alice = _signup_and_login("_sa")
    token_bob = _signup_and_login("_sb")

    pdf_bytes = _minimal_pdf()
    requests.post(
        f"{BASE_URL}/documents",
        headers=_auth_headers(token_alice),
        files={"file": ("alice_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    time.sleep(10)

    # Bob searches — should get no results (he has no documents)
    response = requests.get(f"{BASE_URL}/search?q=hello", headers=_auth_headers(token_bob))
    assert response.status_code == 200
    assert response.json() == []
