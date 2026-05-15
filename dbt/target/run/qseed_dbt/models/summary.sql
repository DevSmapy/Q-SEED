




    create  table
      "stocks"."main"."summary__dbt_tmp"

    as (
      SELECT
    COUNT(*) AS total_row_count,
    COUNT(DISTINCT Ticker) AS total_ticker_count,
    MIN(Date) AS min_date,
    MAX(Date) AS max_date
FROM "stocks"."main"."raw_stocks"
    );
