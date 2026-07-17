select
    Date,
    Market,
    advances,
    declines,
    unchanged,
    adr_20d,
    ad_line,
    pct_above_ma20,
    pct_above_ma200
from {{ source('market', 'raw_market_breadth') }}
