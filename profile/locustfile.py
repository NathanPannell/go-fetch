import uuid

from locust import HttpUser, between, task


class GoFetchUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.username = f"user_{uuid.uuid4().hex[:8]}"
        self.client.post("/auth/signup", json={"username": self.username, "password": "testpass"})
        resp = self.client.post("/auth/login", json={"username": self.username, "password": "testpass"})
        self.token = resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        with open("/fixtures/small.pdf", "rb") as f:
            self.client.post("/documents", files={"file": f}, headers=self.headers)

    @task(3)
    def search(self):
        self.client.get("/search?q=introduction", headers=self.headers)

    @task(1)
    def list_documents(self):
        self.client.get("/documents", headers=self.headers)
