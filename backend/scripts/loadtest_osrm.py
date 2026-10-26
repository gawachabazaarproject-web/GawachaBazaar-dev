"""Closed-loop load test for an OSRM endpoint (dev/ops tool, not part of the app).

    python scripts/loadtest_osrm.py http://127.0.0.1:15000 --container gb-itest-osrm

For each concurrency level, N worker threads fire /route/v1/driving requests
between RANDOM points inside the Nagpur bounding box (so nothing is cached) for
--seconds seconds. Reports throughput, latency percentiles, HTTP/parse errors
and, if --container is given, peak CPU% / RSS sampled with `docker stats`.
Numbers describe THIS host and THIS dataset only.
"""

import argparse
import json
import random
import statistics
import subprocess
import threading
import time

import httpx

# Nagpur urban area (approx.), lat/lng
LAT = (21.05, 21.25)
LNG = (78.98, 79.22)


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def sample_docker(name, stop, out):
    while not stop.is_set():
        try:
            line = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}", name],
                capture_output=True, text=True, timeout=15,
            ).stdout.strip()
            cpu, mem = line.split("|")
            out.append((float(cpu.rstrip("%")), mem.split("/")[0].strip()))
        except Exception:  # noqa: BLE001
            pass


def run_level(base, concurrency, seconds, container):
    lat, errors, bad = [], [], []
    lock = threading.Lock()
    stop = threading.Event()
    stats_stop = threading.Event()
    docker_samples = []
    sampler = None
    if container:
        sampler = threading.Thread(target=sample_docker, args=(container, stats_stop, docker_samples), daemon=True)
        sampler.start()
    deadline = time.monotonic() + seconds

    def worker():
        rng = random.Random()
        with httpx.Client(timeout=10, limits=httpx.Limits(max_connections=2)) as client:
            while time.monotonic() < deadline and not stop.is_set():
                a = (rng.uniform(*LAT), rng.uniform(*LNG))
                b = (rng.uniform(*LAT), rng.uniform(*LNG))
                url = f"{base}/route/v1/driving/{a[1]:.5f},{a[0]:.5f};{b[1]:.5f},{b[0]:.5f}"
                t = time.perf_counter()
                try:
                    r = client.get(url, params={"overview": "false"})
                    ms = (time.perf_counter() - t) * 1000
                    ok = r.status_code == 200 and r.json().get("code") == "Ok"
                    with lock:
                        lat.append(ms)
                        if not ok:
                            bad.append(r.status_code)
                except Exception as exc:  # noqa: BLE001
                    with lock:
                        errors.append(type(exc).__name__)

    started = time.monotonic()
    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - started
    stats_stop.set()
    if sampler:
        sampler.join(timeout=20)
    res = {
        "concurrency": concurrency,
        "requests": len(lat),
        "rps": round(len(lat) / elapsed, 1),
        "p50_ms": round(statistics.median(lat), 1) if lat else None,
        "p95_ms": round(pct(lat, 0.95), 1) if lat else None,
        "p99_ms": round(pct(lat, 0.99), 1) if lat else None,
        "max_ms": round(max(lat), 1) if lat else None,
        "http_non_ok": len(bad),
        "client_errors": len(errors),
    }
    if docker_samples:
        res["peak_cpu_pct"] = max(c for c, _ in docker_samples)
        res["mem_last"] = docker_samples[-1][1]
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--container")
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--levels", default="10,50,100")
    args = ap.parse_args()
    out = [run_level(args.base.rstrip("/"), int(n), args.seconds, args.container) for n in args.levels.split(",")]
    print(json.dumps(out, indent=1))
