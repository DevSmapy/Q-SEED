{% macro calculate_roe(net_income, equity) %}
    CASE
        WHEN {{ equity }} = 0 THEN NULL
        ELSE ({{ net_income }}::FLOAT / {{ equity }}) * 100
    END
{% endmacro %}
