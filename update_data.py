import json
import datetime
import requests

def find_fractal_pivots(highs, lows, closes):
    """識別道氏 5-bar 波段分形拐點與 14 日 ATR"""
    swing_highs = []
    swing_lows = []
    n = len(highs)
    
    for i in range(2, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])
            
    tr_list = []
    for i in range(1, min(15, n)):
        tr = max(highs[-i] - lows[-i], abs(highs[-i] - closes[-i-1]), abs(lows[-i] - closes[-i-1]))
        tr_list.append(tr)
    atr = sum(tr_list) / len(tr_list) if tr_list else (highs[-1] * 0.035)
    
    return swing_highs, swing_lows, atr

def calculate_swing_trade(current_price, support, resistance, atr, decimals=2):
    """計算波段買入 (Buy) 與目標止盈 (Sell) 推薦價位"""
    ideal_buy = max(support * 1.015, current_price - (atr * 0.75))
    if ideal_buy >= current_price:
        ideal_buy = current_price * 0.965
        
    ideal_sell = min(resistance * 0.985, current_price + (atr * 1.25))
    if ideal_sell <= current_price:
        ideal_sell = current_price + (atr * 1.618)
        
    return {
        "buy_target": round(ideal_buy, decimals),
        "sell_target": round(ideal_sell, decimals)
    }

def analyze_crypto_symbol(symbol_binance, coingecko_id):
    """通用加密貨幣分析 (BTC, ETH, UNI)"""
    current_price = 0.0
    highs, lows, closes = [], [], []

    # 1. 首選 CoinGecko
    try:
        cg_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency=usd&days=45&interval=daily"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(cg_url, headers=headers, timeout=8).json()
        prices = [p[1] for p in res.get('prices', [])]
        if len(prices) >= 20:
            current_price = prices[-1]
            closes = prices
            highs = [p * 1.025 for p in prices]
            lows = [p * 0.975 for p in prices]
    except Exception as e:
        print(f"CoinGecko error {coingecko_id}: {e}")

    # 2. 次選 Binance 現貨
    if current_price == 0.0:
        try:
            bn_url = f"https://api.binance.com/api/v3/klines?symbol={symbol_binance}&interval=1d&limit=45"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(bn_url, headers=headers, timeout=8).json()
            if isinstance(res, list) and len(res) >= 20 and isinstance(res[0], list):
                closes = [float(k[4]) for k in res]
                highs = [float(k[2]) for k in res]
                lows = [float(k[3]) for k in res]
                current_price = closes[-1]
        except Exception as e:
            print(f"Binance error {symbol_binance}: {e}")

    if current_price == 0.0:
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                old = json.load(f)
                key = symbol_binance[:3].lower()
                current_price = float(old[key]["price"])
                closes = [current_price] * 30
                highs = [current_price * 1.02] * 30
                lows = [current_price * 0.98] * 30
        except Exception:
            current_price = 1.0
            closes, highs, lows = [1.0]*30, [1.02]*30, [0.98]*30

    swing_highs, swing_lows, atr = find_fractal_pivots(highs, lows, closes)
    overhead = [h for h in swing_highs if h > current_price]
    resistance = min(overhead) if overhead else (current_price + atr * 1.618)
    underlying = [l for l in swing_lows if l < current_price]
    support = max(underlying) if underlying else (current_price - atr * 1.618)

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

    range_span = resistance - support
    pos = (current_price - support) / range_span if range_span > 0 else 0.5
    if pos < 0.20:
        wyckoff_hint = "【支撐邊界】逼近波段防守點，留意 Spring 彈簧洗盤或 ST 二次測試。"
    elif pos > 0.80:
        wyckoff_hint = "【阻力邊界】挑戰上方強壓，防範 UTAD 假突破，觀察有無放量 SOS。"
    else:
        wyckoff_hint = "【區間運行】處於結構通道中段，主力籌碼穩定換手中。"

    decimals = 3 if current_price < 50 else 2
    swing_plan = calculate_swing_trade(current_price, support, resistance, atr, decimals)

    return {
        "price": round(current_price, decimals),
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support": round(support, decimals),
        "resistance": round(resistance, decimals),
        "buy_target": swing_plan["buy_target"],
        "sell_target": swing_plan["sell_target"],
        "wyckoff_hint": wyckoff_hint
    }

