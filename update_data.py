import json
import datetime
import requests

# 1. 道氏結構碎形 (維持原樣，用來判斷趨勢 Higher High / Lower Low)
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

# 2. 100 天宏觀日線費氏大支撐
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

# 3. 動態網格買賣點追蹤
def calculate_grid_targets(current_price, fib_levels, decimals=2):
    fib_382 = fib_levels["fib_382"]
    fib_500 = fib_levels["fib_500"]
    fib_618 = fib_levels["fib_618"]
    macro_high = fib_levels["macro_high"]

    if current_price > fib_382: buy_target = fib_382
    elif current_price > fib_500: buy_target = fib_500
    elif current_price > fib_618: buy_target = fib_618
    else: buy_target = macro_high - ((macro_high - fib_618) / 0.618 * 0.786)

    if current_price < fib_618: sell_target = fib_500
    elif current_price < fib_500: sell_target = fib_382
    elif current_price < fib_382: sell_target = macro_high
    else: sell_target = macro_high * 1.05 

    return {
        "buy_target": round(buy_target, decimals),
        "sell_target": round(sell_target, decimals)
    }

# 🌟 4. 全新核心：Wyckoff VSA (量價分析引擎)
def analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels):
    if len(closes) < 20 or len(volumes) < 20:
        return "PHASE B", "資料不足，預設為區間震盪 (Phase B)。"

    # 計算 20 日均量
    vol_sma = sum(volumes[-20:]) / 20
    curr_vol = volumes[-1]
    
    # 價格動能與收盤位置 (K線型態)
    curr_close = closes[-1]
    curr_high = highs[-1]
    curr_low = lows[-1]
    prev_close = closes[-2]
    
    curr_spread = curr_high - curr_low if curr_high - curr_low > 0 else 0.001
    close_pos = (curr_close - curr_low) / curr_spread # 0 到 1 之間，大於 0.5 代表收在上半部

    # 量能判定
    is_high_vol = curr_vol > vol_sma * 1.2
    is_low_vol = curr_vol < vol_sma * 0.8

    # 取得費氏位階
    fib_382 = fib_levels["fib_382"]
    fib_618 = fib_levels["fib_618"]

    # --- VSA 量價邏輯判定 ---
    
    # 底部區：價格逼近或跌破 618 支撐
    if curr_low <= fib_618 * 1.015:
        if is_low_vol:
            return "PHASE C", "【無供應測試】(No Supply) 測試 618 支撐但成交量萎縮，賣壓枯竭，醞釀反轉。"
        elif is_high_vol and close_pos >= 0.5:
            return "PHASE C", "【彈簧洗盤】(Spring) 爆量下殺但收長下影線，主力於深水區強力承接停止量。"
        elif is_high_vol and close_pos < 0.5:
            return "PHASE A", "【恐慌拋售】(Selling Climax) 放量跌破 618，賣壓沉重，底部尚未確認。"
        else:
            return "PHASE C", "【邊界測試】位於 618 深水區防守測試中。"

    # 頂部區：價格逼近或突破 382 阻力
    elif curr_high >= fib_382 * 0.985:
        if curr_close > prev_close and is_high_vol and close_pos >= 0.5:
            return "PHASE D", "【展現強勢】(SOS) 放量突破 382，需求強勁且收盤飽滿，啟動主升段。"
        elif curr_close > prev_close and is_low_vol:
            return "PHASE B", "【需求不足】(No Demand) 逼近壓力區但量能萎縮，追價意願低，提防假突破。"
        elif is_high_vol and close_pos <= 0.4 and curr_close < prev_close:
            return "PHASE B", "【上衝回落】(Upthrust) 挑戰前高爆量且留長上影線，遭遇主力派發供應。"
        else:
            return "PHASE D", "【頂部突破】挑戰上方強壓區，關注量能是否延續。"

    # 通道中段：價格在 382 ~ 618 之間
    else:
        if curr_close < prev_close and is_low_vol:
            return "PHASE C", "【二次測試】(Secondary Test) 區間內回調且縮量，主力測試下方浮動籌碼。"
        elif curr_close > prev_close and is_high_vol:
            return "PHASE D", "【標記躍升】(Minor SOS) 區間內放量上攻，買盤積極換手。"
        else:
            return "PHASE B", "【區間震盪】(Building Cause) 於黃金區間內縮量換手，籌碼沉澱中。"


