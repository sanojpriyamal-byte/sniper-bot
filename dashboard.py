import streamlit as st
import ccxt
import pandas as pd
import time

# ==========================================
# PAGE SETUP
# ==========================================
st.set_page_config(page_title="Sniper Bot Dashboard", page_icon="🚀", layout="wide")
st.title("🚀 Pro Sniper Dashboard & Bot Control")
st.markdown("Dashboard එකෙන්ම Bot ව ON/OFF කරන්න සහ Live Trades බලන්න.")
st.divider()

# ==========================================
# SIDEBAR SETTINGS
# ==========================================
st.sidebar.header("⚙️ Settings")
api_key = st.sidebar.text_input("Binance API Key", type="password")
secret_key = st.sidebar.text_input("Binance Secret Key", type="password")

# TELEGRAM (Optional - Ona nam danna, nathnam hisව තියන්න)
telegram_token = st.sidebar.text_input("Telegram Token (Optional)", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID (Optional)")

# 🤖 ON / OFF TOGGLE BUTTON EKA!
bot_active = st.sidebar.toggle("🤖 RUN AUTO-TRADING BOT", value=False)

symbols = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT', 'LTC/USDT'
]
timeframe = '5m'

# ==========================================
# MATH FUNCTIONS
# ==========================================
def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_bbands(df, period=20, std_dev=2.0): # 2.0 kara entries wadi wenna
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    return sma - (std * std_dev), sma + (std * std_dev)

def calculate_ema(df, period=200):
    return df['close'].ewm(span=period, adjust=False).mean()

def calculate_macd(df, fast=12, slow=26, signal=9):
    exp1 = df['close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def send_tg(msg):
    if telegram_token and telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            requests.post(url, json={"chat_id": telegram_chat_id, "text": msg, "parse_mode": "Markdown"})
        except: pass

# ==========================================
# MAIN EXECUTION
# ==========================================
if api_key and secret_key:
    exchange = ccxt.binance({
        'apiKey': api_key, 'secret': secret_key,
        'enableRateLimit': True, 'options': {'defaultType': 'spot'}
    })
    exchange.set_sandbox_mode(True)

    try:
        # 1. BALANCE SECTION
        balance = exchange.fetch_balance()
        usdt_bal = balance['USDT']['free']
        btc_bal = balance['BTC']['free']

        col1, col2, col3 = st.columns(3)
        col1.metric("USDT Balance", f"${usdt_bal:.2f}")
        col2.metric("BTC Balance", f"{btc_bal}")
        col3.metric("Bot Status", "🟢 ACTIVE & RUNNING" if bot_active else "🔴 STOPPED / MANUAL MODE")
        
        st.divider()

        # 2. BOT TRADING ENGINE (IF TOGGLED ON)
        if bot_active:
            st.subheader("🎯 Live Bot Log (Scanning...)")
            log_area = st.empty()
            log_text = f"[{time.ctime()}] 🛡️ Coins {len(symbols)} scan කරනවා...\n"

            for symbol in symbols:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe, limit=250)
                    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    close_price = df['close'].iloc[-1]
                    rsi = calculate_rsi(df).iloc[-1]
                    lower_bb, upper_bb = calculate_bbands(df)
                    ema_200 = calculate_ema(df, 200).iloc[-1]
                    macd_line, signal_line = calculate_macd(df)
                    
                    curr_macd = macd_line.iloc[-1]
                    curr_signal = signal_line.iloc[-1]

                    # Relaxed Buy Logic (RSI < 45, Bullish MACD)
                    if (close_price > ema_200) and (close_price < lower_bb.iloc[-1] or rsi < 45) and (curr_macd > curr_signal):
                        log_text += f" Found Signal on {symbol}! Buying...\n"
                        amount = round(50 / close_price, 4)
                        buy_order = exchange.create_market_buy_order(symbol, amount)
                        
                        tp = round(close_price * 1.02, 2)
                        sl = round(close_price * 0.99, 2)
                        time.sleep(1)
                        exchange.create_oco_order(symbol, 'sell', amount, tp, sl, sl)
                        
                        send_tg(f"🟢 *BUY ORDER EXECUTION*\n\nCoin: {symbol}\nPrice: ${close_price}\nTP: ${tp} | SL: ${sl}")
                        log_text += f"✅ Successfully Bought {symbol} & Set SL/TP!\n"
                except Exception as e:
                    pass
            
            log_area.text(log_text)
            st.divider()

        # 3. LIVE PRICES
        st.subheader("📈 Current Market Prices")
        tickers = exchange.fetch_tickers(symbols)
        price_data = [{"Coin": s, "Price (USDT)": f"${tickers[s]['last']:.4f}", "24h Change": f"{tickers[s]['percentage']}%"} for s in symbols]
        st.dataframe(pd.DataFrame(price_data), use_container_width=True)

        st.divider()

        # 4. RECENT TRADES
        st.subheader("📋 Bot Trade History (BTC/USDT)")
        trades = exchange.fetch_my_trades('BTC/USDT', limit=5)
        if len(trades) > 0:
            st.dataframe(pd.DataFrame([{
                'Time': t['datetime'], 'Type': "🟢 BUY" if t['side'] == 'buy' else "🔴 SELL",
                'Price': f"${t['price']}", 'Amount': t['amount'], 'Cost': f"${t['cost']}"
            } for t in trades]), use_container_width=True)
        else:
            st.info("No trades found.")

        # Auto rerun every 20 seconds to update dashboard & scan market
        time.sleep(20)
        st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.warning("👈 ඩැෂ්බෝඩ් එක ලෝඩ් වෙන්න වම් පැත්තේ Sidebar එකට oyage Binance API Keys දාන්න!")
