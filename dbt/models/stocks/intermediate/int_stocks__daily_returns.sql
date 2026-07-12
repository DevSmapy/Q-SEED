with ordered as (
    select
        Date,
        Ticker,
        Market,
        Close,
        lag(Close, 1) over (
            partition by Ticker
            order by Date
        ) as prev_close,
        lead(Close, 21) over (
            partition by Ticker
            order by Date
        ) as forward_close_21d
    from {{ ref('stg_stocks__raw_stocks') }}
    where Close is not null
)

select
    Date,
    Ticker,
    Market,
    Close,
    case
        when prev_close is null or prev_close = 0 then null
        else (Close / prev_close) - 1
    end as daily_return,
    case
        when forward_close_21d is null or Close = 0 then null
        else (forward_close_21d / Close) - 1
    end as forward_return_21d
from ordered
