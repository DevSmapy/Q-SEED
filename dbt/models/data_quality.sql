WITH base AS (
    SELECT
        Date,
        Ticker,
        Market,
        Volume,
        Close
    FROM {{ ref('stg_raw_stocks') }} -- 또는 source() 함수 사용
),

-- 1. 각 티커별로 데이터의 시작일과 종료일을 구하고, 수집된 총 일수를 계산합니다.
ticker_stats AS (
    SELECT
        Ticker,
        Market,
        MIN(Date) AS start_date,
        MAX(Date) AS end_date,
        COUNT(Date) AS actual_days,

        -- 거래량이 0이거나 데이터가 비어있는(Null) 날을 카운트합니다.
        SUM(CASE WHEN Volume = 0 OR Volume IS NULL THEN 1 ELSE 0 END) AS zero_volume_days,
        SUM(CASE WHEN Close IS NULL THEN 1 ELSE 0 END) AS null_price_days
    FROM base
    GROUP BY Ticker, Market
),

-- 2. DuckDB의 강력한 날짜 함수를 사용해, 수집 시작일부터 종료일까지 '실제 주말을 제외한 영업일(평일)'이 몇 일이어야 하는지 계산합니다.
expected_stats AS (
    SELECT
        Ticker,
        Market,
        start_date,
        end_date,
        actual_days,
        zero_volume_days,
        null_price_days,

        -- DuckDB에서 두 날짜 사이의 순수 평일(월-금) 수를 계산하는 로직입니다.
        (DATEDIFF('day', start_date, end_date) + 1)
        - (DATEDIFF('week', start_date, end_date) * 2) AS expected_business_days
    FROM ticker_stats
)

-- 3. 최종적으로 이론적 영업일과 실제 수집된 일수를 비교하여 누락률을 계산합니다.
SELECT
    Ticker,
    Market,
    start_date AS "수집 시작일",
    end_date AS "수집 마감일",
    expected_business_days AS "이론적 영업일수",
    actual_days AS "실제 수집일수",

    -- 누락된 일수와 누락률 계산
    (expected_business_days - actual_days) AS "누락 일수",
    ROUND(
        CASE
            WHEN expected_business_days > 0
            THEN (1.0 - (actual_days::DOUBLE / expected_business_days)) * 100
            ELSE 0
        END, 2
    ) AS "데이터 누락률(%)",

    zero_volume_days AS "거래량 0인 날",
    null_price_days AS "종가 결측일"
FROM expected_stats
ORDER BY "데이터 누락률(%)" DESC  -- 누락이 심한 종목부터 먼저 보도록 정렬
