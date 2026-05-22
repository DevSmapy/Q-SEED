select
    count(*) as total_row_count,
    count(distinct Ticker) as total_ticker_count,
    min(Date) as first_date,
    max(Date) as last_date
from {{ ref('stg_raw_stocks') }}
