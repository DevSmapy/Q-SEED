WITH ordered AS (
    SELECT
        Date,
        Ticker,
        Market,
        Close,
        Volume,
        LAG(Close, 21) OVER w AS close_lag_21,
        LAG(Close, 126) OVER w AS close_lag_126,
        LAG(Close, 252) OVER w AS close_lag_252,
        LAG(Close, 5) OVER w AS close_lag_5,
        AVG(CAST(Volume AS DOUBLE)) OVER (
            PARTITION BY Ticker
            ORDER BY Date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) AS volume_avg_20d
    FROM {{ ref('stg_raw_stocks') }}
    WHERE Close IS NOT NULL
    WINDOW w AS (PARTITION BY Ticker ORDER BY Date)
),

with_returns AS (
    SELECT
        *,
        CASE
            WHEN LAG(Close, 1) OVER w IS NULL OR LAG(Close, 1) OVER w = 0 THEN NULL
            ELSE (Close / LAG(Close, 1) OVER w) - 1
        END AS daily_return
    FROM ordered
    WINDOW w AS (PARTITION BY Ticker ORDER BY Date)
)

SELECT
    Date,
    Ticker,
    Market,
    CASE
        WHEN close_lag_252 IS NULL OR close_lag_252 = 0 THEN NULL
        ELSE (close_lag_21 / close_lag_252) - 1
    END AS momentum_12_1,
    CASE
        WHEN close_lag_126 IS NULL OR close_lag_126 = 0 THEN NULL
        ELSE (Close / close_lag_126) - 1
    END AS momentum_6m,
    CASE
        WHEN close_lag_5 IS NULL OR close_lag_5 = 0 THEN NULL
        ELSE -((Close / close_lag_5) - 1)
    END AS reversal_5d,
    STDDEV_SAMP(daily_return) OVER (
        PARTITION BY Ticker
        ORDER BY Date
        ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
    ) AS volatility_60d,
    CASE
        WHEN volume_avg_20d IS NULL OR volume_avg_20d = 0 THEN NULL
        ELSE CAST(Volume AS DOUBLE) / volume_avg_20d
    END AS volume_ratio_20d,
    LN(1 + Close * CAST(Volume AS DOUBLE)) AS log_dollar_volume
FROM with_returns
