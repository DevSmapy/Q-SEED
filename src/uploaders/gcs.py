"""Google Cloud Storage 업로더 모듈."""

from __future__ import annotations

from pathlib import Path

from google.cloud import storage


class GCSUploader:
    """GCS에 파일을 업로드하는 업로더."""

    def __init__(self, bucket_name: str | None, blob_prefix: str = "") -> None:
        """GCSUploader 초기화.

        Args:
            bucket_name: GCS 버킷 이름. None이면 업로드 비활성화
            blob_prefix: 업로드할 blob 경로 접두사
        """
        self.bucket_name = bucket_name
        self.blob_prefix = blob_prefix.strip("/")

    @property
    def is_enabled(self) -> bool:
        """업로드 활성화 여부."""
        return self.bucket_name is not None

    def upload_file(self, source_file: Path | str, destination_blob_name: str) -> None:
        """로컬 파일을 GCS에 업로드.

        Args:
            source_file: 업로드할 로컬 파일 경로
            destination_blob_name: GCS에 저장될 blob 이름

        Raises:
            ValueError: bucket_name이 설정되지 않은 경우
        """
        if self.bucket_name is None:
            raise ValueError("GCS bucket_name이 설정되지 않았습니다.")

        source_path = Path(source_file)

        storage_client = storage.Client()
        bucket = storage_client.bucket(self.bucket_name)
        blob_name = self._build_blob_name(destination_blob_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(source_path))

    def upload_parquet(self, source_file: Path | str) -> None:
        """Parquet 파일을 blob_prefix 아래로 업로드."""
        source_path = Path(source_file)
        self.upload_file(
            source_file=source_path,
            destination_blob_name=source_path.name,
        )

    def _build_blob_name(self, destination_blob_name: str) -> str:
        """blob 접두사를 포함한 최종 blob 이름 생성."""
        destination_blob_name = destination_blob_name.lstrip("/")

        if not self.blob_prefix:
            return destination_blob_name

        return f"{self.blob_prefix}/{destination_blob_name}"
