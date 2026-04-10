# 베이스 이미지로 Python 3.12-slim 사용 (uv와 호환성 고려)
FROM python:3.12-slim

# 필요한 패키지 설치 및 uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 (uv.lock 및 pyproject.toml)
COPY pyproject.toml uv.lock ./

# 의존성 설치 (가상환경 없이 시스템 경로에 설치하도록 설정)
RUN uv sync --frozen --no-dev --no-editable

# 프로젝트 코드 복사
COPY . .

# 결과물을 저장할 폴더 생성
RUN mkdir -p kor_ticker

# Python 실행 경로 설정 (uv가 생성한 가상환경 사용)
ENV PATH="/app/.venv/bin:$PATH"

# 실행 명령 설정
CMD ["python", "research/main.py"]
