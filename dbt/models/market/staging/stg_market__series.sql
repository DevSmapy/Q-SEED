select
    Date,
    series_id,
    value,
    source
from {{ source('market', 'raw_market_series') }}
