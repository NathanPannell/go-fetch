import random
import uuid

from locust import HttpUser, constant_throughput, task

SEARCH_QUERIES = [
    "introduction",
    "conclusion",
    "methodology",
    "results",
    "abstract",
    "background",
    "discussion",
    "references",
    "analysis",
    "summary",
]


class GoFetchUser(HttpUser):
    wait_time = constant_throughput(1)

    def on_start(self):
        self.username = f"user_{uuid.uuid4().hex[:8]}"
        self.client.post("/auth/signup", json={"username": self.username, "password": "testpass"})
        resp = self.client.post("/auth/login", json={"username": self.username, "password": "testpass"})
        self.token = resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        with open("/fixtures/medium.pdf", "rb") as f:
            self.client.post("/documents", files={"file": f}, headers=self.headers)

    @task(6)
    def search(self):
        q = random.choice(SEARCH_QUERIES)
        self.client.get(f"/search?q={q}", headers=self.headers)

    @task(3)
    def list_documents(self):
        self.client.get("/documents", headers=self.headers)

    @task(1)
    def upload_document(self):
        with open("/fixtures/medium.pdf", "rb") as f:
            self.client.post("/documents", files={"file": f}, headers=self.headers)
