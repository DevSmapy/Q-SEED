.PHONY: help setup sync profiles env pre-commit test dbt dashboard web docker-build docker-up docker-down docker-shell docker-logs

help:
	@echo "Q-SEED 개발 환경"
	@echo ""
	@echo "  make setup        로컬 환경 초기화 (uv sync + 설정 파일 + pre-commit)"
	@echo "  make sync         uv 의존성 설치"
	@echo "  make test         단위 테스트 (pytest)"
	@echo "  make dbt          stocks dbt 모델 실행"
	@echo "  make dashboard    Streamlit stocks 리뷰 대시보드"
	@echo "  make web          로컬 DuckDB 조회 웹 서버"
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

dashboard:
	PYTHONPATH=src uv run streamlit run src/qseed/dashboard/app.py

web:
	PYTHONPATH=src uv run python -m qseed.web.server --db data/stocks.db

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
