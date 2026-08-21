.PHONY: help setup sync profiles env pre-commit test dbt dbt-ci ci-seed dashboard web scheduled-update docker-build docker-up docker-down docker-shell docker-logs

help:
	@echo "Q-SEED 개발 환경"
	@echo ""
	@echo "  make setup        로컬 환경 초기화 (uv sync + 설정 파일 + pre-commit)"
	@echo "  make sync         uv 의존성 설치"
	@echo "  make test         단위 테스트 (pytest)"
	@echo "  make dbt          stocks dbt 모델 실행"
	@echo "  make ci-seed      CI용 합성 DuckDB 생성 (네트워크 없음)"
	@echo "  make dbt-ci       합성 DB로 dbt build (CI와 동일)"
	@echo "  make dashboard    Streamlit stocks 리뷰 대시보드"
	@echo "  make web          로컬 DuckDB 조회 웹 서버"
	@echo "  make scheduled-update SESSION=kr|us  세션별 증분 업데이트 (cron용)"
	@echo "  make docker-build Docker 이미지 빌드"
	@echo "  make docker-up    Docker 컨테이너 시작"
	@echo "  make docker-shell 컨테이너 셸 접속"
	@echo "  make docker-down  Docker 컨테이너 중지"

setup: sync profiles env pre-commit
	@echo "로컬 환경 설정이 완료되었습니다."

sync:
	uv sync

profiles:
	@test -f profiles.yml || cp profiles.yml.example profiles.yml

env:
	@test -f .env || cp .env.example .env

pre-commit:
	uv run pre-commit install

test:
	uv run pytest

dbt:
	uv run dbt run --select stocks

ci-seed:
	uv run python scripts/ci_seed_duckdb.py --db data/ci_stocks.db

dbt-ci: ci-seed
	@mkdir -p .dbt-ci
	@cp profiles.yml.example .dbt-ci/profiles.yml
	DBT_PROFILES_DIR=.dbt-ci QSEED_DBT_DUCKDB_PATH=data/ci_stocks.db \
		uv run dbt build --select stocks market

dashboard:
	PYTHONPATH=src uv run streamlit run src/qseed/dashboard/app.py

web:
	PYTHONPATH=src uv run python -m qseed.web.server --db data/stocks.db

# SESSION=kr|us (default kr)
SESSION ?= kr
scheduled-update:
	./scripts/scheduled_update.sh "$(SESSION)"

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-shell:
	docker compose exec q-seed bash

docker-logs:
	docker compose logs -f q-seed
