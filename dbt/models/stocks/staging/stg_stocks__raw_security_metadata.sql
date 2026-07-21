select
    Ticker,
    Market,
    company_name,
    quote_type,
    sector_raw,
    sector,
    industry_raw,
    industry,
    sector_key,
    industry_key,
    country,
    currency,
    sector_source,
    sector_status,
    sector_status_reason,
    cast(as_of as date) as as_of,
    updated_at
from {{ source('stocks', 'raw_security_metadata') }}
