-- Static market dimension: country/currency derived from listing universe.
-- KONEX shares .KS suffix with KOSPI; country still KR via Market map.
with markets as (
    select distinct Market
    from {{ ref('stg_stocks__raw_stocks') }}
)

select
    Market,
    case
        when Market in ('KOSPI', 'KOSDAQ', 'KONEX') then 'KR'
        when Market in ('S&P500', 'NASDAQ', 'NYSE', 'AMEX') then 'US'
        else 'OTHER'
    end as country,
    case
        when Market in ('KOSPI', 'KOSDAQ', 'KONEX') then 'KRW'
        when Market in ('S&P500', 'NASDAQ', 'NYSE', 'AMEX') then 'USD'
        else 'UNKNOWN'
    end as currency
from markets
