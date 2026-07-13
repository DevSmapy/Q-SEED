.PHONY: help setup sync profiles env pre-commit docker-build docker-up docker-down docker-shell docker-logs

help:
	@echo "Q-SEED 개발 환경"
	@echo ""
	@echo "  make setup        로컬 환경 초기화 (uv sync + 설정 파일 + pre-commit)"
	@echo "  make sync         uv 의존성 설치"
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
