select
    Ticker,
    Market,
    count(*) as row_count,
    min(Date) as start_date,
    max(Date) as end_date
from {{ ref('stg_raw_stocks') }}
group by 1, 2
