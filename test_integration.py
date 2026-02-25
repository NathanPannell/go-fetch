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
    assert response.status_code == 200
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
    assert response.status_code == 200
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
