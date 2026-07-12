-- Market-stratified daily return summary (KRW/USD mixed — never pool across markets).
with ordered as (
    select
        Date,
        Ticker,
        Market,
        Close,
        Volume,
        lag(Close, 1) over (
            partition by Ticker
            order by Date
        ) as prev_close
    from {{ ref('stg_stocks__raw_stocks') }}
    where Close is not null
),

returns as (
    select
        Market,
        case
            when prev_close is null or prev_close = 0 then null
            else (Close / prev_close) - 1
        end as daily_return,
        Close,
        Volume
    from ordered
),

agg as (
    select
        Market,
        count(*) as observation_count,
        avg(daily_return) as mean_return,
        stddev_samp(daily_return) as std_return,
        quantile_cont(daily_return, 0.05) as p05_return,
        quantile_cont(daily_return, 0.50) as median_return,
        quantile_cont(daily_return, 0.95) as p95_return,
        sum(case when abs(daily_return) > 0.20 then 1 else 0 end) as extreme_return_count,
        quantile_cont(Close, 0.50) as median_close,
        quantile_cont(Volume, 0.50) as median_volume,
        avg(case when Volume = 0 then 1.0 else 0.0 end) as zero_volume_rate
    from returns
    where daily_return is not null
    group by Market
)

select
    a.Market,
    d.country,
    d.currency,
    a.observation_count,
    a.mean_return,
    a.std_return,
    a.p05_return,
    a.median_return,
    a.p95_return,
    a.extreme_return_count,
    round(100.0 * a.extreme_return_count / nullif(a.observation_count, 0), 4) as extreme_return_pct,
    a.median_close,
    a.median_volume,
    round(100.0 * a.zero_volume_rate, 2) as zero_volume_pct
from agg as a
left join {{ ref('dim_stocks__market') }} as d
    on a.Market = d.Market
order by a.Market
