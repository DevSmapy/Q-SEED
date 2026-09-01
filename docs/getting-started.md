# 시작하기

저장소를 클론한 뒤 **작업 명령**으로 환경을 점검하고, 샘플 데이터로 연구 루프를 한 바퀴 돕니다.

```bash
make setup
uv run qseed doctor
uv run qseed demo          # 또는: uv run qseed quickstart
```

실제 시세·증분·cron은 [data-pipeline.md](data-pipeline.md)를 참고하세요.

## 사전 요구사항

| 방식      | 필요 도구                                                         |
| --------- | ----------------------------------------------------------------- |
| 로컬 (uv) | [uv](https://docs.astral.sh/uv/getting-started/installation/)     |
| Docker    | [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2 |

Python 버전은 **3.12**를 권장합니다 (`.python-version` 참고).

공식 CLI 표기는 `uv run qseed`입니다. 명령 목록은 `uv run qseed --help`입니다.

## 1. 설치와 점검

클론·의존성 설치는 네트워크가 필요합니다.

```bash
git clone https://github.com/DevSmapy/Q-SEED.git
cd Q-SEED
make setup
uv run qseed doctor
```

`doctor`는 Python·패키지·`profiles.yml`·`.env`·`data/stocks.db`를 보고, 빠지면 **다음 명령**을 알려 줍니다.

설치만 확인 (시세 API 불필요):

```bash
uv run qseed --help
make test
```

## 2. 샘플 데이터로 한 바퀴 (`qseed demo`)

**샘플 DuckDB는 git에 없습니다.** `demo`가 합성 warehouse를 만들고 `reversal_5d` IC·백테스트까지 돌립니다. 외부 시세 API는 쓰지 않습니다.

```bash
uv run qseed demo
# 한 줄로 점검+데모:
uv run qseed quickstart
```

| 명령               | 하는 일                      |
| ------------------ | ---------------------------- |
| `qseed doctor`     | 환경 점검, 다음 명령 안내    |
| `qseed demo`       | 샘플 DB + 팩터 IC + 백테스트 |
| `qseed quickstart` | doctor 다음 demo             |
| `qseed factors`    | 등록 팩터 목록               |

기존 `stocks.db`를 덮어쓰려면 `qseed demo --force`입니다.

성공하면 `data/stocks.db`, `data/factor_analysis/reversal_5d/`, `data/backtest/case_study_kr/`가 생깁니다.

CI용 합성 DB(`make dbt-ci` → `data/ci_stocks.db`)는 dbt 검증 전용이며 demo warehouse와 다릅니다.

## 3. 실제 시세 (`qseed collect`)

네트워크가 필요합니다. 기본값은 IC가 돌아가도록 KOSPI 80종목 · 1년입니다 (20종목이면 단면 IC가 비거나 NaN).

```bash
uv run qseed collect
uv run dbt run --select stocks
uv run qseed analyze
uv run qseed backtest
```

| 명령                       | 의미                         |
| -------------------------- | ---------------------------- |
| `qseed collect`            | KOSPI 80종목 · 1y            |
| `qseed collect --full`     | 전 시장 · 기간 max           |
| `qseed collect --update`   | 증분 업데이트                |
| `qseed analyze --factor …` | 팩터 IC (기본 `reversal_5d`) |
| `qseed backtest`           | 백테스트                     |
| `qseed optimize`           | 가중치 최적화                |

`momentum_12_1`은 종목당 약 252거래일이 필요합니다. 1년 샘플/수집이면 `qseed analyze --factor reversal_5d`를 쓰세요. 오류 메시지에 다음 명령이 나옵니다.

기존 `--build-db` 플래그는 그대로 동작합니다. 목록은 `qseed --help-flags`.

## 4. 결과 보기 (선택)

```bash
make dashboard   # Streamlit :8501
make web         # 로컬 조회 서버 :8000
```

## Docker

컨테이너 셸에서 같은 명령을 씁니다.

```bash
make docker-up
make docker-shell
uv run qseed doctor
uv run qseed demo
```

| 서비스               | 컨테이너 포트 | 호스트 |
| -------------------- | ------------- | ------ |
| 로컬 웹 (`make web`) | 8000          | 8000   |
| Streamlit dashboard  | 8501          | 8501   |

중지: `make docker-down`.

## 설정 파일

| 파일                   | 설명                                           |
| ---------------------- | ---------------------------------------------- |
| `profiles.yml.example` | dbt DuckDB 연결 템플릿 → `profiles.yml`로 복사 |
| `.env.example`         | 환경 변수 템플릿 → `.env`로 복사               |

`make setup`이 예시 파일을 복사합니다. 머신별 절대경로는 `.env`의 `QSEED_STOCK_BASE_DIR`에만 둡니다.

## 다음 단계

- [데이터 파이프라인](data-pipeline.md) — 전체 적재·증분·dbt·대시보드
- [팩터 분석](factor-analysis.md) — 내장 팩터·IC
- [백테스팅](backtesting.md) — 롱숏/롱온리
- [CLI 레퍼런스](cli-reference.md) — 플래그·환경 변수
- [아키텍처](architecture.md) — 디렉토리·저장 구조
