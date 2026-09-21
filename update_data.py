import requests
import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

# ==========================================
# 1. 基礎設定與交易對
# ==========================================
SYMBOLS = {
    'btc': 'BTCUSDT',
    'eth': 'ETHUSDT',
    'ethbtc': 'ETHBTC',
    'sol': 'SOLUSDT',
    'uni': 'UNIUSDT'
}

# ==========================================
# 2. 核心量化演算法
# ==========================================
def calculate_rsi(series, period=14):
    """計算 RSI 相對強弱指標"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_dynamic_targets(high, low, current_price, rsi, ma20, ma50):
    """
    動態波段買賣點演算法：
    根據趨勢強度 (RSI, MA20, MA50) 動態調整買入與止盈位階
    """
    diff = high - low
    fib_236 = high - (diff * 0.236)
    fib_382 = high - (diff * 0.382)
    fib_500 = high - (diff * 0.500)
    fib_618 = high - (diff * 0.618)
    
    # [狀態 A] 極強勢狂暴多頭
    if current_price > ma20 and rsi > 65:
        buy_target = max(fib_236, ma20)  # 回踩極淺，買在 0.236 或 MA20
        sell_target = high + (diff * 0.272) # 預期突破前高，看到 1.272 擴展
        dow = "Bullish"
        phase = "PHASE E"
        hint = "🔥【強力買進】狂暴多頭，沿 MA20 或 0.236 淺回踩即接盤。"
        
    # [狀態 B] 穩健多頭趨勢
    elif current_price > ma50:
        buy_target = (fib_382 + fib_500) / 2 # 標準黃金坑買入
        sell_target = high # 保守止盈抓前高
        dow = "Bullish"
        phase = "PHASE D"
        hint = "🚀【穩健偏多】多頭趨勢延續，等待 0.382-0.5 黃金坑機會。"
        
    # [狀態 C] 大區間震盪洗盤
    elif current_price < ma50 and current_price > fib_618:
        buy_target = fib_618 # 深掛 0.618 防守
        sell_target = fib_382 # 跌深反彈到 0.382 就跑
        dow = "Neutral"
        phase = "PHASE B"
        hint = "⚖️【合理區間】大區間洗盤，靠近 0.618 分批建倉防守。"
        
    # [狀態 D] 空頭走勢 / 恐慌拋售
    else:
        buy_target = low # 準備接彈簧洗盤
        sell_target = fib_500
        dow = "Bearish"
        phase = "PHASE A"
        hint = "⚠️【恐慌拋售】趨勢轉弱，等待底部彈簧洗盤 (Spring) 測試。"
        
    return buy_target, sell_target, dow, phase, hint, fib_236, fib_382, fib_500, fib_618

# ==========================================
# 3. 獲取並處理加密貨幣數據 (Binance)
# ==========================================
def process_crypto(symbol_key, symbol):
    # 抓取近 120 天的日線資料
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=120"
    res = requests.get(url)
    df = pd.DataFrame(res.json(), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    
    current_price = df['close'].iloc[-1]
    high_90 = df['high'].tail(90).max() # 取 90 天波段高點
    low_90 = df['low'].tail(90).min()   # 取 90 天波段低點
    
    # 計算指標
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['rsi'] = calculate_rsi(df['close'])
    
    ma20 = df['ma20'].iloc[-1]
    ma50 = df['ma50'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    
    # 取得動態點位與診斷
    buy_tgt, sell_tgt, dow, phase, hint, f236, f382, f500, f618 = calculate_dynamic_targets(high_90, low_90, current_price, rsi, ma20, ma50)
    
    # ETH/BTC 匯率保留 5 位小數，其餘保留 2 位
    decimals = 5 if symbol_key == 'ethbtc' else 2
    
    return {
        "price": round(current_price, decimals),
        "buy_target": round(buy_tgt, decimals),
        "sell_target": round(sell_tgt, decimals),
        "dow_status": dow,
        "wyckoff_phase": phase,
        "wyckoff_hint": hint,
        "fib_236": round(f236, decimals),
        "fib_382": round(f382, decimals),
        "fib_500": round(f500, decimals),
        "fib_618": round(f618, decimals)
    }

# ==========================================
# 4. 獲取並處理美股 MSTR 數據 (Yahoo Finance)
# ==========================================
def process_mstr():
    # 使用 yfinance 抓取 MSTR 日線資料
    mstr = yf.Ticker("MSTR")
    hist = mstr.history(period="6mo")
    
    current_price = hist['Close'].iloc[-1]
    high_90 = hist['High'].tail(90).max()
    low_90 = hist['Low'].tail(90).min()
    
    hist['ma20'] = hist['Close'].rolling(20).mean()
    hist['ma50'] = hist['Close'].rolling(50).mean()
    hist['rsi'] = calculate_rsi(hist['Close'])
    
    ma20 = hist['ma20'].iloc[-1]
    ma50 = hist['ma50'].iloc[-1]
    rsi = hist['rsi'].iloc[-1]
    
    buy_tgt, sell_tgt, dow, phase, hint, f236, f382, f500, f618 = calculate_dynamic_targets(high_90, low_90, current_price, rsi, ma20, ma50)
    
    # 針對 MSTR 的特殊標籤覆蓋
    if dow == "Bullish" and rsi > 65:
        phase = "PREMIUM"
        hint = "🔥【溢價買進】帶槓桿之王，強勢貼 MA20 買進，注意高位溢價風險。"
    elif dow == "Bullish":
        phase = "FAIR VALUE"
        hint = "⚖️【合理區間】跟隨大盤多頭，可於 0.382-0.5 區間接回。"
    else:
        phase = "DISCOUNT"
        hint = "🚀【極度低估】跌破合理價位，注意 0.618 強力防守與彈簧洗盤機會。"

    # 動態模擬 mNAV 溢價倍數 (RSI 越高，市場給予的溢價通常越高)
    mnav_multiple = round(1.2 + (rsi / 100) * 0.8, 2)

    return {
        "price": round(current_price, 2),
        "buy_target": round(buy_tgt, 2),
        "sell_target": round(sell_tgt, 2),
        "dow_status": dow,
        "wyckoff_phase": phase,
        "wyckoff_hint": hint,
        "mnav_multiple": f"{mnav_multiple}x",
        "fib_236": round(f236, 2),
        "fib_382": round(f382, 2),
        "fib_500": round(f500, 2),
        "fib_618": round(f618, 2)
    }

# ==========================================
# 5. 主程式執行與檔案輸出
# ==========================================
def main():
    print("🚀 BITLYPHA Terminal - Starting Macro-Swing Data Sync...")
    
    output = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    }
    
    # 執行 Crypto 爬蟲
    for key, symbol in SYMBOLS.items():
        try:
            print(f"[*] Processing {symbol}...")
            output[key] = process_crypto(key, symbol)
        except Exception as e:
            print(f"[!] Error processing {symbol}: {e}")
            
    # 執行 美股 MSTR 爬蟲
    try:
        print("[*] Processing MSTR...")
        output['mstr'] = process_mstr()
    except Exception as e:
        print(f"[!] Error processing MSTR: {e}")
        
    # 輸出為 JSON 給前端
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
        
    print("✅ data.json has been updated successfully!")

if __name__ == "__main__":
    main()
