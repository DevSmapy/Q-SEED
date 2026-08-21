-- dim_stocks__security grain: one row per (Ticker, Market)
select
    Ticker,
    Market,
    count(*) as n
from {{ ref('dim_stocks__security') }}
group by 1, 2
having count(*) > 1
