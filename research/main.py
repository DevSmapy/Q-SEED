import os
from collections.abc import Iterator

import duckdb
import FinanceDataReader
import yfinance as yf
from google.cloud import storage

CHUNK_SIZE = 100
MAX_STOCKS = 500


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

    div_krx_list = divide_list(krx_list, CHUNK_SIZE)

    # connection stock db
    conn = duckdb.connect("my_stocks.db")

    # create table
    conn.execute("""
    CREATE OR REPLACE TABLE raw_stocks
    (Date Timestamp, Ticker TEXT, Open REAL, High REAL, Low REAL, Close REAL, Volume BIGINT)
    """)

    # get all KRX stocks information
    load_tickers = []  # success stocks names
    total = 0  # total stocks
    n_success = 0  # success stocks count
    success_tickers = []  # success stocks names

    for stocks in div_krx_list:
        # add stocks names to list
        load_tickers.extend(stocks)

        # get stocks information(multiple stocks with multiple threads)
        df = yf.download(stocks, period="1y", threads=True, group_by="Ticker", auto_adjust=True)

        # add column 'Ticker'
        df_flat = df.stack(level=0, future_stack=True).reset_index()

        # drop unnecessary columns
        if "Adj Close" in df_flat.columns:
            df_flat = df_flat.drop(columns=["Adj Close"])

        df_flat = df_flat.dropna(subset=["Close"])  # drop NaN values for identifying no data stocks

        conn.execute(
            """INSERT INTO raw_stocks SELECT * FROM df_flat"""
        )  # insert stocks information to db

        success_tickers.extend(df_flat["Ticker"].tolist())
        n_success += df_flat["Ticker"].nunique()  # count success stocks

        total += CHUNK_SIZE  # count total stocks

        print(f"Processed {n_success}/{total} stocks")

        # save stocks information to parquet
        df_flat.to_parquet(f"./kor_ticker/stocks_{total}.parquet", engine="pyarrow")

        if total >= MAX_STOCKS:
            break

    conn.close()  # close db connection

    # get no data stocks
    no_data_list = list(set(load_tickers) - set(success_tickers))

    print(len(no_data_list), "stocks have no data")

    # save no data stocks to file
    with open("no_data_list.txt", "w") as f:
        f.write("\n".join(no_data_list))
