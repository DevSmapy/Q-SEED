select
    *
from {{ source('raw', 'raw_stocks') }}
