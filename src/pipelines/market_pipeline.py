"""시장 지표 수집·파생 파이프라인."""

from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import ContextManager

from src.fetchers.market_series import fetch_all_series
from src.pipelines.breadth import compute_market_breadth
from src.qseed.config import AppConfig, get_config
from src.repositories.market_repository import MarketRepository

logger = logging.getLogger("qseed")


@dataclass(slots=True)
class MarketPipelineOptions:
    """시장 지표 파이프라인 옵션."""

    breadth_only: bool = False
    markets: list[str] | None = None


class MarketDataPipeline:
    """외부 시계열 적재 + raw_stocks breadth 파생."""

    def __init__(
        self,
        config: AppConfig | None = None,
        repository: MarketRepository | None = None,
    ) -> None:
        self.config = config or get_config()
        self._repository = repository

    @property
    def db_path(self) -> Path:
        return self.config.stock.db_path

    def run(self, options: MarketPipelineOptions | None = None) -> None:
        """파이프라인 실행."""
        opts = options or MarketPipelineOptions()
        self.config.stock.ensure_directories()

        repo_cm: ContextManager[MarketRepository]
        if self._repository is None:
            repo_cm = MarketRepository(self.db_path)
        else:
            repo_cm = nullcontext(self._repository)

        with repo_cm as repo:
            repo.initialize()

            if not opts.breadth_only:
                self._ingest_series(repo)

            self._ingest_breadth(repo, markets=opts.markets)

    def _ingest_series(self, repo: MarketRepository) -> None:
        logger.info("시장 시계열 수집 시작")
        series = fetch_all_series()
        if series.empty:
            logger.warning("수집된 시장 시계열이 없습니다")
            return
        repo.insert_series(series)
        repo.deduplicate_series()
        logger.info("시장 시계열 적재 완료: %d rows", len(series))

    def _ingest_breadth(
        self,
        repo: MarketRepository,
        *,
        markets: list[str] | None,
    ) -> None:
        logger.info("breadth 계산 시작")
        prices = repo.load_stock_closes(markets)
        if prices.empty:
            logger.warning("raw_stocks가 비어 있어 breadth를 건너뜁니다")
            return

        breadth = compute_market_breadth(prices)
        if breadth.empty:
            logger.warning("breadth 결과가 비어 있습니다")
            return

        target_markets = sorted(breadth["Market"].astype(str).unique().tolist())
        repo.replace_breadth_for_markets(target_markets, breadth)
        logger.info(
            "breadth 적재 완료: %d rows (%d markets)",
            len(breadth),
            len(target_markets),
        )
