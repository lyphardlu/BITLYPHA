import json
import datetime
import requests

def find_fractal_pivots(highs, lows, closes):
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

# 核心 1：計算 100 天宏觀日線費氏大支撐
def calculate_fibonacci_levels(highs, lows, decimals=2):
    if not highs or not lows:
        return {"macro_high": 0.0, "fib_382": 0.0, "fib_500": 0.0, "fib_618": 0.0}
    
    macro_high = max(highs)
    macro_low = min(lows)
    diff = macro_high - macro_low
    
    return {
        "macro_high": round(macro_high, decimals),
        "fib_382": round(macro_high - (diff * 0.382), decimals),
        "fib_500": round(macro_high - (diff * 0.500), decimals),
        "fib_618": round(macro_high - (diff * 0.618), decimals)
    }

# 核心 2：動態網格追蹤，根據目前價格自動切換買賣目標
def calculate_grid_targets(current_price, fib_levels, decimals=2):
    fib_382 = fib_levels["fib_382"]
    fib_500 = fib_levels["fib_500"]
    fib_618 = fib_levels["fib_618"]
    macro_high = fib_levels["macro_high"]

    # 決定買入目標：向下尋找最近的費氏支撐
    if current_price > fib_382:
        buy_target = fib_382
    elif current_price > fib_500:
        buy_target = fib_500
    elif current_price > fib_618:
        buy_target = fib_618
    else:
        # 跌破 618，向下預估更深的極限防守位 (786)
        buy_target = macro_high - ((macro_high - fib_618) / 0.618 * 0.786)

    # 決定止盈目標：向上尋找最近的費氏壓力或前高
    if current_price < fib_618:
        sell_target = fib_500
    elif current_price < fib_500:
        sell_target = fib_382
    elif current_price < fib_382:
        sell_target = macro_high
    else:
        sell_target = macro_high * 1.05 # 突破前高，往上看多 5% 延伸

    return {
        "buy_target": round(buy_target, decimals),
        "sell_target": round(sell_target, decimals)
    }