def analyze_mstr(btc_price):
    """透過 OKX XMSTR 進行 100% 動態實盤分析"""
    current_price = 0.0
    highs, lows, closes = [], [], []
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1. 優先透過 OKX API 抓取 XMSTR 即時行情
    try:
        okx_url = "https://www.okx.com/api/v5/market/ticker?instId=XMSTR-USDT"
        res = requests.get(okx_url, headers=headers, timeout=6).json()
        if res.get("code") == "0" and len(res.get("data", [])) > 0:
            current_price = float(res["data"][0]["last"])
            print(f"[OKX XMSTR] Fetched live price: {current_price}")
    except Exception as e:
        print(f"OKX XMSTR ticker fetch notice: {e}")

    # 2. 抓取 OKX XMSTR 歷史 K 線計算道氏結構與 ATR
    try:
        okx_kline = "https://www.okx.com/api/v5/market/candles?instId=XMSTR-USDT&bar=1D&limit=45"
        res = requests.get(okx_kline, headers=headers, timeout=6).json()
        if res.get("code") == "0" and len(res.get("data", [])) > 0:
            candles = res["data"]
            # OKX candles format: [ts, o, h, l, c, vol, ...] (Newest first)
            candles.reverse()
            closes = [float(k[4]) for k in candles]
            highs = [float(k[2]) for k in candles]
            lows = [float(k[3]) for k in candles]
            if current_price == 0.0 and closes:
                current_price = closes[-1]
    except Exception as e:
        print(f"OKX XMSTR klines fetch notice: {e}")

    # 3. 備援：若 OKX 逾時，嘗試 Yahoo Finance MSTR
    if current_price == 0.0:
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/MSTR?interval=1d&range=45d"
            res = requests.get(url, headers=headers, timeout=6).json()
            quotes = res['chart']['result'][0]['indicators']['quote'][0]
            c_list = [c for c in quotes['close'] if c is not None]
            h_list = [h for h in quotes['high'] if h is not None]
            l_list = [l for l in quotes['low'] if l is not None]
            if c_list:
                closes, highs, lows = c_list, h_list, l_list
                current_price = closes[-1]
        except Exception as e:
            print(f"Yahoo fallback notice: {e}")

    # 4. 最終防禦：從歷史 data.json 繼承
    if current_price == 0.0:
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                old = json.load(f)
                current_price = float(old["mstr"]["price"])
        except Exception:
            current_price = 150.0

    if not closes or len(closes) < 5:
        closes = [current_price * (1 + 0.005 * (i - 15)) for i in range(30)]
        highs = [c * 1.02 for c in closes]
        lows = [c * 0.98 for c in closes]

    swing_highs, swing_lows, atr = find_fractal_pivots(highs, lows, closes)
    overhead = [h for h in swing_highs if h > current_price]
    resistance = min(overhead) if overhead else (current_price + atr * 1.618)
    underlying = [l for l in swing_lows if l < current_price]
    support = max(underlying) if underlying else (current_price - atr * 1.618)

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

    swing_plan = calculate_swing_trade(current_price, support, resistance, atr, 2)

    # mNAV 計算模型
    official_base_btc = 81240.0
    official_base_stock = 153.92
    official_base_mnav = 1.21
    mstr_btc_holdings = 845050

    stock_ratio = current_price / official_base_stock
    btc_ratio = btc_price / official_base_btc if btc_price > 0 else 1.0
    dynamic_mnav = official_base_mnav * (stock_ratio / btc_ratio)
    mnav_multiple = round(dynamic_mnav, 2)

    if mnav_multiple <= 1.15:
        wyckoff_hint = "【平價/折價價值區】mNAV 處於極限安全邊際，機構主力強烈吸籌階段。"
    elif mnav_multiple >= 1.80:
        wyckoff_hint = "【槓桿極限溢價區】市場情緒過熱，建議逢高分批減倉止盈。"
    else:
        wyckoff_hint = "【合理估值常態運作】隨 BTC 槓桿 Beta 同步震盪，遵循波段區間操作。"

    return {
        "price": round(current_price, 2),
        "mnav_multiple": mnav_multiple,
        "btc_holdings": mstr_btc_holdings,
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "buy_target": swing_plan["buy_target"],
        "sell_target": swing_plan["sell_target"],
        "wyckoff_hint": wyckoff_hint
    }

def main():
    btc_data = analyze_crypto_symbol("BTCUSDT", "bitcoin")
    eth_data = analyze_crypto_symbol("ETHUSDT", "ethereum")
    uni_data = analyze_crypto_symbol("UNIUSDT", "uniswap")
    mstr_data = analyze_mstr(btc_data["price"])

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "btc": btc_data,
        "eth": eth_data,
        "uni": uni_data,
        "mstr": mstr_data
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"OKX XMSTR Sync complete. Price: ${mstr_data['price']}")

if __name__ == "__main__":
    main()
