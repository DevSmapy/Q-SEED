with ranked as (
    select
        *,
        row_number() over (
            partition by Ticker, Market
            order by updated_at desc
        ) as rn
    from {{ ref('stg_stocks__raw_security_metadata') }}
),

latest as (
    select * from ranked where rn = 1
)

select
    l.Ticker,
    l.Market,
    l.company_name,
    l.quote_type,
    l.sector,
    l.industry,
    l.sector_status,
    l.sector_status_reason,
    l.sector_source,
    l.as_of,
    coalesce(l.country, m.country) as country,
    coalesce(l.currency, m.currency) as currency
from latest as l
left join {{ ref('dim_stocks__market') }} as m
    on l.Market = m.Market
