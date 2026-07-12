select
    d.country,
    d.currency,
    count(distinct s.Ticker) as ticker_count,
    count(*) as row_count,
    count(distinct s.Market) as market_count,
    min(s.Date) as min_date,
    max(s.Date) as max_date
from {{ ref('stg_stocks__raw_stocks') }} as s
inner join {{ ref('dim_stocks__market') }} as d
    on s.Market = d.Market
group by 1, 2
order by ticker_count desc
