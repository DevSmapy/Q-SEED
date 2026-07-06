WITH ordered AS (
    SELECT
        Date,
        Ticker,
        Market,
        Close,
        LAG(Close, 1) OVER (
            PARTITION BY Ticker
            ORDER BY Date
        ) AS prev_close,
        LEAD(Close, 21) OVER (
            PARTITION BY Ticker
            ORDER BY Date
        ) AS forward_close_21d
    FROM {{ ref('stg_raw_stocks') }}
    WHERE Close IS NOT NULL
)

SELECT
    Date,
    Ticker,
    Market,
    Close,
    CASE
        WHEN prev_close IS NULL OR prev_close = 0 THEN NULL
        ELSE (Close / prev_close) - 1
    END AS daily_return,
    CASE
        WHEN forward_close_21d IS NULL OR Close = 0 THEN NULL
        ELSE (forward_close_21d / Close) - 1
    END AS forward_return_21d
FROM ordered
