SELECT
    count(distinct Ticker) as Ticker_counts, Market
FROM {{ ref('stg_raw_stocks') }} GROUP BY Market
