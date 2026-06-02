import pandas as pd
from pandas import DataFrame, Series


class PriceRepo:
    def get_ohlcv(ticker, start, end, adjusted=True) -> DataFrame:
        pass

    def get_latest(ticker) -> Series:
        pass

    def get_multi(tickers, date) -> DataFrame:
        pass
