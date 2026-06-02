# APIs - Available

- `yfinance`
- [sec-edgar-api](https://sec-edgar-api.readthedocs.io/en/latest/)
- `fredapi`

## Massive API

The API base URL is https://api.massive.com/ (with paths like /v3/ or asset-specific like /stocks/v1/ in some docs; versioning appears to use v1/v2/v3 depending on endpoint). All responses are structured JSON (with fields like status, count, results, request_id, next for pagination).

- Stocks Basic
- Forex EOD
- Crypto EOD
- reference/reference data
- corporate actions (dividend, splits)
- technical indicators (SMA, EMA, RSI, MACD)
- minute-levl aggregations for US stocks (OHLCV bars)

Tier

- Rate limit: 5 API requests/minute
- Historical Depth: 2 years
- Data types:

```sh
curl "https://api.massive.com/v3/reference/dividends?apiKey=$MASSIVE_API"
```
