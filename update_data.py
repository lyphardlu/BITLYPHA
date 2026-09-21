import json
import datetime
import requests

def find_fractal_pivots(highs, lows, closes):
    swing_highs, swing_lows = [], []
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

def calculate_fibonacci_levels(highs, lows, decimals=2):
    if not highs or not lows: return {"macro_high": 0.0, "fib_236": 0.0, "fib_382": 0.0, "fib_500": 0.0, "fib_618": 0.0, "fib_786": 0.0}
    macro_high, macro_low = max(highs), min(lows)
    diff = macro_high - macro_low
    return {
        "macro_high": round(macro_high, decimals),
        "fib_236": round(macro_high - (diff * 0.236), decimals),
        "fib_382": round(macro_high - (diff * 0.382), decimals),
        "fib_500": round(macro_high - (diff * 0.500), decimals),
        "fib_618": round(macro_high - (diff * 0.618), decimals),
        "fib_786": round(macro_high - (diff * 0.786), decimals)
    }

def calculate_grid_targets(current_price, fib_levels, decimals=2):
    fib_382, fib_500, fib_618, macro_high = fib_levels["fib_382"], fib_levels["fib_500"], fib_levels["fib_618"], fib_levels["macro_high"]
    if current_price > fib_382: buy_target = fib_382
    elif current_price > fib_500: buy_target = fib_500
    elif current_price > fib_618: buy_target = fib_618
    else: buy_target = macro_high - ((macro_high - fib_618) / 0.618 * 0.786)

    if current_price < fib_618: sell_target = fib_500
    elif current_price < fib_500: sell_target = fib_382
    elif current_price < fib_382: sell_target = macro_high
    else: sell_target = macro_high * 1.05 
    return {"buy_target": buy_target, "sell_target": sell_target}

def analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels):
    if len(closes) < 20 or len(volumes) < 20: return "PHASE B", "資料不足，預設為區間震盪 (Phase B)。"
    vol_sma = sum(volumes[-20:]) / 20
    recent_3d_vol = sum(volumes[-3:]) / 3
    curr_close, prev_close = closes[-1], (closes[-4] if len(closes) >= 4 else closes[0])
    curr_high, curr_low = max(highs[-3:]), min(lows[-3:])   
    curr_spread = curr_high - curr_low if curr_high - curr_low > 0 else 0.001
    close_pos = (curr_close - curr_low) / curr_spread 
    is_high_vol, is_low_vol = recent_3d_vol > vol_sma * 1.2, recent_3d_vol < vol_sma * 0.8
    fib_382, fib_618 = fib_levels["fib_382"], fib_levels["fib_618"]
    
    if curr_low <= fib_618 * 1.015:
        if is_low_vol: return "PHASE C", "🔥【強力買進】無供應測試 (No Supply)：近三日量縮測底，賣壓枯竭，右側絕佳買點！"
        elif is_high_vol and close_pos >= 0.5: return "PHASE C", "🔥【強力買進】彈簧洗盤 (Spring)：爆量下殺但收盤強勢拉回，主力深水區強力吃貨！"
        elif is_high_vol and close_pos < 0.5: return "PHASE A", "【恐慌拋售】(Selling Climax) 近三日放量跌破 618，賣壓沉重，觀望勿接飛刀。"
        else: return "PHASE C", "【邊界測試】位於 618 深水區防守測試中，等待量能表態。"
    elif curr_high >= fib_382 * 0.985:
        if curr_close > prev_close and is_high_vol and close_pos >= 0.5: return "PHASE D", "【展現強勢】(SOS) 近三日放量突破 382 且收盤飽滿，需求強勁，主升段確認。"
        elif curr_close > prev_close and is_low_vol: return "PHASE B", "🛑【逃頂賣出】需求不足 (No Demand)：近三日無量過高，追買意願極度低迷，提防假突破！"
        elif is_high_vol and close_pos <= 0.4 and curr_close < prev_close: return "PHASE B", "🛑【逃頂賣出】上衝回落 (Upthrust)：近三日爆量挑戰前高卻留長上影線，主力趁機派發，高位危險！"
        else: return "PHASE D", "【頂部突破】挑戰上方強壓區，關注多頭量能是否持續堆積。"
    else:
        if curr_close < prev_close and is_low_vol: return "PHASE C", "【二次測試】(Secondary Test) 區間內回調且連續縮量，測試下方浮動籌碼。"
        elif curr_close > prev_close and is_high_vol: return "PHASE D", "【標記躍升】(Minor SOS) 區間內連續放量上攻，買盤積極換手。"
        else: return "PHASE B", "【區間震盪】(Building Cause) 於黃金區間內縮量換手，籌碼沉澱中。"

