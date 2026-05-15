SELECT
    COUNT(*) AS total_rows,
    COUNT(CASE WHEN Date IS NULL THEN 1 END) AS null_date_rows,
    COUNT(CASE WHEN Ticker IS NULL OR Ticker = '' THEN 1 END) AS null_ticker_rows
FROM {{ source('raw', 'raw_stocks') }}
