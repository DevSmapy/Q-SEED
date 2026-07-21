with base as (
    select
        sector,
        Market,
        count(*) as ticker_count
    from {{ ref('dim_stocks__security') }}
    group by 1, 2
),

totals as (
    select count(*) as total_tickers from {{ ref('dim_stocks__security') }}
),

sector_totals as (
    select
        sector,
        sum(ticker_count) as ticker_count
    from base
    group by 1
)

select
    s.sector,
    s.ticker_count,
    round(100.0 * s.ticker_count / t.total_tickers, 2) as pct_of_universe,
    case when s.sector = 'Unclassified' then s.ticker_count else 0 end as unclassified_count
from sector_totals as s
cross join totals as t
order by s.ticker_count desc
