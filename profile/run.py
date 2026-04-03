import csv
import datetime
import os
import subprocess
import threading
import time

import docker


def collect_stats(results_dir, stop_event):
    client = docker.from_env()
    path = os.path.join(results_dir, "stats.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "container", "cpu_pct", "mem_mb"])
        while not stop_event.is_set():
            ts = datetime.datetime.utcnow().isoformat()
            for c in client.containers.list():
                try:
                    s = c.stats(stream=False)
                    cpu_delta = (
                        s["cpu_stats"]["cpu_usage"]["total_usage"]
                        - s["precpu_stats"]["cpu_usage"]["total_usage"]
                    )
                    sys_delta = (
                        s["cpu_stats"]["system_cpu_usage"]
                        - s["precpu_stats"]["system_cpu_usage"]
                    )
                    ncpus = s["cpu_stats"].get("online_cpus", 1)
                    cpu_pct = (
                        round((cpu_delta / sys_delta) * ncpus * 100, 2)
                        if sys_delta > 0
                        else 0.0
                    )
                    mem_mb = round(s["memory_stats"]["usage"] / 1024 / 1024, 2)
                    writer.writerow([ts, c.name, cpu_pct, mem_mb])
                except Exception:
                    pass
            f.flush()
            time.sleep(2)


stop = threading.Event()
t = threading.Thread(
    target=collect_stats,
    args=(os.environ["RESULTS_DIR"], stop),
    daemon=True,
)
t.start()

subprocess.run(
    [
        "locust",
        "-f", "/locustfile.py",
        "--headless",
        "-u", "10",
        "-r", "2",
        "--run-time", "60s",
        "--host", os.environ["APP_URL"],
    ]
)

stop.set()
t.join(timeout=5)
