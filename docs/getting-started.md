# 시작하기

저장소를 클론한 뒤 **uv**(로컬) 또는 **Docker**(컨테이너) 중 하나로 환경을 구성할 수 있습니다.

## 사전 요구사항

| 방식      | 필요 도구                                                         |
| --------- | ----------------------------------------------------------------- |
| 로컬 (uv) | [uv](https://docs.astral.sh/uv/getting-started/installation/)     |
| Docker    | [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2 |

Python 버전은 **3.12**를 권장합니다 (`.python-version` 참고).

공식 CLI 표기는 `uv run qseed`입니다 (`python -m src.qseed.cli`와 동등).

## 1. 설치와 설치 확인

클론·의존성 설치(`git clone`, `make setup` / `uv sync`)는 네트워크가 필요합니다.
설치가 끝난 뒤 CLI·단위 테스트만 확인하는 단계는 외부 금융 API나 DuckDB 웨어하우스 없이
진행할 수 있습니다.

```bash
git clone https://github.com/DevSmapy/Q-SEED.git
cd Q-SEED

# 한 번에 초기화: 의존성 설치, profiles.yml/.env 생성, pre-commit 훅 설치
make setup

# 또는 수동으로
uv sync
cp profiles.yml.example profiles.yml
cp .env.example .env
uv run pre-commit install
```

설치 후 확인 (시세 API·DuckDB 불필요):

```bash
uv run qseed --help
make test          # 또는: uv run pytest
```

## 2. 소형 실제 DB 구축 (네트워크 필요)

연구·대시보드·dbt를 쓰려면 외부 시세 API(yfinance / FinanceDataReader)로 작은 warehouse를 만듭니다.
**샘플 DuckDB는 git에 포함하지 않습니다.** CI의 합성 DB(`make dbt-ci`)와는 목적이 다릅니다.

예상: 시장 1개 · 종목 20개 · 기간 `1y` 기준 수분(네트워크·레이트 리밋에 따라 달라짐).

```bash
# KOSPI 소수 종목만 수집 (실제 데이터)
uv run qseed --build-db \
  --market KOSPI \
  --max-stocks 20 \
  --download-period 1y \
  --data-dir ./data

# 같은 DB에 stocks 모델 빌드
uv run dbt run --select stocks
```

선택: CI와 동일한 **합성** DB로 dbt만 검증하려면 (외부 API 없음):

```bash
make dbt-ci
```

`make dbt-ci`는 `data/ci_stocks.db`를 쓰며 실제 `data/stocks.db`를 덮어쓰지 않습니다.

## 빠른 시작 (Docker)

```bash
git clone https://github.com/DevSmapy/Q-SEED.git
cd Q-SEED

cp profiles.yml.example profiles.yml
cp .env.example .env

make docker-up
make docker-shell
```

컨테이너 안에서도 동일하게 `uv run`을 사용합니다.

```bash
uv run qseed --help
uv run pytest
```

호스트에서 포트 매핑:

| 서비스               | 컨테이너 포트 | 호스트 |
| -------------------- | ------------- | ------ |
| 로컬 웹 (`make web`) | 8000          | 8000   |
| Streamlit dashboard  | 8501          | 8501   |

컨테이너를 중지하려면 `make docker-down`을 실행합니다.

## 설정 파일

| 파일                   | 설명                                           |
| ---------------------- | ---------------------------------------------- |
| `profiles.yml.example` | dbt DuckDB 연결 템플릿 → `profiles.yml`로 복사 |
| `.env.example`         | 환경 변수 템플릿 → `.env`로 복사               |

`profiles.yml`과 `.env`는 git에 포함되지 않습니다. 클론 후 예시 파일을 복사해 사용하세요.

dbt 경로: 기본 `data/stocks.db`. CI·합성 검증은 `QSEED_DBT_DUCKDB_PATH=data/ci_stocks.db`.

## 다음 단계

- [아키텍처](architecture.md) — 디렉토리·저장 구조
- [데이터 파이프라인](data-pipeline.md) — 수집·dbt·대시보드
- [CLI 레퍼런스](cli-reference.md) — 전체 CLI 옵션·환경 변수
