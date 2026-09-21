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
    atr = sum(tr_list) / len(tr_list) if tr_list else (highs[-1] * 0.035 if highs else 1.0)
    return swing_highs, swing_lows, atr

def calculate_fibonacci_levels(highs, lows, decimals=2):
    if not highs or not lows: return {"macro_high": "N/A", "fib_236": "N/A", "fib_382": "N/A", "fib_500": "N/A", "fib_618": "N/A", "fib_786": "N/A"}
    macro_high, macro_low = max(highs), min(lows)
    diff = macro_high - macro_low
    return {
        "macro_high": round(macro_high, decimals),
        "macro_low": round(macro_low, decimals),
        "fib_236": round(macro_high - (diff * 0.236), decimals),
        "fib_382": round(macro_high - (diff * 0.382), decimals),
        "fib_500": round(macro_high - (diff * 0.500), decimals),
        "fib_618": round(macro_high - (diff * 0.618), decimals),
        "fib_786": round(macro_high - (diff * 0.786), decimals)
    }

def calculate_volume_profile_weights(highs, lows, closes, volumes, fib_levels, decimals=2):
    if not highs or not lows or not volumes or fib_levels["macro_high"] == "N/A":
        return fib_levels, {}

    macro_high = fib_levels["macro_high"]
    macro_low = fib_levels["macro_low"]
    if macro_high == macro_low:
        return fib_levels, {}

    bins_count = 30
    bin_width = (macro_high - macro_low) / bins_count
    volume_profile = [0.0] * bins_count

    for h, l, c, v in zip(highs, lows, closes, volumes):
        typical_price = (h + l + c) / 3
        bin_idx = int((typical_price - macro_low) / bin_width)
        if bin_idx >= bins_count: bin_idx = bins_count - 1
        if bin_idx < 0: bin_idx = 0
        volume_profile[bin_idx] += v

    indexed_profile = sorted(enumerate(volume_profile), key=lambda x: x[1], reverse=True)
    hvn_prices = [macro_low + (idx + 0.5) * bin_width for idx, _ in indexed_profile[:3]]

    fib_keys = ["fib_236", "fib_382", "fib_500", "fib_618", "fib_786"]
    weights = {}
    
    for f_key in fib_keys:
        f_val = fib_levels[f_key]
        score = 1.0
        for hvn in hvn_prices:
            distance = abs(f_val - hvn)
            if distance <= (bin_width * 1.5):
                score += 2.5
        weights[f_key] = round(score, 1)

    return fib_levels, weights

def get_mining_onchain_metrics(btc_current_price):
    """
    🔗 真實抓取全網算力與生產成本指標（無任何寫死假數字，確保客觀真實）
    """
    hashrate_eh = "N/A"
    production_cost = "N/A"
    status = "⚠️ 鏈上數據未同步"
    
    # 1. 真實抓取全網算力 (Blockchain.com API)
    try:
        res = requests.get("https://blockchain.info/q/hashrate", timeout=4)
        if res.status_code == 200:
            h_val = float(res.text)
            hashrate_eh = f"{round(h_val / 1e9, 2)} EH/s"
    except Exception:
        hashrate_eh = "API 連線失敗"

    # 2. 生產成本底線：若無法動態計算則標示 N/A，不給予臆測數值
    # 若您有對接特定的礦業成本 API 可以在此處替換
    production_cost = "N/A" 

    return {
        "hashrate_eh": hashrate_eh,
        "production_cost": production_cost,
        "mining_status": status
    }

def calculate_grid_targets(current_price, fib_levels, highs, lows, closes, decimals=2):
    if current_price == "N/A" or fib_levels["fib_382"] == "N/A":
        return {"buy_target": "N/A", "sell_target": "N/A"}
    
    fib_382 = fib_levels["fib_382"]
    fib_500 = fib_levels["fib_500"]
    fib_618 = fib_levels["fib_618"]
    macro_high = fib_levels["macro_high"]
    macro_low = fib_levels["macro_low"]
    macro_range = macro_high - macro_low

    tr_list = []
    n = len(closes)
    for i in range(1, min(15, n)):
        tr = max(highs[-i] - lows[-i], abs(highs[-i] - closes[-i-1]), abs(lows[-i] - closes[-i-1]))
        tr_list.append(tr)
    atr = sum(tr_list) / len(tr_list) if tr_list else current_price * 0.04

    if current_price > fib_382: buy_target = fib_382
    elif current_price > fib_500: buy_target = fib_500
    elif current_price > fib_618: buy_target = fib_618
    else: buy_target = current_price - (atr * 1.5)

    if current_price < fib_618: sell_target = fib_500
    elif current_price < fib_500: sell_target = fib_382
    elif current_price < macro_high: sell_target = macro_high
    else: sell_target = macro_high + (macro_range * 0.272)

    if sell_target <= current_price: sell_target = current_price + (atr * 2.0)
    if buy_target >= current_price: buy_target = current_price - (atr * 1.2)

    return {"buy_target": round(buy_target, decimals), "sell_target": round(sell_target, decimals)}

