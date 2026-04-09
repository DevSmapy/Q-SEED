import FinanceDataReader
import yfinance as yf
from tqdm import tqdm

if __name__ == "__main__":
    # make stock list of KRX
    krx_list = FinanceDataReader.StockListing("KRX")["Code"].apply(lambda x: x + ".KS")

    krx_list.to_csv("./kor_ticker/krx_list.csv", index=False, header=False)

    # make stock list of KRX
    krx_list = krx_list.tolist()

    # get stock info
    i = 0
    for stock in tqdm(krx_list):
        stock_ticker = yf.Ticker(stock)

        hist = stock_ticker.history(period="1y")

        hist.to_csv(f"./kor_ticker/{stock}.csv", header=True, sep=",")
