with ticker_dates as (
    select
        Ticker,
        Market,
        max(Date) as last_date,
        count(*) as history_days
    from {{ ref('stg_stocks__raw_stocks') }}
    group by 1, 2
),

market_last as (
    select
        Market,
        max(last_date) as market_last_date
    from ticker_dates
    group by 1
),

joined as (
    select
        t.Ticker,
        t.Market,
        t.history_days,
        date_diff('day', t.last_date, m.market_last_date) as gap_days,
        l.adv_20d,
        l.dollar_volume_20d
    from ticker_dates as t
    inner join market_last as m
        on t.Market = m.Market
    left join {{ ref('int_stocks__liquidity') }} as l
        on t.Ticker = l.Ticker and t.Market = l.Market
),

tiered as (
    select
        *,
        case
            when adv_20d is null then 'unknown'
            when adv_20d >= 1000000 then 'high'
            when adv_20d >= 100000 then 'mid'
            else 'low'
        end as liquidity_tier
    from joined
)

select
    Ticker,
    Market,
    history_days,
    gap_days,
    adv_20d,
    dollar_volume_20d,
    liquidity_tier,
    (
        coalesce(adv_20d, 0) >= 100000
        and history_days >= 252
        and gap_days < 5
    ) as investable_flag
from tiered
