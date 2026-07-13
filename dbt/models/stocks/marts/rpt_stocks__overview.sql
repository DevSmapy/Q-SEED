select
    count(*) as total_row_count,
    count(distinct Ticker) as total_ticker_count,
    count(distinct Market) as total_market_count,
    min(Date) as min_date,
    max(Date) as max_date
from {{ ref('stg_stocks__raw_stocks') }}
