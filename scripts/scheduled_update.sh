#!/usr/bin/env bash
# Session-scoped incremental stock update for cron.
# Usage: ./scripts/scheduled_update.sh kr|us
set -euo pipefail

SESSION="${1:-}"
if [[ "$SESSION" != "kr" && "$SESSION" != "us" ]]; then
  echo "usage: $0 kr|us" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DATA_DIR="${DATA_DIR:-./data}"
LOCK_DIR="${DATA_DIR}/.scheduled_update.lock"
LOG_DIR="${DATA_DIR}/data_log"
mkdir -p "$LOG_DIR" "$DATA_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "skip: another scheduled_update holds ${LOCK_DIR}" >&2
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

LOG_FILE="${LOG_DIR}/scheduled_update_${SESSION}_$(date +%Y%m%d).log"
exec >>"$LOG_FILE" 2>&1

ts() { date '+%Y-%m-%dT%H:%M:%S%z'; }

echo "==> $(ts) session=${SESSION} data_dir=${DATA_DIR}"

if [[ "$SESSION" == "kr" ]]; then
  uv run qseed --update-db --data-dir "$DATA_DIR" \
    --market KOSPI --market KOSDAQ --market KONEX
else
  uv run qseed --update-db --data-dir "$DATA_DIR" \
    --market NASDAQ --market NYSE --market AMEX --market "S&P500"
fi

echo "==> $(ts) done session=${SESSION}"
