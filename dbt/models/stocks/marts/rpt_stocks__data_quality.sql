with base as (
    select
        Date,
        Ticker,
        Market,
        Volume,
        Close,
        Open,
        High,
        Low
    from {{ ref('stg_stocks__raw_stocks') }}
),

ticker_stats as (
    select
        Ticker,
        Market,
        min(Date) as start_date,
        max(Date) as end_date,
        count(Date) as actual_days,
        sum(case when Volume = 0 or Volume is null then 1 else 0 end) as zero_volume_days,
        sum(case when Close is null then 1 else 0 end) as null_price_days,
        sum(
            case
                when High is not null and Low is not null and High < Low then 1
                else 0
            end
        ) as high_lt_low_days,
        sum(
            case
                when
                    Close is not null
                    and High is not null
                    and Low is not null
                    and (Close > High or Close < Low)
                then 1
                else 0
            end
        ) as close_outside_hl_days
    from base
    group by Ticker, Market
),

expected_stats as (
    select
        Ticker,
        Market,
        start_date,
        end_date,
        actual_days,
        zero_volume_days,
        null_price_days,
        high_lt_low_days,
        close_outside_hl_days,
        -- Weekday-only expected days (ignores exchange holidays → may overstate gaps)
        (datediff('day', start_date, end_date) + 1)
        - (datediff('week', start_date, end_date) * 2) as expected_business_days
    from ticker_stats
)

select
    e.Ticker,
    e.Market,
    d.country,
    e.start_date,
    e.end_date,
    e.expected_business_days,
    e.actual_days,
    (e.expected_business_days - e.actual_days) as missing_days,
    round(
        case
            when e.expected_business_days > 0
            then (1.0 - (e.actual_days::double / e.expected_business_days)) * 100
            else 0
        end,
        2
    ) as missing_rate_pct,
    e.zero_volume_days,
    e.null_price_days,
    e.high_lt_low_days,
    e.close_outside_hl_days
from expected_stats as e
left join {{ ref('dim_stocks__market') }} as d
    on e.Market = d.Market
order by missing_rate_pct desc
