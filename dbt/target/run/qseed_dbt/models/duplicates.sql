




    create  table
      "stocks"."main"."duplicates__dbt_tmp"

    as (
      SELECT
    Ticker,
    Date,
    COUNT(*) AS duplicate_count
FROM "stocks"."main"."raw_stocks"
GROUP BY Ticker, Date
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, Ticker, Date
    );
