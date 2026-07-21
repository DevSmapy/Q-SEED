"""Q-SEED 프로젝트 설정 관리 모듈."""

from functools import cached_property
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StockConfig(BaseSettings):
    """주식 데이터 수집 관련 설정."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="QSEED_STOCK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 수집 설정
    chunk_size: int = Field(default=100, ge=1, description="한 번에 처리할 종목 수")
    max_stocks: int = Field(default=1000, ge=1, description="시장별 최대 수집 종목 수")
    download_period: str = Field(default="max", description="yfinance 다운로드 기간")
    yfinance_threads: bool = Field(
        default=False,
        description="yfinance 멀티스레드 다운로드 (대량 청크 시 FD 누수 위험)",
    )
    sleep_interval: float = Field(default=5.0, ge=0, description="청크 간 대기 시간 (초)")
    gap_tolerance_days: int = Field(
        default=5,
        ge=0,
        description="시장별 최신일 대비 공백으로 간주할 최소 지연 일수",
    )
    auto_repair_gaps: bool = Field(
        default=True,
        description="증분 업데이트 후 공백 티커 자동 재수집 여부",
    )

    # 경로 설정 (로컬 절대경로는 .env의 QSEED_STOCK_BASE_DIR로 지정)
    base_dir: Path = Field(default=Path("./data"), description="기본 데이터 디렉토리")

    @property
    def log_dir(self) -> Path:
        """로그 데이터 디렉토리."""
        return self.base_dir / "data_log"

    @property
    def db_path(self) -> Path:
        """DuckDB 파일 경로."""
        return self.base_dir / "stocks.db"

    # 파일명 설정
    ticker_list_filename: str = Field(default="krx_list.csv", description="티커 목록 파일명")
    no_data_filename: str = Field(
        default="no_data_list.txt", description="데이터 없는 종목 목록 파일명"
    )
    completed_data_filename: str = Field(
        default="completed_data_list.txt", description="수집 완료된 종목 목록 파일명"
    )
    last_date_filename: str = Field(
        default="last_date.txt", description="마지막 수집 날짜 기록 파일명"
    )

    @cached_property
    def ticker_list_path(self) -> Path:
        """티커 목록 파일 전체 경로."""
        return self.log_dir / self.ticker_list_filename

    @cached_property
    def no_data_path(self) -> Path:
        """데이터 없는 종목 목록 파일 전체 경로."""
        return self.log_dir / self.no_data_filename

    @cached_property
    def completed_data_path(self) -> Path:
        """수집 완료된 종목 목록 파일 전체 경로."""
        return self.log_dir / self.completed_data_filename

    @cached_property
    def last_date_path(self) -> Path:
        """마지막 수집 날짜 파일 전체 경로."""
        return self.log_dir / self.last_date_filename

    def ensure_directories(self) -> None:
        """필요한 디렉토리 생성."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


class FactorConfig(BaseSettings):
    """팩터 분석 관련 설정."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="QSEED_FACTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    forward_horizon: int = Field(default=21, ge=1, description="선행 수익률 기간(거래일)")
    min_observations: int = Field(default=30, ge=5, description="단면 IC/분위수 최소 종목 수")
    default_factor: str = Field(default="momentum_12_1", description="기본 분석 팩터")


class BacktestConfig(BaseSettings):
    """백테스트 관련 설정."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="QSEED_BACKTEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rebalance_freq: int = Field(default=21, ge=1, description="리밸런싱 주기(거래일)")
    min_observations: int = Field(default=30, ge=5, description="리밸런싱 최소 종목 수")
    transaction_cost_bps: float = Field(default=0.0, ge=0, description="거래비용 (bps)")
    initial_capital: float = Field(default=100_000_000.0, gt=0, description="초기 자본")
    default_factor: str = Field(default="reversal_5d", description="기본 백테스트 팩터")
    position_mode: str = Field(default="long_short", description="long_short 또는 long_only")
    output_dir: Path | None = Field(
        default=None,
        description="결과 출력 경로 (미지정 시 {data_dir}/backtest/case_study_kr)",
    )
    export_format: str = Field(
        default="parquet",
        description="결과 파일 형식 (parquet, csv, both)",
    )


class OptimizeConfig(BaseSettings):
    """포트폴리오 최적화 관련 설정."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="QSEED_OPTIMIZE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    weight_method: str = Field(
        default="min_volatility",
        description="equal_weight | min_volatility | max_sharpe | hrp",
    )
    lookback: int = Field(default=252, ge=20, description="최적화 lookback 거래일")
    max_assets: int = Field(
        default=50,
        ge=2,
        description="슬리브당 최적화 최대 종목 수 (관측치 많은 순)",
    )
    default_factor: str = Field(default="reversal_5d", description="기본 최적화 팩터")
    position_mode: str = Field(default="long_short", description="long_short 또는 long_only")


class SecurityMetadataConfig(BaseSettings):
    """종목 섹터·업종 메타데이터 수집 설정."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="QSEED_SECURITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sleep_seconds: float = Field(
        default=0.3,
        ge=0,
        description="티커 간 yfinance info 대기(초)",
    )
    max_tickers: int | None = Field(
        default=None,
        ge=1,
        description="메타데이터 수집 최대 종목 수 (로컬 dev)",
    )
    equity_only: bool = Field(
        default=False,
        description="EQUITY quote_type만 저장 (비-EQUITY는 API 호출 후 skip)",
    )


class GCSConfig(BaseSettings):
    """Google Cloud Storage 설정."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="QSEED_GCS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bucket_name: str | None = Field(default=None, description="GCS 버킷 이름")
    ticker_blob_prefix: str = Field(default="kor_ticker", description="GCS blob 접두사")

    @cached_property
    def is_enabled(self) -> bool:
        """GCS 업로드 활성화 여부."""
        return self.bucket_name is not None


class AppConfig(BaseSettings):
    """애플리케이션 전체 설정."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    stock: StockConfig = Field(default_factory=StockConfig)
    factor: FactorConfig = Field(default_factory=FactorConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    optimize: OptimizeConfig = Field(default_factory=OptimizeConfig)
    security: SecurityMetadataConfig = Field(default_factory=SecurityMetadataConfig)
    gcs: GCSConfig = Field(default_factory=GCSConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """환경 변수에서 설정 로드."""
        return cls()

    def model_post_init(self, __context: Any) -> None:
        """초기화 후 처리."""
        pass


def get_config() -> AppConfig:
    """설정 인스턴스 생성 (환경 변수 자동 로드)."""
    return AppConfig()
