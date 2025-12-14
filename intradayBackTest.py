# backtest_intraday.py
import yfinance as yf
import pandas as pd
from datetime import time

# ---------------- CONFIG ----------------
INTERVAL = "15m"
PERIOD = "60d"          # Yahoo intraday limit
ENTRY_AFTER = time(9, 45)
FORCE_EXIT = time(15, 15)

RISK_PCT = 0.005        # 0.5% SL
RR_TARGET = 2.0         # 1:2 RR

SYMBOLS = [
    "TCS.NS",
    "INFY.NS",
    "SBIN.NS",
    "RELIANCE.NS",
    "TVSMOTOR.NS"
]
# --------------------------------------


def backtest_intraday(symbol):
    print(f"\nRunning backtest for {symbol}")

    df = yf.download(
        symbol,
        interval=INTERVAL,
        period=PERIOD,
        progress=False
    )

    if df is None or df.empty:
        print(f"{symbol}: No data")
        return []

    # 🔥 KEEP DATETIME AS INDEX (IMPORTANT)
    df.index = pd.to_datetime(df.index)
    df["TradeDate"] = df.index.date

    trades = []

    # -------- DAY LOOP --------
    for day, day_df in df.groupby("TradeDate"):
        entry = None
        entry_time = None
        stop = None
        target = None

        for idx, candle in day_df.iterrows():

            # ✅ idx is Timestamp → idx.time() is SCALAR
            candle_time = idx.time()

            # ENTRY
            if entry is None:
                if candle_time < ENTRY_AFTER:
                    continue

                entry = float(candle["Open"])
                entry_time = candle_time
                stop = entry * (1 - RISK_PCT)
                target = entry * (1 + RISK_PCT * RR_TARGET)
                continue

            high = float(candle["High"])
            low = float(candle["Low"])

            # TARGET HIT
            if high >= target:
                trades.append({
                    "Symbol": symbol,
                    "Date": day,
                    "Entry Time": entry_time.strftime("%H:%M"),
                    "Entry": round(entry, 2),
                    "Exit Time": candle_time.strftime("%H:%M"),
                    "Exit": round(target, 2),
                    "Result": "WIN",
                    "RR": RR_TARGET
                })
                break

            # STOP LOSS HIT
            if low <= stop:
                trades.append({
                    "Symbol": symbol,
                    "Date": day,
                    "Entry Time": entry_time.strftime("%H:%M"),
                    "Entry": round(entry, 2),
                    "Exit Time": candle_time.strftime("%H:%M"),
                    "Exit": round(stop, 2),
                    "Result": "LOSS",
                    "RR": -1.0
                })
                break

            # FORCE EXIT
            if candle_time >= FORCE_EXIT:
                exit_price = float(candle["Close"])
                rr = (exit_price - entry) / (entry - stop)

                trades.append({
                    "Symbol": symbol,
                    "Date": day,
                    "Entry Time": entry_time.strftime("%H:%M"),
                    "Entry": round(entry, 2),
                    "Exit Time": candle_time.strftime("%H:%M"),
                    "Exit": round(exit_price, 2),
                    "Result": "WIN" if rr > 0 else "LOSS",
                    "RR": round(rr, 2)
                })
                break

    print(f"{symbol}: {len(trades)} trades")
    return trades


# ---------------- RUN ----------------
all_trades = []

for sym in SYMBOLS:
    all_trades.extend(backtest_intraday(sym))

if not all_trades:
    print("\nNo trades found.")
    exit()

df = pd.DataFrame(all_trades)

wins = df[df["RR"] > 0]
losses = df[df["RR"] < 0]

print("\n========== SUMMARY ==========")
print(f"Total trades      : {len(df)}")
print(f"Win rate (%)      : {len(wins)/len(df)*100:.2f}")
print(f"Avg Win RR        : {wins['RR'].mean():.2f}" if not wins.empty else "Avg Win RR : 0")
print(f"Avg Loss RR       : {abs(losses['RR'].mean()):.2f}" if not losses.empty else "Avg Loss RR : 0")

expectancy = (
    (len(wins)/len(df)) * (wins["RR"].mean() if not wins.empty else 0)
    - (len(losses)/len(df)) * (abs(losses["RR"].mean()) if not losses.empty else 0)
)

print(f"Expectancy (R)    : {expectancy:.2f}")