def analyze_mstr_mnav(mnav):
    if mnav >= 2.0: return "OVERVALUED", "🛑【溢價過高】mNAV 超過 2.0x！回顧 2025 牛市見頂特徵，散戶極度 FOMO 產生巨大泡沫，強烈建議獲利了結！"
    elif mnav >= 1.6: return "PREMIUM", "⚠️【高位溢價】mNAV 達 1.6x 以上，處於歷史相對高位，建議停止追高，開始分批派發。"
    elif mnav <= 0.95: return "DISCOUNT", "🚀【極度低估】mNAV 罕見跌破 1.0x 產生折價！絕對的黃金抄底坑！"
    elif mnav <= 1.15: return "UNDERVALUED", "🔥【折價買進】mNAV 接近基準線 (< 1.15x)，溢價泡沫已洗淨，此時買入具備極高安全邊際！"
    else: return "FAIR VALUE", "⚖️【合理區間】mNAV 位於 1.15x - 1.6x 常態區間，隨 BTC 現貨連動，無極端情緒干擾。"

def analyze_crypto_symbol(symbol_binance, coingecko_id, vs_currency="usd"):
    current_price = 0.0
    highs, lows, closes, volumes = [], [], [], []
    limit_days = 100 
    try:
        bn_url = f"https://api.binance.com/api/v3/klines?symbol={symbol_binance}&interval=1d&limit={limit_days}"
        res = requests.get(bn_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
        if isinstance(res, list) and len(res) >= 20:
            closes, highs, lows, volumes = [float(k[4]) for k in res], [float(k[2]) for k in res], [float(k[3]) for k in res], [float(k[5]) for k in res]
            current_price = closes[-1]
    except: pass

    if current_price == 0.0:
        try:
            cg_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency={vs_currency}&days={limit_days}&interval=daily"
            res = requests.get(cg_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
            p_data, v_data = res.get('prices', []), res.get('total_volumes', [])
            if len(p_data) >= 20:
                min_len = min(len(p_data), len(v_data))
                closes = [p[1] for p in p_data[-min_len:]]
                volumes = [v[1] for v in v_data[-min_len:]]
                highs, lows = [p * 1.025 for p in closes], [p * 0.975 for p in closes]
                current_price = closes[-1]
        except: pass

    if current_price == 0.0:
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                old = json.load(f)
                key = symbol_binance[:3].lower() if symbol_binance != "ETHBTC" else "ethbtc"
                current_price = float(old[key]["price"])
                closes, highs, lows, volumes = [current_price]*30, [current_price*1.02]*30, [current_price*0.98]*30, [1000]*30
        except:
            current_price = 1.0
            closes, highs, lows, volumes = [1.0]*30, [1.02]*30, [0.98]*30, [1000]*30

    decimals = 5 if current_price < 0.1 else (3 if current_price < 50 else 2)
    fib_levels = calculate_fibonacci_levels(highs, lows, decimals)
    swing_plan = calculate_grid_targets(current_price, fib_levels, decimals)
    wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels)

    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    overhead = [h for h in swing_highs if h > current_price]
    resistance = min(overhead) if overhead else (current_price + atr * 1.618)
    underlying = [l for l in swing_lows if l < current_price]
    support = max(underlying) if underlying else (current_price - atr * 1.618)

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1] >= swing_highs[-2] and swing_lows[-1] >= swing_lows[-2]: dow_status, dow_signal = "Bullish", "多頭推進"
        elif swing_highs[-1] <= swing_highs[-2] and swing_lows[-1] <= swing_lows[-2]: dow_status, dow_signal = "Bearish", "空頭受阻"
        else: dow_status, dow_signal = "Neutral", "結構收斂"
    else:
        dow_status, dow_signal = ("Bullish", "趨勢延續") if current_price >= recent_closes[0] else ("Neutral", "趨勢延續")

    final_buy_target, final_sell_target = swing_plan["buy_target"], swing_plan["sell_target"]
    if wyckoff_phase == "PHASE D":
        final_buy_target = fib_levels["fib_236"]
        final_sell_target = fib_levels["macro_high"] * 1.05
    elif wyckoff_phase == "PHASE C":
        final_buy_target = fib_levels["fib_618"]
        final_sell_target = fib_levels["macro_high"]
    elif wyckoff_phase == "PHASE B":
        final_buy_target = fib_levels["fib_500"]
        final_sell_target = fib_levels["fib_236"]
    elif wyckoff_phase == "PHASE A":
        final_buy_target = fib_levels["fib_786"]
        final_sell_target = fib_levels["fib_500"]

    return {
        "price": round(current_price, decimals), "dow_status": dow_status, "dow_signal": dow_signal,
        "support": round(support, decimals), "resistance": round(resistance, decimals),
        "buy_target": round(final_buy_target, decimals), 
        "sell_target": round(final_sell_target, decimals),
        "wyckoff_phase": wyckoff_phase, "wyckoff_hint": wyckoff_hint,
        "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], 
        "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"]
    }