def analyze_crypto_symbol(symbol_binance, coingecko_id):
    current_price = 0.0
    highs, lows, closes = [], [], []
    limit_days = 100 # 拉長到 100 天抓取大波段

    try:
        cg_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency=usd&days={limit_days}&interval=daily"
        res = requests.get(cg_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
        prices = [p[1] for p in res.get('prices', [])]
        if len(prices) >= 20:
            current_price = prices[-1]
            closes = prices
            highs = [p * 1.025 for p in prices]
            lows = [p * 0.975 for p in prices]
    except Exception as e:
        print(f"CoinGecko error {coingecko_id}: {e}")

    if current_price == 0.0:
        try:
            bn_url = f"https://api.binance.com/api/v3/klines?symbol={symbol_binance}&interval=1d&limit={limit_days}"
            res = requests.get(bn_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
            if isinstance(res, list) and len(res) >= 20:
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
                closes = [current_price] * limit_days
                highs = [current_price * 1.02] * limit_days
                lows = [current_price * 0.98] * limit_days
        except Exception:
            current_price = 1.0
            closes, highs, lows = [1.0]*limit_days, [1.02]*limit_days, [0.98]*limit_days

    decimals = 3 if current_price < 50 else 2
    
    # 進行費氏回撤與網格買賣點計算
    fib_levels = calculate_fibonacci_levels(highs, lows, decimals)
    swing_plan = calculate_grid_targets(current_price, fib_levels, decimals)

    # 近期波段與威科夫指標保留最近 45 天來分析，不受百日干擾
    recent_highs = highs[-45:]
    recent_lows = lows[-45:]
    recent_closes = closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    
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
        dow_status = "Bullish" if current_price >= recent_closes[0] else "Neutral"

    range_span = resistance - support
    pos = (current_price - support) / range_span if range_span > 0 else 0.5

    if pos < 0.22:
        wyckoff_phase = "PHASE C"
        wyckoff_hint = "【支撐邊界】(試盤/洗盤階段)，逼近防守點，留意 Spring 彈簧洗盤或 ST 二次測試。"
    elif pos > 0.78:
        wyckoff_phase = "PHASE D"
        wyckoff_hint = "【阻力邊界】(突破/測試階段)，挑戰上方強壓，防範 UTAD 假突破。"
    else:
        wyckoff_phase = "PHASE B"
        wyckoff_hint = "【區間運行】(橫向築底/換手階段)，處於結構通道中段，主力籌碼穩定換手中。"

    return {
        "price": round(current_price, decimals),
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support": round(support, decimals),
        "resistance": round(resistance, decimals),
        "buy_target": swing_plan["buy_target"],
        "sell_target": swing_plan["sell_target"],
        "wyckoff_phase": wyckoff_phase,
        "wyckoff_hint": wyckoff_hint,
        "fib_382": fib_levels["fib_382"],
        "fib_500": fib_levels["fib_500"],
        "fib_618": fib_levels["fib_618"]
    }

def analyze_mstr(btc_price):
    current_price = 0.0
    highs, lows, closes = [], [], []
    headers = {"User-Agent": "Mozilla/5.0"}
    limit_days = 100

    try:
        okx_url = "https://www.okx.com/api/v5/market/ticker?instId=XMSTR-USDT"
        res = requests.get(okx_url, headers=headers, timeout=6).json()
        if res.get("code") == "0" and len(res.get("data", [])) > 0:
            current_price = float(res["data"][0]["last"])
    except Exception as e:
        print(f"OKX XMSTR ticker error: {e}")

    try:
        okx_kline = f"https://www.okx.com/api/v5/market/candles?instId=XMSTR-USDT&bar=1D&limit={limit_days}"
        res = requests.get(okx_kline, headers=headers, timeout=6).json()
        if res.get("code") == "0" and len(res.get("data", [])) > 0:
            candles = res["data"]
            candles.reverse()
            closes = [float(k[4]) for k in candles]
            highs = [float(k[2]) for k in candles]
            lows = [float(k[3]) for k in candles]
            if current_price == 0.0 and closes:
                current_price = closes[-1]
    except Exception as e:
        print(f"OKX XMSTR klines error: {e}")

    if current_price == 0.0:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/MSTR?interval=1d&range={limit_days}d"
            res = requests.get(url, headers=headers, timeout=6).json()
            quotes = res['chart']['result'][0]['indicators']['quote'][0]
            c_list = [c for c in quotes['close'] if c is not None]
            h_list = [h for h in quotes['high'] if h is not None]
            l_list = [l for l in quotes['low'] if l is not None]
            if c_list:
                closes, highs, lows = c_list, h_list, l_list
                current_price = closes[-1]
        except Exception as e:
            print(f"Yahoo fallback error: {e}")

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

    # 進行費氏回撤與網格買賣點計算
    fib_levels = calculate_fibonacci_levels(highs, lows, 2)
    swing_plan = calculate_grid_targets(current_price, fib_levels, 2)

    recent_highs = highs[-45:]
    recent_lows = lows[-45:]
    recent_closes = closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    
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
        dow_status = "Bullish" if current_price >= recent_closes[0] else "Neutral"

    range_span = resistance - support
    pos = (current_price - support) / range_span if range_span > 0 else 0.5

    official_base_btc = 81240.0
    official_base_stock = 153.92
    official_base_mnav = 1.21
    mstr_btc_holdings = 845050

    stock_ratio = current_price / official_base_stock
    btc_ratio = btc_price / official_base_btc if btc_price > 0 else 1.0
    dynamic_mnav = official_base_mnav * (stock_ratio / btc_ratio)
    mnav_multiple = round(dynamic_mnav, 2)

    if pos < 0.22:
        wyckoff_phase = "PHASE C"
        wyckoff_hint = "【支撐邊界】(試盤/洗盤階段)，mNAV 處於安全邊際，留意強力支撐。"
    elif pos > 0.78:
        wyckoff_phase = "PHASE D"
        wyckoff_hint = "【阻力邊界】(突破/測試階段)，溢價過熱，防範假突破。"
    else:
        wyckoff_phase = "PHASE B"
        wyckoff_hint = "【通道中段】(橫向換手階段)，隨 BTC 槓桿 Beta 同步震盪。"

    return {
        "price": round(current_price, 2),
        "mnav_multiple": mnav_multiple,
        "btc_holdings": mstr_btc_holdings,
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support": round(support, 2),
        # 修正的這行在這裡：
        "resistance": round(resistance, 2), 
        "buy_target": swing_plan["buy_target"],
        "sell_target": swing_plan["sell_target"],
        "wyckoff_phase": wyckoff_phase,
        "wyckoff_hint": wyckoff_hint,
        "fib_382": fib_levels["fib_382"],
        "fib_500": fib_levels["fib_500"],
        "fib_618": fib_levels["fib_618"]
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
    print("Data.json updated successfully with 1D Fibonacci levels.")

if __name__ == "__main__":
    main()