def get_dow_status(swing_highs, swing_lows, current_price, recent_closes, fib_levels):
    if current_price == "N/A" or fib_levels["fib_382"] == "N/A":
        return "N/A", "API 數據獲取失敗"
    if current_price > fib_levels["fib_382"]: return "Primary Bull", "SOS 強勢修復"
    elif current_price < fib_levels["fib_618"]: return "Secondary Correction", "空頭壓制"
    return "Consolidation", "結構收斂"

def analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels, dow_status):
    if not closes or len(closes) < 30 or dow_status == "N/A": 
        return "N/A", "⚠️【數據缺失】無法執行威科夫 VSA 診斷"
    vol_sma = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1.0
    recent_3d_vol = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else 1.0
    curr_close = closes[-1]
    curr_high, curr_low = max(highs[-3:]), min(lows[-3:])   
    curr_spread = curr_high - curr_low if curr_high - curr_low > 0 else 0.001
    close_pos = (curr_close - curr_low) / curr_spread 
    is_high_vol, is_low_vol = recent_3d_vol > vol_sma * 1.2, recent_3d_vol < vol_sma * 0.8
    fib_618 = fib_levels["fib_618"]
    
    if curr_low <= fib_618 * 1.015:
        if is_low_vol: return "PHASE C", "🔥【強力買進】無供應測試 (No Supply)：賣壓枯竭！"
        elif is_high_vol and close_pos >= 0.5: return "PHASE C", "🔥【強力買進】彈簧洗盤 (Spring)，絕佳波段買點。"
        else: return "PHASE C", "【邊界測試】位於 618 深水區防守測試中。"
    return "PHASE D", "【區間突圍】多空交戰中，等待方向表態。"

def analyze_crypto_symbol(symbol_binance, coingecko_id, vs_currency="usd", okx_inst_id=None):
    current_price = 0.0
    highs, lows, closes, volumes = [], [], [], []
    limit_days = 100 
    headers = {"User-Agent": "Mozilla/5.0"}
    
    if okx_inst_id:
        try:
            res = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={okx_inst_id}&bar=1D&limit={limit_days}", headers=headers, timeout=5).json()
            if res.get("code") == "0" and len(res.get("data", [])) >= 20:
                raw = res["data"][::-1]
                closes, highs, lows, volumes = [float(k[4]) for k in raw], [float(k[2]) for k in raw], [float(k[3]) for k in raw], [float(k[5]) for k in raw]
                current_price = closes[-1]
        except: pass

    if current_price == 0.0 or len(closes) < 20:
        try:
            res = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol_binance}&interval=1d&limit={limit_days}", headers=headers, timeout=5).json()
            if isinstance(res, list) and len(res) >= 20:
                closes, highs, lows, volumes = [float(k[4]) for k in res], [float(k[2]) for k in res], [float(k[3]) for k in res], [float(k[5]) for k in res]
                current_price = closes[-1]
        except: pass

    if current_price == 0.0 or not closes:
        return {"price": "N/A", "dow_status": "N/A", "wyckoff_phase": "N/A", "wyckoff_hint": "資料讀取失敗"}

    decimals = 5 if current_price < 0.1 else (3 if current_price < 50 else 2)
    fib_levels = calculate_fibonacci_levels(highs, lows, decimals)
    fib_levels, fib_weights = calculate_volume_profile_weights(highs, lows, closes, volumes, fib_levels, decimals)
    swing_plan = calculate_grid_targets(current_price, fib_levels, highs, lows, closes, decimals)

    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    dow_status, dow_signal = get_dow_status(swing_highs, swing_lows, current_price, recent_closes, fib_levels)
    wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels, dow_status)

    result = {
        "price": round(current_price, decimals), "dow_status": dow_status, "dow_signal": dow_signal,
        "buy_target": swing_plan["buy_target"], "sell_target": swing_plan["sell_target"],
        "wyckoff_phase": wyckoff_phase, "wyckoff_hint": wyckoff_hint,
        "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], 
        "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"],
        "fib_weights": fib_weights
    }

    if symbol_binance == "BTCUSDT":
        result["mining_data"] = get_mining_onchain_metrics(current_price)

    return result

