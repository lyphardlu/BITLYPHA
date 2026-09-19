import json
import datetime
import requests

def get_mstr_mnav(btc_price):
    """計算 MSTR mNAV 倍數"""
    share_price = 0.0
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/MSTR"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10).json()
        share_price = float(res['chart']['result'][0]['meta']['regularMarketPrice'])
    except Exception as e:
        print(f"Yahoo Finance failed: {e}")
        share_price = 330.0  # 基準參考估值

    # 參數設定
    shares_outstanding = 245000000
    total_debt = 4250000000
    total_cash = 50000000
    mstr_btc_holdings = 500000

    market_cap = share_price * shares_outstanding
    enterprise_value = market_cap + total_debt - total_cash
    btc_nav = mstr_btc_holdings * btc_price
    
    mnav_multiple = enterprise_value / btc_nav if btc_nav > 0 else 1.8
    return {
        "mstr_price": round(share_price, 2),
        "market_cap_b": round(market_cap / 1e9, 2),
        "mnav_multiple": round(mnav_multiple, 2),
        "btc_holdings": mstr_btc_holdings
    }

def analyze_btc_market():
    """多源抓取 BTC 數據並進行道氏分析"""
    current_price = 0.0
    highs, lows = [], []

    # 1. 首選嘗試 Binance API
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=30"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10).json()
        if isinstance(res, list) and len(res) >= 15 and isinstance(res[0], list):
            closes = [float(k[4]) for k in res]
            highs = [float(k[2]) for k in res]
            lows = [float(k[3]) for k in res]
            current_price = closes[-1]
    except Exception as e:
        print(f"Binance API fallback: {e}")

    # 2. 次選嘗試 CoinGecko API（若 Binance 失敗）
    if current_price == 0.0:
        try:
            cg_url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=30&interval=daily"
            cg_res = requests.get(cg_url, timeout=10).json()
            prices = [p[1] for p in cg_res.get('prices', [])]
            if len(prices) >= 15:
                current_price = prices[-1]
                highs = prices
                lows = prices
        except Exception as e:
            print(f"CoinGecko fallback: {e}")

    # 3. 兜底基準防線（防止任何網路封鎖）
    if current_price == 0.0:
        current_price = 84000.0
        highs = [86000.0] * 30
        lows = [81000.0] * 30

    # 道氏理論判定
    half = len(highs) // 2
    prev_high = max(highs[:half])
    recent_high = max(highs[half:])
    prev_low = min(lows[:half])
    recent_low = min(lows[half:])

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
    print("data.json updated successfully.")

if __name__ == "__main__":
    main()
