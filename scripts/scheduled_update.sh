#!/usr/bin/env bash
# Session-scoped incremental stock update for cron.
# Usage: ./scripts/scheduled_update.sh kr|us
# Prefer TZ=Asia/Seoul in crontab (see docs/data-pipeline.md).
set -euo pipefail

export TZ="${TZ:-Asia/Seoul}"

SESSION="${1:-}"
if [[ "$SESSION" != "kr" && "$SESSION" != "us" ]]; then
  echo "usage: $0 kr|us" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# DATA_DIR overrides; else QSEED_STOCK_BASE_DIR (project config); else ./data
DATA_DIR="${DATA_DIR:-${QSEED_STOCK_BASE_DIR:-./data}}"
LOCK_DIR="${DATA_DIR}/.scheduled_update.lock"
LOCK_OWNER_FILE="${LOCK_DIR}/owner"
LOG_DIR="${DATA_DIR}/data_log"
mkdir -p "$LOG_DIR" "$DATA_DIR"

LOG_FILE="${LOG_DIR}/scheduled_update_${SESSION}_$(date +%Y%m%d).log"
exec >>"$LOG_FILE" 2>&1

ts() { date '+%Y-%m-%dT%H:%M:%S%z'; }

OWNER_TOKEN="$$:${SESSION}:$(date +%s)"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "$(ts) skip: another scheduled_update holds ${LOCK_DIR}"
  exit 75
fi
printf '%s\n' "$OWNER_TOKEN" >"$LOCK_OWNER_FILE"

cleanup_lock() {
  if [[ -f "$LOCK_OWNER_FILE" ]] && [[ "$(cat "$LOCK_OWNER_FILE" 2>/dev/null || true)" == "$OWNER_TOKEN" ]]; then
    rm -f "$LOCK_OWNER_FILE"
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
}
trap cleanup_lock EXIT

if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  UV_BIN="${HOME}/.local/bin/uv"
elif [[ -x "${HOME}/.cargo/bin/uv" ]]; then
  UV_BIN="${HOME}/.cargo/bin/uv"
else
  echo "$(ts) uv not found (PATH=${PATH})"
  exit 127
fi

echo "==> $(ts) session=${SESSION} data_dir=${DATA_DIR} uv=${UV_BIN} TZ=${TZ}"

if [[ "$SESSION" == "kr" ]]; then
  "$UV_BIN" run qseed --update-db --data-dir "$DATA_DIR" \
    --market KOSPI --market KOSDAQ --market KONEX
else
  "$UV_BIN" run qseed --update-db --data-dir "$DATA_DIR" \
    --market NASDAQ --market NYSE --market AMEX --market "S&P500"
fi

echo "==> $(ts) done session=${SESSION}"
