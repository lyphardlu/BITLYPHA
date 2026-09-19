import json
import datetime
import requests
import yfinance as yf

def get_mstr_mnav(btc_price):
    """計算 MSTR mNAV 溢價倍數"""
    try:
        mstr = yf.Ticker("MSTR")
        info = mstr.info
        share_price = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)
        shares_outstanding = info.get("sharesOutstanding", 0)
        total_debt = info.get("totalDebt", 0)
        total_cash = info.get("totalCash", 0)
        
        market_cap = share_price * shares_outstanding
        enterprise_value = market_cap + total_debt - total_cash
        
        # MSTR 持倉 BTC 基準量 (依官方公告動態調整)
        mstr_btc_holdings = 500000 
        btc_nav = mstr_btc_holdings * btc_price
        
        mnav_multiple = enterprise_value / btc_nav if btc_nav > 0 else 0
        return {
            "mstr_price": round(share_price, 2),
            "market_cap_b": round(market_cap / 1e9, 2),
            "mnav_multiple": round(mnav_multiple, 2),
            "btc_holdings": mstr_btc_holdings
        }
    except Exception as e:
        print(f"Error fetching MSTR data: {e}")
        return {"mstr_price": 0, "market_cap_b": 0, "mnav_multiple": 1.5, "btc_holdings": 500000}

def analyze_btc_market():
    """抓取 BTC 日 K 線並以道氏理論分析"""
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=30"
    res = requests.get(url).json()
    
    closes = [float(k[4]) for k in res]
    highs = [float(k[2]) for k in res]
    lows = [float(k[3]) for k in res]
    
    current_price = closes[-1]
    
    # 道氏理論高低點對比 (近 14 天 vs 前 14 天)
    prev_high = max(highs[:15])
    recent_high = max(highs[15:])
    prev_low = min(lows[:15])
    recent_low = min(lows[15:])
    
    if recent_high > prev_high and recent_low > prev_low:
        dow_signal = "多頭格局 (Higher High + Higher Low)"
        dow_status = "Bullish"
    elif recent_high < prev_high and recent_low < prev_low:
        dow_signal = "空頭結構 (Lower High + Lower Low)"
        dow_status = "Bearish"
    else:
        dow_signal = "區間震盪 / 轉折收斂中"
        dow_status = "Neutral"
        
    return current_price, {
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support_level": round(recent_low, 2),
        "resistance_level": round(recent_high, 2)
    }

def main():
    btc_price, dow_data = analyze_btc_market()
    mstr_data = get_mstr_mnav(btc_price)
    
    range_span = dow_data["resistance_level"] - dow_data["support_level"]
    pos = (btc_price - dow_data["support_level"]) / range_span if range_span > 0 else 0.5
    
    # 威科夫區間邊界量價判定
    if pos < 0.15:
        wyckoff_hint = "【Phase C / 支撐測試】價格貼近區間底部，重點觀察是否出現 Spring（彈簧洗盤）或縮量二次測試（ST）。"
    elif pos > 0.85:
        wyckoff_hint = "【Phase C-D / 壓力邊界】價格觸及區間上軌，警惕 UTAD（誘多假突破）或確認是否有爆量強勢突破（SOS）。"
    else:
        wyckoff_hint = "【Phase B / 籌碼換手】處於 TR（交易區間）核心洗盤帶，主力資金持續多空拉鋸，嚴禁追高殺跌，耐心等待邊緣訊號。"

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "btc_price": round(btc_price, 2),
        "mstr": mstr_data,
        "dow": dow_data,
        "wyckoff": {
            "current_phase_hint": wyckoff_hint
        }
    }
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("data.json generated successfully.")

if __name__ == "__main__":
    main()
