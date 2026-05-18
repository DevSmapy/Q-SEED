SELECT
    COUNT(*) AS total_row_count,
    COUNT(DISTINCT Ticker) AS total_ticker_count,
    MIN(Date) AS min_date,
    MAX(Date) AS max_date
FROM {{ source('raw', 'raw_stocks') }}