# 🌟 更新：混合引擎。即時價格看 OKX，量價歷史看 Yahoo
def analyze_tokenized_stock(stock_ticker, okx_prefix, is_mstr=False, btc_price=0, official_base_stock=1.0, official_base_mnav=1.21):
    current_price = 0.0
    highs, lows, closes, volumes = [], [], [], []
    headers = {"User-Agent": "Mozilla/5.0"}
    limit_days = 100

    # 1. 抓取 OKX 報價 (確保終端機能 24H 顯示最新價格)
    okx_inst_ids = [f"{okx_prefix}-USDT", f"{okx_prefix}-USDT-SWAP"]
    for instId in okx_inst_ids:
        if current_price != 0.0: break
        try:
            okx_url = f"https://www.okx.com/api/v5/market/ticker?instId={instId}"
            res = requests.get(okx_url, headers=headers, timeout=4).json()
            if res.get("code") == "0" and len(res.get("data", [])) > 0:
                current_price = float(res["data"][0]["last"])
        except Exception: continue

    # 2. 強制抓取 Yahoo Finance 原股數據 (完美避開週末，取得真實華爾街量能)
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_ticker}?interval=1d&range={limit_days}d"
        res = requests.get(url, headers=headers, timeout=6).json()
        quotes = res['chart']['result'][0]['indicators']['quote'][0]
        valid = [(c, h, l, v) for c, h, l, v in zip(quotes['close'], quotes['high'], quotes['low'], quotes['volume']) if None not in (c, h, l, v)]
        if valid:
            closes, highs, lows, volumes = [x[0] for x in valid], [x[1] for x in valid], [x[2] for x in valid], [x[3] for x in valid]
            # 若 OKX API 突然當機，就用美股最新收盤價兜底
            if current_price == 0.0: current_price = closes[-1]
    except Exception: pass

    # 防呆機制
    if not closes or len(closes) < 20:
        if current_price == 0.0: current_price = official_base_stock
        closes = [current_price * (1 + 0.005 * (i - 15)) for i in range(30)]
        highs, lows, volumes = [c * 1.02 for c in closes], [c * 0.98 for c in closes], [1000000]*30

    fib_levels = calculate_fibonacci_levels(highs, lows, 2)
    swing_plan = calculate_grid_targets(current_price, fib_levels, 2)
    
    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1] >= swing_highs[-2] and swing_lows[-1] >= swing_lows[-2]: dow_status, dow_signal = "Bullish", "多頭推進"
        elif swing_highs[-1] <= swing_highs[-2] and swing_lows[-1] <= swing_lows[-2]: dow_status, dow_signal = "Bearish", "空頭受阻"
        else: dow_status, dow_signal = "Neutral", "結構收斂"
    else:
        dow_status, dow_signal = ("Bullish", "趨勢延續") if current_price >= recent_closes[0] else ("Neutral", "趨勢延續")

    final_buy_target, final_sell_target = swing_plan["buy_target"], swing_plan["sell_target"]

    if is_mstr:
        official_base_btc = 81240.0
        stock_ratio = current_price / official_base_stock
        btc_ratio = btc_price / official_base_btc if btc_price > 0 else 1.0
        mnav_multiple = round(official_base_mnav * (stock_ratio / btc_ratio), 2)
        stock_phase, stock_hint = analyze_mstr_mnav(mnav_multiple)

        if stock_phase in ["OVERVALUED", "PREMIUM"]:  
            final_buy_target = fib_levels["fib_236"]
            final_sell_target = fib_levels["macro_high"] * 1.05
        elif stock_phase == "FAIR VALUE":             
            final_buy_target = fib_levels["fib_382"]
            final_sell_target = fib_levels["macro_high"]
        elif stock_phase == "UNDERVALUED":            
            final_buy_target = fib_levels["fib_500"]
            final_sell_target = fib_levels["fib_236"]
        elif stock_phase == "DISCOUNT":               
            final_buy_target = fib_levels["fib_618"]
            final_sell_target = fib_levels["fib_382"]

        return {
            "price": round(current_price, 2), "mnav_multiple": f"{mnav_multiple}x",
            "dow_status": dow_status, 
            "buy_target": round(final_buy_target, 2), "sell_target": round(final_sell_target, 2),
            "wyckoff_phase": stock_phase, "wyckoff_hint": stock_hint, 
            "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], 
            "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"]
        }
    
    else:
        # 這裡丟進去的 volumes 是真實美股的成交量，絕不會有週末無量盲區！
        wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels)

        if wyckoff_phase == "PHASE D":
            final_buy_target = fib_levels["fib_236"]
            final_sell_target = fib_levels["macro_high"] * 1.05
        elif wyckoff_phase == "PHASE C":
            final_buy_target = fib_levels["fib_618"]
            final_sell_target = fib_levels["macro_high"]
        elif wyckoff_phase == "PHASE B":
            final_buy_target = fib_levels["fib_500"]
            final_sell_target = fib_levels["fib_236"]
        elif wyckoff_phase == "PHASE A":
            final_buy_target = fib_levels["fib_786"]
            final_sell_target = fib_levels["fib_500"]

        return {
            "price": round(current_price, 2),
            "dow_status": dow_status, "dow_signal": dow_signal,
            "buy_target": round(final_buy_target, 2), "sell_target": round(final_sell_target, 2),
            "wyckoff_phase": wyckoff_phase, "wyckoff_hint": wyckoff_hint,
            "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], 
            "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"]
        }

