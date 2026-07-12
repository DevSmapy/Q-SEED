select
    Date,
    Ticker,
    Market,
    Open,
    High,
    Low,
    Close,
    Volume,
    Dividends,
    Split
from {{ source('stocks', 'raw_stocks') }}
