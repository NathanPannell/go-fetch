#!/bin/sh
set -e
SCENARIO="${PERF_SCENARIO:-baseline}"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
RESULTS_DIR="${RESULTS_DIR:-/perf/results}"
PREFIX="${RESULTS_DIR}/${SCENARIO}_${TIMESTAMP}"
mkdir -p "${RESULTS_DIR}"
exec locust \
    -f /perf/locustfile.py \
    --headless \
    --host "${APP_URL}" \
    --csv "${PREFIX}" \
    --html "${PREFIX}.html" \
    --logfile "${PREFIX}.log"
