-- Local/CI seed for dbt before security-master ingest runs.
-- Apply manually: duckdb data/stocks.db < tests/fixtures/seed_security_metadata.sql
INSERT OR REPLACE INTO raw_security_metadata (
    Ticker, Market, company_name, quote_type,
    sector_raw, sector, industry_raw, industry,
    sector_key, industry_key, country, currency,
    sector_source, sector_status, sector_status_reason,
    as_of, updated_at
) VALUES
    ('AAPL', 'NASDAQ', 'Apple Inc.', 'EQUITY', 'Technology', 'Information Technology', 'Consumer Electronics', 'Consumer Electronics', 'technology', 'consumer-electronics', 'United States', 'USD', 'yfinance', 'mapped', NULL, CURRENT_DATE, CURRENT_TIMESTAMP),
    ('MSFT', 'NASDAQ', 'Microsoft', 'EQUITY', 'Technology', 'Information Technology', 'Software', 'Software', 'technology', 'software-infrastructure', 'United States', 'USD', 'yfinance', 'mapped', NULL, CURRENT_DATE, CURRENT_TIMESTAMP),
    ('005930.KS', 'KOSPI', 'SamsungElec', 'EQUITY', 'Technology', 'Information Technology', 'Semiconductors', 'Semiconductors', 'technology', 'semiconductors', 'South Korea', 'KRW', 'yfinance', 'mapped', NULL, CURRENT_DATE, CURRENT_TIMESTAMP),
    ('SPY', 'NYSE', 'SPDR S&P 500', 'ETF', NULL, 'Unclassified', NULL, NULL, NULL, NULL, 'United States', 'USD', 'yfinance', 'unclassified', 'non_equity', CURRENT_DATE, CURRENT_TIMESTAMP),
    ('UNKNOWN.KS', 'KOSPI', NULL, 'EQUITY', NULL, 'Unclassified', NULL, NULL, NULL, NULL, 'South Korea', 'KRW', 'yfinance', 'unclassified', 'missing_yahoo', CURRENT_DATE, CURRENT_TIMESTAMP);
