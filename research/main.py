import os

import FinanceDataReader
import yfinance as yf
from google.cloud import storage
from tqdm import tqdm


def upload_to_gcs(bucket_name: str, source_file_name: str, destination_blob_name: str) -> None:
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")


if __name__ == "__main__":
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    os.makedirs("./kor_ticker", exist_ok=True)

    # make stock list of KRX
    krx_list = FinanceDataReader.StockListing("KRX")["Code"].apply(lambda x: x + ".KS")

    ticker_list_path = "./kor_ticker/krx_list.csv"
    krx_list.to_csv(ticker_list_path, index=False, header=False)

    if bucket_name:
        upload_to_gcs(bucket_name, ticker_list_path, "kor_ticker/krx_list.csv")

    # make stock list of KRX
    krx_list = krx_list.tolist()

    # get stock info
    for stock in tqdm(krx_list):
        stock_ticker = yf.Ticker(stock)
        hist = stock_ticker.history(period="1y")

        local_path = f"./kor_ticker/{stock}.csv"
        hist.to_csv(local_path, header=True, sep=",")

        if bucket_name:
            upload_to_gcs(bucket_name, local_path, f"kor_ticker/{stock}.csv")
