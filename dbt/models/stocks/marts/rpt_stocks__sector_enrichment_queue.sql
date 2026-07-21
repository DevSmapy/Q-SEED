select
    Ticker,
    Market,
    company_name,
    sector,
    industry,
    sector_status,
    sector_status_reason,
    sector_source,
    as_of
from {{ ref('dim_stocks__security') }}
where upper(coalesce(quote_type, '')) = 'EQUITY'
  and sector_status in ('unclassified', 'error')
order by Market, Ticker
