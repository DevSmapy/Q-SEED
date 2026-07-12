with ordered as (
    select
        Date,
        Ticker,
        Market,
        Close,
        Volume,
        lag(Close, 21) over w as close_lag_21,
        lag(Close, 126) over w as close_lag_126,
        lag(Close, 252) over w as close_lag_252,
        lag(Close, 5) over w as close_lag_5,
        avg(cast(Volume as double)) over (
            partition by Ticker
            order by Date
            rows between 19 preceding and current row
        ) as volume_avg_20d
    from {{ ref('stg_stocks__raw_stocks') }}
    where Close is not null
    window w as (partition by Ticker order by Date)
),

with_returns as (
    select
        *,
        case
            when lag(Close, 1) over w is null or lag(Close, 1) over w = 0 then null
            else (Close / lag(Close, 1) over w) - 1
        end as daily_return
    from ordered
    window w as (partition by Ticker order by Date)
)

select
    Date,
    Ticker,
    Market,
    case
        when close_lag_252 is null or close_lag_252 = 0 then null
        else (close_lag_21 / close_lag_252) - 1
    end as momentum_12_1,
    case
        when close_lag_126 is null or close_lag_126 = 0 then null
        else (Close / close_lag_126) - 1
    end as momentum_6m,
    case
        when close_lag_5 is null or close_lag_5 = 0 then null
        else -((Close / close_lag_5) - 1)
    end as reversal_5d,
    stddev_samp(daily_return) over (
        partition by Ticker
        order by Date
        rows between 59 preceding and current row
    ) as volatility_60d,
    case
        when volume_avg_20d is null or volume_avg_20d = 0 then null
        else cast(Volume as double) / volume_avg_20d
    end as volume_ratio_20d,
    ln(1 + Close * cast(Volume as double)) as log_dollar_volume
from with_returns
