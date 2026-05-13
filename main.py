import os
from typing import Dict, List

import numpy as np
import pandas as pd
import vectorbt as vbt
import yfinance as yf

from utils.fs import get_configs

massive_api_key = os.environ["MASSIVE_API"]


def main():
    configs = get_configs()
    print(configs["tickers.toml"])
    print(massive_api_key)

    print()
    data = vbt.YFData.download("BTC-USD")
    price = data.get("Close")
    print(price)


if __name__ == "__main__":
    main()
