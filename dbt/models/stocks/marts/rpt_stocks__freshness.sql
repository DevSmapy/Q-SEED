with market_max as (
    select
        Market,
        max(Date) as last_date
    from {{ ref('stg_stocks__raw_stocks') }}
    group by 1
),

global_max as (
    select max(last_date) as global_last_date
    from market_max
)

select
    m.Market,
    d.country,
    m.last_date,
    g.global_last_date,
    date_diff('day', m.last_date, g.global_last_date) as lag_days
from market_max as m
cross join global_max as g
left join {{ ref('dim_stocks__market') }} as d
    on m.Market = d.Market
order by lag_days desc, m.Market
