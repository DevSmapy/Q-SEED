import os
from collections.abc import Iterator

import FinanceDataReader
import yfinance as yf
from google.cloud import storage

MAX_STOCKS = 100


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

    div_krx_list = divide_list(krx_list, 100)

    # get stock info
    no_data_list = []
    i = 0
    for stocks in div_krx_list:
        stocks_str = " ".join(stocks)
        stocks_tickers = yf.Tickers(stocks_str)
        for stock in stocks:
            if i >= MAX_STOCKS:
                break

            try:
                hist = stocks_tickers.tickers[stock].history(period="1y")
            except Exception:
                no_data_list.append(stock)
                continue

            if hist.empty:
                no_data_list.append(stock)
                continue
            else:
                hist.to_csv(f"./kor_ticker/{stock}.csv", header=True, sep=",")
                i += 1

        # upload stock info to GCS
        """if bucket_name:
            upload_to_gcs(bucket_name, local_path, f"kor_ticker/{stock}.csv")"""

        if i >= MAX_STOCKS:
            break

    with open("no_data_list.txt", "w") as f:
        f.write("\n".join(no_data_list))