def analyze_crypto_symbol(symbol_binance, coingecko_id):
    current_price = 0.0
    highs, lows, closes, volumes = [], [], [], []
    limit_days = 100 

    # 優先從 Binance 獲取精準 OHLCV (含成交量)
    try:
        bn_url = f"https://api.binance.com/api/v3/klines?symbol={symbol_binance}&interval=1d&limit={limit_days}"
        res = requests.get(bn_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
        if isinstance(res, list) and len(res) >= 20:
            closes = [float(k[4]) for k in res]
            highs = [float(k[2]) for k in res]
            lows = [float(k[3]) for k in res]
            volumes = [float(k[5]) for k in res] # K線第6個參數是 Volume
            current_price = closes[-1]
    except Exception as e:
        print(f"Binance error {symbol_binance}: {e}")

    # Fallback 到 CoinGecko
    if current_price == 0.0:
        try:
            cg_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency=usd&days={limit_days}&interval=daily"
            res = requests.get(cg_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
            p_data = res.get('prices', [])
            v_data = res.get('total_volumes', [])
            if len(p_data) >= 20:
                min_len = min(len(p_data), len(v_data))
                closes = [p[1] for p in p_data[-min_len:]]
                volumes = [v[1] for v in v_data[-min_len:]]
                highs = [p * 1.025 for p in closes]
                lows = [p * 0.975 for p in closes]
                current_price = closes[-1]
        except Exception as e:
            print(f"CoinGecko error {coingecko_id}: {e}")

    # Fallback 本地
    if current_price == 0.0:
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                old = json.load(f)
                key = symbol_binance[:3].lower()
                current_price = float(old[key]["price"])
                closes, highs, lows, volumes = [current_price]*30, [current_price*1.02]*30, [current_price*0.98]*30, [1000]*30
        except Exception:
            current_price = 1.0
            closes, highs, lows, volumes = [1.0]*30, [1.02]*30, [0.98]*30, [1000]*30

    decimals = 3 if current_price < 50 else 2
    
    # 費氏與網格
    fib_levels = calculate_fibonacci_levels(highs, lows, decimals)
    swing_plan = calculate_grid_targets(current_price, fib_levels, decimals)

    # 威科夫 VSA 量價引擎
    wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels)

    # 道氏趨勢判斷 (近期 45 天碎形)
    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    overhead = [h for h in swing_highs if h > current_price]
    resistance = min(overhead) if overhead else (current_price + atr * 1.618)
    underlying = [l for l in swing_lows if l < current_price]
    support = max(underlying) if underlying else (current_price - atr * 1.618)

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1] >= swing_highs[-2] and swing_lows[-1] >= swing_lows[-2]:
            dow_status, dow_signal = "Bullish", "多頭推進 (Higher High + Higher Low)"
        elif swing_highs[-1] <= swing_highs[-2] and swing_lows[-1] <= swing_lows[-2]:
            dow_status, dow_signal = "Bearish", "空頭受阻 (Lower High + Lower Low)"
        else:
            dow_status, dow_signal = "Neutral", "結構收斂 / 區間震盪"
    else:
        dow_status, dow_signal = ("Bullish", "趨勢延續中") if current_price >= recent_closes[0] else ("Neutral", "趨勢延續中")

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
    highs, lows, closes, volumes = [], [], [], []
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
            volumes = [float(k[5]) for k in candles]
            if current_price == 0.0 and closes: current_price = closes[-1]
    except Exception as e:
        print(f"OKX XMSTR klines error: {e}")

    if current_price == 0.0 or not volumes:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/MSTR?interval=1d&range={limit_days}d"
            res = requests.get(url, headers=headers, timeout=6).json()
            quotes = res['chart']['result'][0]['indicators']['quote'][0]
            valid = [(c, h, l, v) for c, h, l, v in zip(quotes['close'], quotes['high'], quotes['low'], quotes['volume']) if None not in (c, h, l, v)]
            if valid:
                closes, highs, lows, volumes = [x[0] for x in valid], [x[1] for x in valid], [x[2] for x in valid], [x[3] for x in valid]
                if current_price == 0.0: current_price = closes[-1]
        except Exception as e:
            print(f"Yahoo fallback error: {e}")

    if not closes or len(closes) < 20:
        if current_price == 0.0: current_price = 150.0
        closes = [current_price * (1 + 0.005 * (i - 15)) for i in range(30)]
        highs, lows, volumes = [c * 1.02 for c in closes], [c * 0.98 for c in closes], [1000000]*30

    fib_levels = calculate_fibonacci_levels(highs, lows, 2)
    swing_plan = calculate_grid_targets(current_price, fib_levels, 2)
    wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels)

    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    overhead = [h for h in swing_highs if h > current_price]
    resistance = min(overhead) if overhead else (current_price + atr * 1.618)
    underlying = [l for l in swing_lows if l < current_price]
    support = max(underlying) if underlying else (current_price - atr * 1.618)

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1] >= swing_highs[-2] and swing_lows[-1] >= swing_lows[-2]:
            dow_status, dow_signal = "Bullish", "多頭推進 (Higher High + Higher Low)"
        elif swing_highs[-1] <= swing_highs[-2] and swing_lows[-1] <= swing_lows[-2]:
            dow_status, dow_signal = "Bearish", "空頭受阻 (Lower High + Lower Low)"
        else:
            dow_status, dow_signal = "Neutral", "結構收斂 / 區間震盪"
    else:
        dow_status, dow_signal = ("Bullish", "趨勢延續中") if current_price >= recent_closes[0] else ("Neutral", "趨勢延續中")

    official_base_btc, official_base_stock, official_base_mnav = 81240.0, 153.92, 1.21
    stock_ratio = current_price / official_base_stock
    btc_ratio = btc_price / official_base_btc if btc_price > 0 else 1.0
    mnav_multiple = round(official_base_mnav * (stock_ratio / btc_ratio), 2)

    return {
        "price": round(current_price, 2),
        "mnav_multiple": mnav_multiple,
        "btc_holdings": 845050,
        "dow_status": dow_status,
        "dow_signal": dow_signal,
        "support": round(support, 2),
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
    print("Data.json updated successfully with VSA Wyckoff.")

if __name__ == "__main__":
    main()
