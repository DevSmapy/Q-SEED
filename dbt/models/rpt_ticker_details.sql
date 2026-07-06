select
    Ticker,
    Market,
    min(Date) as start_date,
    max(Date) as end_date,
    count(*) as row_count
from {{ ref('stg_raw_stocks') }}
group by 1, 2
