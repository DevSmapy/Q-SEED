with ticker_stats as (
    select
        Ticker,
        Market,
        min(Date) as start_date,
        max(Date) as end_date,
        count(*) as row_count
    from {{ ref('stg_stocks__raw_stocks') }}
    group by 1, 2
)

select
    t.Ticker,
    t.Market,
    d.country,
    t.start_date,
    t.end_date,
    t.row_count,
    case
        when t.row_count < 252 then '<1y'
        when t.row_count < 252 * 3 then '1-3y'
        when t.row_count < 252 * 5 then '3-5y'
        when t.row_count < 252 * 10 then '5-10y'
        else '10y+'
    end as history_bucket
from ticker_stats as t
left join {{ ref('dim_stocks__market') }} as d
    on t.Market = d.Market
