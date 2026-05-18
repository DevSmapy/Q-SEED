SELECT
    Ticker,
    Date,
    COUNT(*) AS duplicate_count
FROM {{ source('raw', 'raw_stocks') }}
GROUP BY Ticker, Date
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, Ticker, Date
