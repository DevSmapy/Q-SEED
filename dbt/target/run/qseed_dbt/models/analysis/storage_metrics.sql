




    create  table
      "stocks"."main"."storage_metrics__dbt_tmp"

    as (
      -- DuckDB의 메타데이터를 사용하여 테이블별 저장 용량 확인
-- 주의: DuckDB 버전에 따라 메타데이터 테이블명이 다를 수 있음
SELECT
    table_name,
    estimated_size AS estimated_row_count,
    -- DuckDB는 컬럼 지향이라 정확한 바이트 크기를 구하기 위해 정밀 쿼리가 필요할 수 있으나
    -- 통상적으로 데이터 파일 전체 크기를 기준으로 비교하는 방식을 권장
FROM duckdb_tables()
WHERE schema_name = 'main'
    );
