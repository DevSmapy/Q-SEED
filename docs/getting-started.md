# 시작하기

저장소를 클론한 뒤 **uv**(로컬) 또는 **Docker**(컨테이너) 중 하나로 환경을 구성할 수 있습니다.

## 사전 요구사항

| 방식      | 필요 도구                                                         |
| --------- | ----------------------------------------------------------------- |
| 로컬 (uv) | [uv](https://docs.astral.sh/uv/getting-started/installation/)     |
| Docker    | [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2 |

Python 버전은 **3.12**를 권장합니다 (`.python-version` 참고).

## 빠른 시작 (uv)

```bash
git clone <repository-url>
cd Q-SEED

# 한 번에 초기화: 의존성 설치, profiles.yml/.env 생성, pre-commit 훅 설치
make setup

# 또는 수동으로
uv sync
cp profiles.yml.example profiles.yml
cp .env.example .env
uv run pre-commit install
```

설치 후 CLI 확인:

```bash
uv run qseed --help
```

## 빠른 시작 (Docker)

```bash
git clone <repository-url>
cd Q-SEED

# 로컬 설정 파일 준비 (dbt·환경 변수용)
cp profiles.yml.example profiles.yml
cp .env.example .env

# 컨테이너 빌드 및 시작
make docker-up

# 컨테이너 셸 접속
make docker-shell
```

컨테이너 내부에서도 동일하게 `uv run`으로 명령을 실행합니다.

```bash
uv run qseed --help
uv run dbt run
```

컨테이너를 중지하려면 `make docker-down`을 실행합니다.

## 설정 파일

| 파일                   | 설명                                           |
| ---------------------- | ---------------------------------------------- |
| `profiles.yml.example` | dbt DuckDB 연결 템플릿 → `profiles.yml`로 복사 |
| `.env.example`         | 환경 변수 템플릿 → `.env`로 복사               |

`profiles.yml`과 `.env`는 git에 포함되지 않습니다. 클론 후 예시 파일을 복사해 사용하세요.

## 다음 단계

- [아키텍처](architecture.md) — 디렉토리·저장 구조
- [데이터 파이프라인](data-pipeline.md) — 수집·dbt·대시보드
- [CLI 레퍼런스](cli-reference.md) — 전체 CLI 옵션·환경 변수
