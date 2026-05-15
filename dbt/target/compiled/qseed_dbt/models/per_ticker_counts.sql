SELECT
    Ticker,
    COUNT(*) AS row_count,
    MIN(Date) AS min_date,
    MAX(Date) AS max_date
FROM "stocks"."main"."raw_stocks"
GROUP BY Ticker
ORDER BY row_count DESC, Ticker
