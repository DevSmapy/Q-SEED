WITH base AS (
    SELECT * FROM {{ source('raw', 'raw_stocks') }}
),

column_stats AS (
    SELECT
        'Open' AS column_name,
        COUNT(*) AS total_rows,
        COUNT(CASE WHEN Open IS NULL THEN 1 END) AS null_count,
        COUNT(CASE WHEN Open = 0 THEN 1 END) AS zero_count,
        MIN(Open) AS min_val,
        MAX(Open) AS max_val,
        QUANTILE_CONT(Open, 0.25) AS q1,
        QUANTILE_CONT(Open, 0.5) AS median,
        QUANTILE_CONT(Open, 0.75) AS q3
    FROM base
    UNION ALL
    SELECT
        'Close' AS column_name,
        COUNT(*) AS total_rows,
        COUNT(CASE WHEN Close IS NULL THEN 1 END) AS null_count,
        COUNT(CASE WHEN Close = 0 THEN 1 END) AS zero_count,
        MIN(Close) AS min_val,
        MAX(Close) AS max_val,
        QUANTILE_CONT(Close, 0.25) AS q1,
        QUANTILE_CONT(Close, 0.5) AS median,
        QUANTILE_CONT(Close, 0.75) AS q3
    FROM base
    -- 필요한 다른 수치형 컬럼들(High, Low, Volume 등) 추가 가능
),

final AS (
    SELECT
        *,
        (null_count::FLOAT / total_rows) * 100 AS null_rate,
        (zero_count::FLOAT / total_rows) * 100 AS zero_rate,
        (q3 - q1) AS iqr,
        (q1 - 1.5 * (q3 - q1)) AS lower_bound,
        (q3 + 1.5 * (q3 - q1)) AS upper_bound
    FROM column_stats
)

SELECT * FROM final
