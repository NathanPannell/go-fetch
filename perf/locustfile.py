import os
import random
import uuid

from locust import HttpUser, LoadTestShape, between, task

SEARCH_QUERIES = ["introduction", "summary", "conclusion", "results", "methods", "analysis", "data", "discussion"]
FIXTURES_DIR = "/fixtures"
UPLOAD_FILES = ["small.pdf", "medium.pdf"]
_SCENARIO = os.environ.get("PERF_SCENARIO", "baseline")


class GoFetchUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        self.username = f"perf_{uuid.uuid4().hex[:8]}"
        password = "perfpass123"
        self.client.post("/auth/signup", json={"username": self.username, "password": password})
        resp = self.client.post("/auth/login", json={"username": self.username, "password": password})
        self.token = resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        with open(f"{FIXTURES_DIR}/small.pdf", "rb") as f:
            self.client.post(
                "/documents",
                files={"file": ("small.pdf", f, "application/pdf")},
                headers=self.headers,
            )

    @task(3)
    def search(self):
        q = random.choice(SEARCH_QUERIES)
        with self.client.get(
            f"/search?q={q}",
            headers=self.headers,
            catch_response=True,
            name="/search?q=[query]",
        ) as resp:
            if resp.elapsed.total_seconds() > 2.0:
                resp.failure(f"Search SLO breach: {resp.elapsed.total_seconds():.2f}s > 2.0s")

    @task(1)
    def upload_document(self):
        filename = random.choice(UPLOAD_FILES)
        with open(f"{FIXTURES_DIR}/{filename}", "rb") as f:
            with self.client.post(
                "/documents",
                files={"file": (filename, f, "application/pdf")},
                headers=self.headers,
                catch_response=True,
            ) as resp:
                if resp.status_code != 202:
                    resp.failure(f"Upload returned {resp.status_code}, expected 202")

    @task(1)
    def list_documents(self):
        self.client.get("/documents", headers=self.headers)


# LoadTestShape selected by PERF_SCENARIO
if _SCENARIO == "baseline":
    class ActiveShape(LoadTestShape):
        stages = [
            {"duration": 30, "users": 10, "spawn_rate": 2},
            {"duration": 120, "users": 10, "spawn_rate": 2},
        ]

        def tick(self):
            t = self.get_current_time()
            for stage in self.stages:
                if t < stage["duration"]:
                    return (stage["users"], stage["spawn_rate"])
            return None

elif _SCENARIO == "stress":
    class ActiveShape(LoadTestShape):
        stages = [
            {"duration": 15, "users": 5, "spawn_rate": 5},
            {"duration": 75, "users": 5, "spawn_rate": 5},
            {"duration": 90, "users": 20, "spawn_rate": 10},
            {"duration": 150, "users": 20, "spawn_rate": 10},
            {"duration": 165, "users": 50, "spawn_rate": 15},
            {"duration": 225, "users": 50, "spawn_rate": 15},
            {"duration": 240, "users": 100, "spawn_rate": 25},
            {"duration": 300, "users": 100, "spawn_rate": 25},
        ]

        def tick(self):
            t = self.get_current_time()
            for stage in self.stages:
                if t < stage["duration"]:
                    return (stage["users"], stage["spawn_rate"])
            return None

elif _SCENARIO == "spike":
    class ActiveShape(LoadTestShape):
        stages = [
            {"duration": 60, "users": 10, "spawn_rate": 5},
            {"duration": 90, "users": 100, "spawn_rate": 100},
            {"duration": 120, "users": 10, "spawn_rate": 100},
            {"duration": 210, "users": 10, "spawn_rate": 5},
        ]

        def tick(self):
            t = self.get_current_time()
            for stage in self.stages:
                if t < stage["duration"]:
                    return (stage["users"], stage["spawn_rate"])
            return None

else:
    raise ValueError(f"Unknown PERF_SCENARIO: {_SCENARIO!r}. Valid values: baseline, stress, spike")