def main():
    btc_data = analyze_crypto_symbol("BTCUSDT", "bitcoin")
    eth_data = analyze_crypto_symbol("ETHUSDT", "ethereum")
    ethbtc_data = analyze_crypto_symbol("ETHBTC", "ethereum", "btc")
    sol_data = analyze_crypto_symbol("SOLUSDT", "solana")
    uni_data = analyze_crypto_symbol("UNIUSDT", "uniswap")
    ray_data = analyze_crypto_symbol("RAYUSDT", "raydium")
    zec_data = analyze_crypto_symbol("ZECUSDT", "zcash")

    mstr_data = analyze_tokenized_stock("MSTR", "XMSTR", is_mstr=True, btc_price=btc_data["price"], official_base_stock=153.92, official_base_mnav=1.21)
    xcoin_data = analyze_tokenized_stock("COIN", "XCOIN")
    xadbe_data = analyze_tokenized_stock("ADBE", "XADBE")
    xcrcl_data = analyze_tokenized_stock("CRCL", "XCRCL")

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "btc": btc_data, "eth": eth_data, "ethbtc": ethbtc_data,
        "sol": sol_data, "uni": uni_data,
        "ray": ray_data, "zec": zec_data,
        "mstr": mstr_data, "xcoin": xcoin_data, "xadbe": xadbe_data, "xcrcl": xcrcl_data
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("Data.json updated successfully with Hybrid Engine (OKX Price + Yahoo Volumes).")

if __name__ == "__main__":
    main()