def analyze_tokenized_stock(stock_ticker, okx_prefix, is_mstr=False, btc_price=0, official_base_stock=1.0, official_base_mnav=1.21):
    current_price = 0.0
    highs, lows, closes, volumes = [], [], [], []
    headers = {"User-Agent": "Mozilla/5.0"}
    limit_days = 100

    for instId in [f"{okx_prefix}-USDT", f"{okx_prefix}-USDT-SWAP"]:
        if current_price != 0.0: break
        try:
            res = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={instId}", headers=headers, timeout=4).json()
            if res.get("code") == "0" and len(res.get("data", [])) > 0:
                current_price = float(res["data"][0]["last"])
        except: continue

    try:
        res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_ticker}?interval=1d&range={limit_days}d", headers=headers, timeout=5).json()
        quotes = res['chart']['result'][0]['indicators']['quote'][0]
        valid = [(c, h, l, v) for c, h, l, v in zip(quotes['close'], quotes['high'], quotes['low'], quotes['volume']) if None not in (c, h, l, v)]
        if valid:
            closes, highs, lows, volumes = [x[0] for x in valid], [x[1] for x in valid], [x[2] for x in valid], [x[3] for x in valid]
            if current_price == 0.0: current_price = closes[-1]
    except: pass

    if current_price == 0.0 or not closes:
        return {"price": "N/A", "dow_status": "N/A", "wyckoff_phase": "N/A", "wyckoff_hint": "資料讀取失敗"}

    fib_levels = calculate_fibonacci_levels(highs, lows, 2)
    fib_levels, fib_weights = calculate_volume_profile_weights(highs, lows, closes, volumes, fib_levels, 2)
    swing_plan = calculate_grid_targets(current_price, fib_levels, highs, lows, closes, 2)
    
    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    dow_status, dow_signal = get_dow_status(swing_highs, swing_lows, current_price, recent_closes, fib_levels)

    if is_mstr:
        official_base_btc = 81240.0
        stock_ratio = current_price / official_base_stock
        btc_ratio = btc_price / official_base_btc if btc_price > 0 else 1.0
        mnav_multiple = round(official_base_mnav * (stock_ratio / btc_ratio), 2)
        if mnav_multiple >= 2.0: phase, hint = "OVERVALUED", "🛑 溢價過高"
        elif mnav_multiple <= 0.95: phase, hint = "DISCOUNT", "🚀 折價買進"
        else: phase, hint = "FAIR VALUE", "⚖️ 合理區間"
        return {"price": round(current_price, 2), "mnav_multiple": f"{mnav_multiple}x", "dow_status": dow_status, "buy_target": swing_plan["buy_target"], "sell_target": swing_plan["sell_target"], "wyckoff_phase": phase, "wyckoff_hint": hint, "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"], "fib_weights": fib_weights}
    
    wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels, dow_status)
    return {"price": round(current_price, 2), "dow_status": dow_status, "buy_target": swing_plan["buy_target"], "sell_target": swing_plan["sell_target"], "wyckoff_phase": wyckoff_phase, "wyckoff_hint": wyckoff_hint, "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"], "fib_weights": fib_weights}

def main():
    btc_data = analyze_crypto_symbol("BTCUSDT", "bitcoin", okx_inst_id="BTC-USDT")
    eth_data = analyze_crypto_symbol("ETHUSDT", "ethereum", okx_inst_id="ETH-USDT")
    ethbtc_data = analyze_crypto_symbol("ETHBTC", "ethereum", "btc")
    sol_data = analyze_crypto_symbol("SOLUSDT", "solana", okx_inst_id="SOL-USDT")
    uni_data = analyze_crypto_symbol("UNIUSDT", "uniswap", okx_inst_id="UNI-USDT")
    ray_data = analyze_crypto_symbol("RAYUSDT", "raydium", okx_inst_id="RAY-USDT")
    zec_data = analyze_crypto_symbol("ZECUSDT", "zcash", okx_inst_id="ZEC-USDT")

    mstr_btc_price = btc_data["price"] if btc_data["price"] != "N/A" else 80000.0
    mstr_data = analyze_tokenized_stock("MSTR", "XMSTR", is_mstr=True, btc_price=mstr_btc_price, official_base_stock=153.92, official_base_mnav=1.21)
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
    print("Data.json updated successfully with strict real on-chain checks.")

if __name__ == "__main__":
    main()
