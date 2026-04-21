import os
import time
from collections.abc import Iterator

import duckdb
import FinanceDataReader
import yfinance as yf
from google.cloud import storage

CHUNK_SIZE = 100
MAX_STOCKS = 3000


def divide_list(lst: list[str], n: int) -> Iterator[list[str]]:
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def upload_to_gcs(bucket_name: str, source_file_name: str, destination_blob_name: str) -> None:
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")


if __name__ == "__main__":
    # get environment variable
    """bucket_name = os.getenv("GCS_BUCKET_NAME")"""

    os.makedirs("./kor_ticker", exist_ok=True)

    # make stock list of KRX
    krx_list = FinanceDataReader.StockListing("KRX")["Code"].apply(lambda x: x + ".KS")

    ticker_list_path = "./kor_ticker/krx_list.csv"
    krx_list.to_csv(ticker_list_path, index=False, header=False)

    # upload stock list to GCS
    """if bucket_name:
        upload_to_gcs(bucket_name, ticker_list_path, "kor_ticker/krx_list.csv")"""

    # make stock list of KRX
    krx_list = krx_list.tolist()
    if len(krx_list) < MAX_STOCKS:
        print("KRX stocks count is less than MAX_STOCKS")
        print(f"MAX_STOCKS: {MAX_STOCKS}")
        print("So set MAX_STOCKS to KRX stocks count")
        print(f"KRX stocks count: {len(krx_list)}")
        MAX_STOCKS = len(krx_list)

    div_krx_list = divide_list(krx_list, CHUNK_SIZE)

    # connection stock db
    conn = duckdb.connect("my_stocks.db")

    # create table
    conn.execute("""
    CREATE OR REPLACE TABLE raw_stocks
    (Date Timestamp, Ticker TEXT, Open REAL, High REAL, Low REAL, Close REAL,
    Volume BIGINT, Dividends REAL, Split REAL)
    """)

    # get all KRX stocks information
    load_tickers = []  # loading stocks names
    success_tickers = set()  # success stocks names (set으로 변경)

    for stocks in div_krx_list:
        # add stocks names to list
        load_tickers.extend(stocks)

        # get stocks information(multiple stocks with multiple threads)
        df = yf.download(
            stocks, period="max", threads=True, group_by="Ticker", auto_adjust=True, actions=True
        )

        # add column 'Ticker'
        df_flat = df.stack(level=0, future_stack=True).reset_index()

        # drop unnecessary columns
        if "Adj Close" in df_flat.columns:
            df_flat = df_flat.drop(columns=["Adj Close"])
        if "Capital Gains" in df_flat.columns:
            df_flat = df_flat.drop(columns=["Capital Gains"])

        # rename columns
        if "Stock Splits" in df_flat.columns:
            df_flat.rename(columns={"Stock Splits": "Split"}, inplace=True)

        # add column 'Dividends'
        if "Dividends" not in df_flat.columns:
            df_flat["Dividends"] = 0.0

        # add column 'Split'
        if "Split" not in df_flat.columns:
            df_flat["Split"] = 1.0  # because there is no stock split

        df_flat = df_flat.dropna(subset=["Close"])  # drop NaN values for identifying no data stocks

        conn.execute(
            """INSERT INTO raw_stocks SELECT * FROM df_flat"""
        )  # insert stocks information to db

        # 고유한 티커만 추가 (unique한 값만)
        success_tickers.update(df_flat["Ticker"].unique())

        # 실제 로드 시도한 개수와 성공 개수 계산
        n_loaded = len(load_tickers)  # 실제 로드 시도한 총 개수
        n_success = len(success_tickers)
        n_failed = n_loaded - n_success

        print(f"Processed: {n_success} success / {n_failed} failed / {n_loaded} total attempted")

        # save stocks information to parquet
        df_flat.to_parquet(f"./kor_ticker/stocks_{n_loaded}.parquet", engine="pyarrow")
        time.sleep(5)

        if n_loaded >= MAX_STOCKS:
            break

    conn.close()  # close db connection

    # get no data stocks
    no_data_list = list(set(load_tickers) - success_tickers)

    print("\n=== Final Summary ===")
    print(f"Total attempted: {len(load_tickers)}")
    print(f"Success: {len(success_tickers)}")
    print(f"Failed: {len(no_data_list)}")
    print(f"Success rate: {len(success_tickers) / len(load_tickers) * 100:.2f}%")

    # save no data stocks to file
    with open("no_data_list.txt", "w") as f:
        f.write("\n".join(no_data_list))
