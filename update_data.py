import json
import datetime
import requests

def get_mstr_mnav(btc_price):
    """計算 MSTR mNAV 溢價倍數"""
    share_price = 0.0
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/MSTR"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10).json()
        share_price = float(res['chart']['result'][0]['meta']['regularMarketPrice'])
    except Exception as e:
        print(f"Yahoo Finance failed: {e}")
        share_price = 330.0

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

def find_fractal_pivots(highs, lows, closes):
    """
    識別道氏波段分形拐點 (5-bar Fractal Pivot)
    中間 K 線高於/低於前後各 2 根
    """
    swing_highs = []
    swing_lows = []
    n = len(highs)
    
    for i in range(2, n - 2):
        # Swing High (有效高點拐點)
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
        # Swing Low (有效低點拐點)
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])
            
    # 計算 14 日 ATR (平均真實波幅) 作為動態擴展緩衝
    tr_list = []
    for i in range(1, min(15, n)):
        tr = max(highs[-i] - lows[-i], abs(highs[-i] - closes[-i-1]), abs(lows[-i] - closes[-i-1]))
        tr_list.append(tr)
    atr = sum(tr_list) / len(tr_list) if tr_list else (highs[-1] * 0.03)
    
    return swing_highs, swing_lows, atr

def analyze_btc_market():
    """抓取 60 日數據並以波段分形 + 道氏結構進行高階分析"""
    current_price = 0.0
    highs, lows, closes = [], [], []

    # 1. 嘗試 Binance 日 K (拉取 60 根以確認有效結構)
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=60"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10).json()
        if isinstance(res, list) and len(res) >= 30 and isinstance(res[0], list):
            closes = [float(k[4]) for k in res]
            highs = [float(k[2]) for k in res]
            lows = [float(k[3]) for k in res]
            current_price = closes[-1]
    except Exception as e:
        print(f"Binance fallback: {e}")

    # 2. 次選 CoinGecko 備援
    if current_price == 0.0:
        try:
            cg_url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=60&interval=daily"
            cg_res = requests.get(cg_url, timeout=10).json()
            prices = [p[1] for p in cg_res.get('prices', [])]
            if len(prices) >= 30:
                current_price = prices[-1]
                closes = prices
                highs = [p * 1.015 for p in prices]
                lows = [p * 0.985 for p in prices]
        except Exception as e:
            print(f"CoinGecko fallback: {e}")

    # 3. 兜底基準
    if current_price == 0.0:
        current_price = 81300.0
        closes = [80000.0] * 60
        highs = [82000.0] * 60
        lows = [78000.0] * 60

    # 提取分形拐點
    swing_highs, swing_lows, atr = find_fractal_pivots(highs, lows, closes)
    
    # 尋找現價上方的有效阻力（若無則以 ATR 向上動態投影目標）
    overhead_resistances = [h for h in swing_highs if h > current_price]
    if overhead_resistances:
        resistance_level = min(overhead_resistances)  # 最近的上方波段強阻
    else:
        # 突破波段新高階段：以 ATR 1.618 擴展目標作為動態阻力
        resistance_level = current_price + (atr * 1.618)

    # 尋找現價下方的有效支撐（最近的波段防守 HL）
    underlying_supports = [l for l in swing_lows if l < current_price]
    if underlying_supports:
        support_level = max(underlying_supports)      # 最近的下方波段防守點
    else:
        support_level = current_price - (atr * 1.618)

    # 道氏結構判斷：檢視最近兩組波段拐點
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1] >= swing_highs[-2] and swing_lows[-1] >= swing_lows[-2]:
            dow_signal = "多頭推進 (Higher High + Higher Low)"
            dow_status = "Bullish"
        elif swing_highs[-1] <= swing_highs[-2] and swing_lows[-1] <= swing_lows[-2]:
            dow_signal = "空頭受阻 (Lower High + Lower Low)"
            dow_status = "Bearish"
        else:
            dow_signal = "結構收斂 / 區間震盪整理"
            dow_status = "Neutral"
    else:
        dow_signal = "趨勢維持中"
        dow_status = "Bullish" if current_price > (closes[-15] if len(closes) >= 15 else current_price) else "Neutral"

    return current_price, {
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support_level": round(support_level, 2),
        "resistance_level": round(resistance_level, 2),
        "atr_val": round(atr, 2)
    }

def main():
    btc_price, dow_data = analyze_btc_market()
    mstr_data = get_mstr_mnav(btc_price)

    sup = dow_data["support_level"]
    res_lvl = dow_data["resistance_level"]
    range_span = res_lvl - sup
    pos = (btc_price - sup) / range_span if range_span > 0 else 0.5

    if pos < 0.18:
        wyckoff_hint = "【Phase C / 支撐測試】價格回踩至前期有效波段低點（HL），觀察縮量二次測試或彈簧洗盤（Spring）。"
    elif pos > 0.82:
        wyckoff_hint = "【Phase D / 突破壓力】價格逼近上方有效波段阻力，觀察是否爆量確認 SOS（強勢出現）或 UTAD（假突破誘多）。"
    else:
        wyckoff_hint = f"【Phase B / 趨勢維持】處於波段通道內（支撐 ${int(sup):,} / 阻力 ${int(res_lvl):,}），主力結構穩定換手中。"

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
    print("data.json updated with fractal pivot model.")

if __name__ == "__main__":
    main()
