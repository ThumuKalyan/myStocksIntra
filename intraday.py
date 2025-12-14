import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, time, timedelta
import pytz
import time as t_sleep

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Trend Sniper Algo", page_icon="🎯", layout="wide")

# --- CUSTOM CSS FOR UI ---
st.markdown("""
    <style>
    .metric-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
    }
    .success-box {
        padding: 10px;
        background-color: #d4edda;
        color: #155724;
        border-radius: 5px;
        text-align: center;
        font-weight: bold;
    }
    .fail-box {
        padding: 10px;
        background-color: #f8d7da;
        color: #721c24;
        border-radius: 5px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- EXPANDED SECTOR & STOCK MAPPING (Major Liquid Stocks) ---
SECTOR_MAP = {
    "NIFTY IT": {
        "Index": "^CNXIT",
        "Stocks": [
            "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "LTIM.NS", "TECHM.NS", 
            "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS"
        ]
    },
    "NIFTY BANK": {
        "Index": "^NSEBANK",
        "Stocks": [
            "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", 
            "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS"
        ]
    },
    "NIFTY AUTO": {
        "Index": "^CNXAUTO",
        "Stocks": [
            "TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", 
            "HEROMOTOCO.NS", "TVSMOTOR.NS", "ASHOKLEY.NS", "BHARATFORG.NS"
        ]
    },
    "NIFTY METAL": {
        "Index": "^CNXMETAL",
        "Stocks": [
            "TATASTEEL.NS", "JINDALSTEL.NS", "HINDALCO.NS", "VEDL.NS", "JSWSTEEL.NS", 
            "SAIL.NS", "NMDC.NS", "NATIONALUM.NS"
        ]
    },
    "NIFTY PHARMA": {
        "Index": "^CNXPHARMA",
        "Stocks": [
            "SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", 
            "LUPIN.NS", "AUROPHARMA.NS", "ALKEM.NS"
        ]
    },
    "NIFTY FMCG": {
        "Index": "^CNXFMCG",
        "Stocks": [
            "ITC.NS", "HINDUNILVR.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", 
            "MARICO.NS", "DABUR.NS", "GODREJCP.NS"
        ]
    },
    "NIFTY ENERGY": {
        "Index": "^CNXENERGY",
        "Stocks": [
            "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS", 
            "BPCL.NS", "IOC.NS", "ADANIGREEN.NS", "TATAPOWER.NS"
        ]
    },
    "NIFTY REALTY": {
        "Index": "^CNXREALTY",
        "Stocks": [
            "DLF.NS", "GODREJPROP.NS", "LODHA.NS", "OBEROIRLTY.NS", "PHOENIXLTD.NS"
        ]
    }
}

# --- HELPER FUNCTIONS ---
def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

def fetch_data(symbol, period="5d", interval="15m"):
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return pd.DataFrame()

def calculate_technical_indicators(df):
    if df.empty: return df
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # EMA 20
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # VWAP (Daily Reset)
    df['Date'] = df.index.date
    today = df.index[-1].date()
    today_data = df[df.index.date == today].copy()
    today_data['Cum_Vol'] = today_data['Volume'].cumsum()
    today_data['Cum_Vol_Price'] = (today_data['Close'] * today_data['Volume']).cumsum()
    
    # Map VWAP back to main DF
    df.loc[today_data.index, 'VWAP'] = today_data['Cum_Vol_Price'] / today_data['Cum_Vol']
    
    return df

# --- SIDEBAR CONTROLS ---
st.sidebar.title("🛠️ Strategy Settings")

selected_sector = st.sidebar.selectbox("1. Select Sector", list(SECTOR_MAP.keys()))
sector_info = SECTOR_MAP[selected_sector]
selected_stock = st.sidebar.selectbox("2. Select Stock", sector_info["Stocks"])

st.sidebar.markdown("---")
rsi_limit = st.sidebar.slider("RSI Threshold", 40, 80, 60)
target_pct = st.sidebar.number_input("Target (%)", 0.5, 5.0, 1.0, 0.1) / 100
stoploss_pct = st.sidebar.number_input("Stoploss (%)", 0.1, 2.0, 0.5, 0.1) / 100

run_scanner = st.sidebar.checkbox("🚀 START LIVE SCANNER", value=False)

# --- MAIN DASHBOARD ---
st.title(f"🎯 15-Min Trend Sniper: {selected_stock}")
st.caption(f"Tracking Sector: {selected_sector} | Strategy: 15m Breakout + RSI > {rsi_limit} + EMA 20 + VWAP")

# Placeholders for Live Updates
header_ph = st.empty()
metrics_ph = st.empty()
chart_ph = st.empty()
status_ph = st.empty()
log_ph = st.empty()

# --- LIVE LOGIC ---
if run_scanner:
    
    # Loop for Live Update
    while True:
        current_time = get_ist_time().time()
        
        # 1. FETCH DATA
        with header_ph.container():
            st.info(f"⏳ Scanning... Last Update: {get_ist_time().strftime('%H:%M:%S')}")

        df = fetch_data(selected_stock)
        sector_df = fetch_data(sector_info["Index"])
        nifty_df = fetch_data("^NSEI")
        
        if df.empty or len(df) < 5:
            st.error("Data not available yet. Waiting...")
            t_sleep.sleep(10)
            continue
            
        df = calculate_technical_indicators(df)
        last_candle = df.iloc[-1]
        
        # 2. CALCULATE RANGE (10:00 AM Logic)
        today_df = df[df.index.date == datetime.now().date()]
        range_high = 0
        range_low = 0
        avg_vol = 0
        
        if len(today_df) >= 3:
            range_candles = today_df.iloc[0:3]
            range_high = range_candles['High'].max()
            range_low = range_candles['Low'].min()
            avg_vol = range_candles['Volume'].mean()
        
        # 3. CHECK CONDITIONS
        cmp = last_candle['Close']
        
        # Trends
        sector_trend = False
        market_trend = False
        if not sector_df.empty:
            sector_trend = sector_df.iloc[-1]['Close'] > sector_df.iloc[0]['Open']
        if not nifty_df.empty:
            market_trend = nifty_df.iloc[-1]['Close'] > nifty_df.iloc[0]['Open']
            
        # Strategy Checks
        cond_breakout = (cmp > range_high) and (range_high > 0)
        cond_rsi = last_candle['RSI'] > rsi_limit
        cond_ema = cmp > last_candle['EMA_20']
        cond_vwap = cmp > last_candle['VWAP']
        cond_vol = last_candle['Volume'] > avg_vol
        
        # Body Strength
        body = abs(last_candle['Close'] - last_candle['Open'])
        full_range = last_candle['High'] - last_candle['Low']
        cond_body = (body / full_range) >= 0.5 if full_range > 0 else False
        
        # Double Confirmation Status
        trend_status = "BULLISH" if sector_trend and market_trend else ("WEAK" if not sector_trend else "MODERATE")

        # 4. UI UPDATES
        
        # A. Key Metrics Row
        with metrics_ph.container():
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Live Price", f"₹{round(cmp, 2)}", f"{round(cmp - df.iloc[-2]['Close'], 2)}")
            col2.metric("RSI (14)", f"{round(last_candle['RSI'], 1)}", delta_color="normal" if cond_rsi else "inverse")
            col3.metric("Range High (Buy)", f"₹{range_high}")
            col4.metric("Sector Trend", "UP 🟢" if sector_trend else "DOWN 🔴")

        # B. Strategy Checklist Table
        with status_ph.container():
            st.markdown("### 📋 Strategy Checklist")
            
            check_col1, check_col2, check_col3, check_col4 = st.columns(4)
            
            def get_status_html(label, condition, value=""):
                color = "#d4edda" if condition else "#f8d7da" # Green / Red
                text_color = "#155724" if condition else "#721c24"
                icon = "✅" if condition else "❌"
                return f"""
                <div style="background-color: {color}; color: {text_color}; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 5px;">
                    <small>{label}</small><br>
                    <strong>{icon} {value}</strong>
                </div>
                """

            with check_col1:
                st.markdown(get_status_html("1. Breakout", cond_breakout, f"> {range_high}"), unsafe_allow_html=True)
                st.markdown(get_status_html("5. Volume", cond_vol), unsafe_allow_html=True)
            with check_col2:
                st.markdown(get_status_html("2. RSI > 60", cond_rsi, round(last_candle['RSI'],1)), unsafe_allow_html=True)
                st.markdown(get_status_html("6. Body > 50%", cond_body), unsafe_allow_html=True)
            with check_col3:
                st.markdown(get_status_html("3. EMA 20", cond_ema, round(last_candle['EMA_20'],1)), unsafe_allow_html=True)
                st.markdown(get_status_html("7. Sector", sector_trend), unsafe_allow_html=True)
            with check_col4:
                st.markdown(get_status_html("4. VWAP", cond_vwap, round(last_candle['VWAP'],1)), unsafe_allow_html=True)
                st.markdown(get_status_html("8. Market", market_trend), unsafe_allow_html=True)

            # FINAL SIGNAL
            all_conditions = [cond_breakout, cond_rsi, cond_ema, cond_vwap, cond_vol, cond_body, sector_trend]
            
            if current_time < time(10, 0):
                st.warning(f"⏳ Waiting for 10:00 AM Range Formation... (Current: {current_time.strftime('%H:%M')})")
            elif current_time > time(14, 0):
                st.error("🛑 No New Entries after 2:00 PM")
            elif all(all_conditions):
                st.markdown(f"""
                <div style="background-color: #28a745; color: white; padding: 15px; border-radius: 10px; text-align: center; font-size: 20px;">
                    🚀 <strong>BUY SIGNAL TRIGGERED!</strong> <br>
                    Entry: {range_high + 0.5} | Target: {round((range_high + 0.5)*(1+target_pct),1)} | SL: {range_low}
                </div>
                """, unsafe_allow_html=True)
            else:
                 st.markdown(f"""
                <div style="background-color: #ffc107; color: black; padding: 10px; border-radius: 10px; text-align: center;">
                    👀 Monitoring... Waiting for all conditions to turn GREEN.
                </div>
                """, unsafe_allow_html=True)

        # C. Interactive Chart (Plotly)
        with chart_ph.container():
            fig = go.Figure(data=[go.Candlestick(x=df.index,
                            open=df['Open'], high=df['High'],
                            low=df['Low'], close=df['Close'], name=selected_stock)])
            
            # Add Indicators
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], mode='lines', name='EMA 20', line=dict(color='orange', width=1)))
            fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], mode='lines', name='VWAP', line=dict(color='purple', width=1, dash='dot')))
            
            # Add Range Levels
            if range_high > 0:
                fig.add_hline(y=range_high, line_dash="dash", line_color="green", annotation_text="Buy Zone")
                fig.add_hline(y=range_low, line_dash="dash", line_color="red", annotation_text="SL Zone")

            fig.update_layout(title=f"{selected_stock} - Live 15m Chart", height=500, xaxis_rangeslider_visible=False, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

        # Refresh Rate
        t_sleep.sleep(60) # Updates every 1 minute

else:
    st.info("👈 Please Select Sector/Stock and check 'START LIVE SCANNER' in the sidebar.")
    
    # Static Guide when not running
    with st.expander("📚 Strategy Cheat Sheet (The 15-min Trend Sniper)"):
        st.markdown("""
        1. **Timeframe:** 15 Minutes.
        2. **Wait:** No trade before 10:00 AM.
        3. **Buy Condition:**
           - ✅ Price breaks 10:00 AM High.
           - ✅ RSI > 60.
           - ✅ Price > 20 EMA & VWAP.
           - ✅ Sector Trend is UP.
           - ✅ Candle Body > 50% (Strong Green).
        4. **Exit:** 1% Target or Day Low SL.
        5. **Cutoff:** No entry after 2:00 PM.
        """)