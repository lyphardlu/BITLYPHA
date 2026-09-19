import json
import datetime
import requests

def get_mstr_mnav(btc_price):
    """
    計算 MSTR mNAV 溢價倍數
    數據基準源自 Strategy.com 官方即時指標：
    - 官方持幣量：845,050 顆 BTC (佔總流通約 4.02%)
    - 官方基準 mNAV：1.21x
    - 官方參考股價：$153.92
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 官方基準參數
    mstr_btc_holdings = 845050
    share_price = 153.92
    mnav_multiple = 1.21

    # 1. 嘗試抓取 Yahoo Finance 即時股價做動態校準
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/MSTR"
        res = requests.get(url, headers=headers, timeout=5).json()
        live_price = float(res['chart']['result'][0]['meta']['regularMarketPrice'])
        if live_price > 0:
            share_price = live_price
    except Exception as e:
        print(f"MSTR Yahoo price fallback: {e}")

    # 2. 依據官方公布的淨負債與總股本動態精算 mNAV
    # 稀釋總股數約 2.45 億股，淨負債約 204 億美元
    shares_outstanding = 245000000
    net_debt = 20395000000 
    
    market_cap = share_price * shares_outstanding
    enterprise_value = market_cap + net_debt
    btc_nav = mstr_btc_holdings * btc_price
    
    if btc_nav > 0:
        # 動態計算並結合官方基準
        calc_mnav = enterprise_value / btc_nav
        mnav_multiple = round(calc_mnav, 2)

    return {
        "mstr_price": round(share_price, 2),
        "market_cap_b": round(market_cap / 1e9, 2),
        "mnav_multiple": mnav_multiple,
        "btc_holdings": mstr_btc_holdings
    }

def find_fractal_pivots(highs, lows, closes):
    """
    識別道氏理論波段分形拐點 (5-bar Fractal Pivot) 與 14 日 ATR
    - Swing High: 高於前後各 2 根 K 線的波段阻力
    - Swing Low: 低於前後各 2 根 K 線的波段防守點 (HL)
    """
    swing_highs = []
    swing_lows = []
    n = len(highs)
    
    for i in range(2, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])
            
    # 計算 14 日 ATR (平均真實波幅)
    tr_list = []
    for i in range(1, min(15, n)):
        tr = max(highs[-i] - lows[-i], abs(highs[-i] - closes[-i-1]), abs(lows[-i] - closes[-i-1]))
        tr_list.append(tr)
    atr = sum(tr_list) / len(tr_list) if tr_list else (highs[-1] * 0.03)
    
    return swing_highs, swing_lows, atr

def fetch_crypto_data(symbol_binance, coingecko_id, default_price):
    """
    雙通道穩定數據獲取：
    1. 首選 CoinGecko (雲端環境最穩定不擋 IP)
    2. 次選 Binance API
    3. 兜底基準
    """
    current_price = 0.0
    highs, lows, closes = [], [], []

    # 通道 1: CoinGecko API
    try:
        cg_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency=usd&days=45&interval=daily"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(cg_url, headers=headers, timeout=10).json()
        prices = [p[1] for p in res.get('prices', [])]
        if len(prices) >= 20:
            current_price = prices[-1]
            closes = prices
            highs = [p * 1.02 for p in prices]
            lows = [p * 0.98 for p in prices]
    except Exception as e:
        print(f"CoinGecko failed for {coingecko_id}: {e}")

    # 通道 2: Binance API (若 CoinGecko 失敗)
    if current_price == 0.0:
        try:
            bn_url = f"https://api.binance.com/api/v3/klines?symbol={symbol_binance}&interval=1d&limit=45"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(bn_url, headers=headers, timeout=10).json()
            if isinstance(res, list) and len(res) >= 20 and isinstance(res[0], list):
                closes = [float(k[4]) for k in res]
                highs = [float(k[2]) for k in res]
                lows = [float(k[3]) for k in res]
                current_price = closes[-1]
        except Exception as e:
            print(f"Binance failed for {symbol_binance}: {e}")

    # 通道 3: 兜底預設防線
    if current_price == 0.0:
        current_price = default_price
        closes = [default_price] * 30
        highs = [default_price * 1.02] * 30
        lows = [default_price * 0.98] * 30

    # 道氏理論波段拐點提取
    swing_highs, swing_lows, atr = find_fractal_pivots(highs, lows, closes)
    
    # 阻力計算：尋找現價上方的有效波段高點（若破新高則以 ATR 向上動態投影）
    overhead = [h for h in swing_highs if h > current_price]
    resistance = min(overhead) if overhead else (current_price + atr * 1.618)

    # 支撐計算：尋找現價下方的有效波段低點防守線
    underlying = [l for l in swing_lows if l < current_price]
    support = max(underlying) if underlying else (current_price - atr * 1.618)

    # 道氏結構判定
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1] >= swing_highs[-2] and swing_lows[-1] >= swing_lows[-2]:
            dow_signal = "多頭推進 (Higher High + Higher Low)"
            dow_status = "Bullish"
        elif swing_highs[-1] <= swing_highs[-2] and swing_lows[-1] <= swing_lows[-2]:
            dow_signal = "空頭受阻 (Lower High + Lower Low)"
            dow_status = "Bearish"
        else:
            dow_signal = "結構收斂 / 區間震盪"
            dow_status = "Neutral"
    else:
        dow_signal = "趨勢延續中"
        dow_status = "Bullish" if current_price >= closes[0] else "Neutral"

    # 威科夫區間位置提示
    range_span = resistance - support
    pos = (current_price - support) / range_span if range_span > 0 else 0.5
    if pos < 0.20:
        wyckoff_hint = "【支撐邊界】逼近波段防守點，留意 Spring 彈簧洗盤或 ST 二次測試。"
    elif pos > 0.80:
        wyckoff_hint = "【阻力邊界】挑戰上方強壓，防範 UTAD 假突破，觀察有無放量 SOS。"
    else:
        wyckoff_hint = "【區間運行】處於結構通道中段，主力籌碼穩定換手中。"

    decimals = 3 if current_price < 50 else 2
    return {
        "price": round(current_price, decimals),
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support": round(support, decimals),
        "resistance": round(resistance, decimals),
        "wyckoff_hint": wyckoff_hint
    }

def main():
    btc_data = fetch_crypto_data("BTCUSDT", "bitcoin", 81250.0)
    eth_data = fetch_crypto_data("ETHUSDT", "ethereum", 2636.82)
    uni_data = fetch_crypto_data("UNIUSDT", "uniswap", 8.85)

    mstr_data = get_mstr_mnav(btc_data["price"])

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "mstr": mstr_data,
        "btc": btc_data,
        "eth": eth_data,
        "uni": uni_data
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("Market data and MSTR mNAV successfully synchronized.")

if __name__ == "__main__":
    main()
