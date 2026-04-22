"""Parquet 저장소 모듈."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class ParquetRepository:
    """DataFrame을 Parquet 파일로 저장하는 저장소."""

    def __init__(self, base_dir: Path | str) -> None:
        """ParquetRepository 초기화.

        Args:
            base_dir: Parquet 파일을 저장할 기본 디렉토리
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, dataframe: pd.DataFrame, filename: str) -> Path:
        """DataFrame을 Parquet 파일로 저장.

        Args:
            dataframe: 저장할 DataFrame
            filename: 저장할 파일명

        Returns:
            저장된 Parquet 파일 경로
        """
        file_path = self.base_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        dataframe.to_parquet(file_path, engine="pyarrow", index=False)
        return file_path

    def save_with_prefix(self, dataframe: pd.DataFrame, prefix: str, index: int) -> Path:
        """접두사와 순번을 사용해 Parquet 파일 저장.

        Args:
            dataframe: 저장할 DataFrame
            prefix: 파일명 접두사
            index: 순번

        Returns:
            저장된 Parquet 파일 경로
        """
        filename = f"{prefix}_{index:04d}.parquet"
        return self.save(dataframe, filename=filename)

    def list_files(self) -> list[Path]:
        """저장된 Parquet 파일 목록 조회."""
        return sorted(self.base_dir.glob("*.parquet"))
