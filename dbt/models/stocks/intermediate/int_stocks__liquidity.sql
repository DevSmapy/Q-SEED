with recent as (
    select
        Ticker,
        Market,
        avg(Volume) as adv_20d,
        avg(Close * Volume) as dollar_volume_20d
    from {{ ref('stg_stocks__raw_stocks') }}
    where Date >= (
        select max(Date) - interval '20 days'
        from {{ ref('stg_stocks__raw_stocks') }}
    )
    group by 1, 2
)

select
    Ticker,
    Market,
    adv_20d,
    dollar_volume_20d
from recent
