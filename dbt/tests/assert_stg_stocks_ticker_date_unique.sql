-- raw_stocks / staging grain: one row per (Ticker, Date)
select
    Ticker,
    Date,
    count(*) as n
from {{ ref('stg_stocks__raw_stocks') }}
group by 1, 2
having count(*) > 1
