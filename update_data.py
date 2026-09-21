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
    """
    🏛️ 華爾街級 Volume Profile 動態權重引擎：
    計算各個價位的成交量分佈密度，找出高成交密集區 (HVN / POC)，
    並對費氏回撤檔位進行「成交量共振權重」評分與微調。
    """
    if not highs or not lows or not volumes or fib_levels["macro_high"] == "N/A":
        return fib_levels, {}

    macro_high = fib_levels["macro_high"]
    macro_low = fib_levels["macro_low"]
    if macro_high == macro_low:
        return fib_levels, {}

    # 將價格區間劃分為 30 個 Bins
    bins_count = 30
    bin_width = (macro_high - macro_low) / bins_count
    volume_profile = [0.0] * bins_count

    for h, l, c, v in zip(highs, lows, closes, volumes):
        typical_price = (h + l + c) / 3
        bin_idx = int((typical_price - macro_low) / bin_width)
        if bin_idx >= bins_count: bin_idx = bins_count - 1
        if bin_idx < 0: bin_idx = 0
        volume_profile[bin_idx] += v

    # 找出成交量最高的前 3 個價位帶 (High Volume Nodes)
    indexed_profile = sorted(enumerate(volume_profile), key=lambda x: x[1], reverse=True)
    hvn_prices = [macro_low + (idx + 0.5) * bin_width for idx, _ in indexed_profile[:3]]

    # 評估各個費氏檔位的「成交量共振權重」 (Confluence Score)
    # 如果費氏支撐位剛好落在成交密集區附近 (距離小於 1.5 個 bin_width)，給予高權重
    fib_keys = ["fib_236", "fib_382", "fib_500", "fib_618", "fib_786"]
    weights = {}
    
    for f_key in fib_keys:
        f_val = fib_levels[f_key]
        score = 1.0  # 基礎權重
        for hvn in hvn_prices:
            distance = abs(f_val - hvn)
            if distance <= (bin_width * 1.5):
                score += 2.5  # 發生價量共振，大幅提升權重！
        weights[f_key] = round(score, 1)

    return fib_levels, weights

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

    # 1. 動態權重買入目標計算
    if current_price > fib_382: 
        buy_target = fib_382
    elif current_price > fib_500: 
        buy_target = fib_500
    elif current_price > fib_618: 
        buy_target = fib_618
    else: 
        buy_target = current_price - (atr * 1.5)

    # 2. 賣出目標計算（雙軌分工：箱體內 or 突破新高幾何延伸）
    if current_price < fib_618: 
        sell_target = fib_500
    elif current_price < fib_500: 
        sell_target = fib_382
    elif current_price < macro_high: 
        sell_target = macro_high
    else: 
        sell_target = macro_high + (macro_range * 0.272)

    if sell_target <= current_price:
        sell_target = current_price + (atr * 2.0)

    if buy_target >= current_price:
        buy_target = current_price - (atr * 1.2)

    return {"buy_target": round(buy_target, decimals), "sell_target": round(sell_target, decimals)}

def get_dow_status(swing_highs, swing_lows, current_price, recent_closes, fib_levels):
    if current_price == "N/A" or fib_levels["fib_382"] == "N/A":
        return "N/A", "API 數據獲取失敗，標記為 N/A"
    
    if current_price > fib_levels["fib_382"]:
        return "Primary Bull", "SOS 強勢修復"
    elif current_price < fib_levels["fib_618"]:
        return "Secondary Correction", "空頭壓制"

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        last_high, prev_high = swing_highs[-1], swing_highs[-2]
        last_low, prev_low = swing_lows[-1], swing_lows[-2]

        if current_price > last_high: return "Primary Bull", "強勢突破"
        if last_high >= prev_high and last_low >= prev_low: return "Primary Bull", "多頭推進"
        elif last_high <= prev_high and last_low <= prev_low: return "Secondary Correction", "空頭受阻"
        else: return "Consolidation", "結構收斂"
    else:
        return ("Primary Bull", "趨勢延續") if current_price >= recent_closes[0] else ("Consolidation", "趨勢延續")

def analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels, dow_status):
    if not closes or len(closes) < 30 or dow_status == "N/A": 
        return "N/A", "⚠️【數據缺失】API 斷線或數據不足，無法執行威科夫 VSA 診斷 (N/A)。"
    
    vol_sma = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1.0
    recent_3d_vol = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else 1.0
    curr_close, prev_close = closes[-1], (closes[-4] if len(closes) >= 4 else closes[0])
    curr_high, curr_low = max(highs[-3:]), min(lows[-3:])   
    curr_spread = curr_high - curr_low if curr_high - curr_low > 0 else 0.001
    close_pos = (curr_close - curr_low) / curr_spread 
    is_high_vol, is_low_vol = recent_3d_vol > vol_sma * 1.2, recent_3d_vol < vol_sma * 0.8
    fib_382, fib_618 = fib_levels["fib_382"], fib_levels["fib_618"]
    
    recent_max_20 = max(highs[-20:])
    is_bouncing_from_low = (curr_close - min(lows[-20:])) > (recent_max_20 - min(lows[-20:])) * 0.5
    
    if curr_low <= fib_618 * 1.015:
        if is_bouncing_from_low and dow_status == "Secondary Correction":
            return "PHASE B", "⚖️【高位回調】雖觸及 618 幾何支撐，但屬於自低位反彈後的回測，盈虧比不佳，建議暫時觀望。"

        if is_low_vol: 
            return "PHASE C", "🔥【強力買進】無供應測試 (No Supply)：賣壓枯竭，右側絕佳買點！"
        elif is_high_vol and close_pos >= 0.5: 
            if dow_status == "Primary Bull": return "PHASE C", "🔥【強力買進】完美共振！主升趨勢中的彈簧洗盤 (Spring)，絕佳波段買點。"
            elif dow_status == "Secondary Correction": return "PHASE C", "🔥【強力買進】極度低估！宏觀極限回調出現恐慌拋售與彈簧洗盤，左側摸底。"
            else: return "PHASE C", "🔥【強力買進】區間極限測試！彈簧洗盤 (Spring) 爆量收腳，主力吃貨。"
        elif is_high_vol and close_pos < 0.5: 
            if dow_status == "Secondary Correction": return "PHASE E", "🛑【逃頂賣出】趨勢破壞！空頭結構全面崩盤，嚴格停損。"
            return "PHASE A", "【恐慌拋售】近三日放量跌破 618，賣壓沉重，觀望勿接飛刀。"
        else: 
            return "PHASE C", "【邊界測試】位於 618 深水區防守測試中，等待量能表態。"
            
    elif curr_high >= fib_382 * 0.985:
        if is_high_vol and close_pos <= 0.3 and curr_close < prev_close: 
            if dow_status == "Primary Bull": 
                return "PHASE B", "🛑【逃頂賣出】高位假突破 (UTAD)！爆量卻留長上影線或實體大跌，主力倒貨，此前的突破宣告失敗！"
            elif dow_status == "Secondary Correction": 
                return "PHASE B", "⚠️【死貓反彈】空頭結構微觀拉升 (LPSY)，遭遇解套賣壓，注意誘多風險！"
            else: 
                return "PHASE B", "🛑【逃頂賣出】上衝回落 (Upthrust)：高檔爆量卻無法收高，危險訊號！"
                
        elif curr_close >= fib_382 * 0.98 and curr_close < closes[-2] and is_low_vol:
            return "PHASE D", "✅【回踩確認】(BUEC) 突破後縮量回測支撐，無明顯拋售壓，確認為真實 SOS，右側買點浮現."

        elif curr_close > prev_close and is_high_vol and close_pos >= 0.5: 
            if dow_status == "Primary Bull": 
                return "PHASE D", "🚀【強勢表態】(SOS) 爆量突破強壓！(系統提示：準備觀察後續是否出現 BUEC 縮量回踩確認)"
            else: 
                return "PHASE D", "🚀【強勢表態】需求強勁湧現，挑戰上方強壓區。"
                
        elif curr_close > prev_close and is_low_vol: 
            return "PHASE B", "⚠️【高位誘多】需求不足 (No Demand)：無量過高，提防假突破！"
            
        else: 
            if dow_status == "Primary Bull":
                return "PHASE D", "【頂部突破】挑戰上方強壓區，關注多頭量能是否持續堆積。"
            else:
                return "PHASE D", "【區間突圍】多空交戰中，嚴格觀望，等待方向表態."
            
    else:
        if curr_close < prev_close and is_low_vol: 
            return "PHASE C", "【二次測試】(Secondary Test) 區間內回調且連續縮量，測試下方籌碼。"
        elif curr_close > prev_close and is_high_vol: 
            return "PHASE D", "【標記躍升】(Minor SOS) 區間內連續放量上攻，買盤積極換手。"
        else: 
            if dow_status == "Consolidation": return "PHASE B", "⚖️【籌碼沉澱】主力建立部位中，無明確方向，建議嚴格執行高拋低吸。"
            return "PHASE B", "【區間震盪】於黃金區間內縮量換手，籌碼沉澱中。"

def analyze_mstr_mnav(mnav):
    if mnav >= 2.0: return "OVERVALUED", "🛑【逃頂賣出】溢價過高！mNAV 超過 2.0x 極端溢價，脫離 BTC 基本面，強烈建議獲利了結！"
    elif mnav >= 1.6: return "PREMIUM", "⚠️【高位溢價】mNAV 達 1.6x 以上，處於歷史相對高位，建議停止追高。"
    elif mnav <= 0.95: return "DISCOUNT", "🚀【極度低估】mNAV 罕見跌破 1.0x 產生折價！絕對的黃金抄底坑！"
    elif mnav <= 1.15: return "UNDERVALUED", "🔥【強力買進】折價買進！mNAV 接近基準線，溢價泡沫已洗淨，具備極高安全邊際！"
    else: return "FAIR VALUE", "⚖️【合理區間】mNAV 位於 1.15x - 1.6x 常態區間，隨 BTC 現貨連動，無極端情緒干擾。"

def analyze_crypto_symbol(symbol_binance, coingecko_id, vs_currency="usd", okx_inst_id=None):
    current_price = 0.0
    highs, lows, closes, volumes = [], [], [], []
    limit_days = 100 
    headers = {"User-Agent": "Mozilla/5.0"}
    
    if okx_inst_id:
        try:
            okx_kline_url = f"https://www.okx.com/api/v5/market/candles?instId={okx_inst_id}&bar=1D&limit={limit_days}"
            res = requests.get(okx_kline_url, headers=headers, timeout=6).json()
            if res.get("code") == "0" and len(res.get("data", [])) >= 20:
                raw_candles = res["data"][::-1]
                closes = [float(k[4]) for k in raw_candles]
                highs = [float(k[2]) for k in raw_candles]
                lows = [float(k[3]) for k in raw_candles]
                volumes = [float(k[5]) for k in raw_candles]
                current_price = closes[-1]
        except: pass

    if current_price == 0.0 or len(closes) < 20:
        try:
            bn_url = f"https://api.binance.com/api/v3/klines?symbol={symbol_binance}&interval=1d&limit={limit_days}"
            res = requests.get(bn_url, headers=headers, timeout=6).json()
            if isinstance(res, list) and len(res) >= 20:
                closes = [float(k[4]) for k in res]
                highs = [float(k[2]) for k in res]
                lows = [float(k[3]) for k in res]
                volumes = [float(k[5]) for k in res]
                current_price = closes[-1]
        except: pass

    if current_price == 0.0 or len(closes) < 20:
        try:
            cg_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency={vs_currency}&days={limit_days}&interval=daily"
            res = requests.get(cg_url, headers=headers, timeout=6).json()
            p_data, v_data = res.get('prices', []), res.get('total_volumes', [])
            if len(p_data) >= 20:
                min_len = min(len(p_data), len(v_data))
                closes = [p[1] for p in p_data[-min_len:]]
                volumes = [v[1] for v in v_data[-min_len:]]
                highs = [p[1] * 1.02 for p in p_data[-min_len:]]
                lows = [p[1] * 0.98 for p in p_data[-min_len:]]
                current_price = closes[-1]
        except: pass

    if current_price == 0.0 or not closes:
        return {
            "price": "N/A", "dow_status": "N/A", "dow_signal": "API 連線失敗，數據缺失 (N/A)",
            "support": "N/A", "resistance": "N/A", "buy_target": "N/A", "sell_target": "N/A",
            "wyckoff_phase": "N/A", "wyckoff_hint": "🛑【數據異常】無法取得即時行情與歷史 K 線，請檢查 API 狀態。",
            "fib_236": "N/A", "fib_382": "N/A", "fib_500": "N/A", "fib_618": "N/A"
        }

    decimals = 5 if current_price < 0.1 else (3 if current_price < 50 else 2)
    fib_levels = calculate_fibonacci_levels(highs, lows, decimals)
    fib_levels, fib_weights = calculate_volume_profile_weights(highs, lows, closes, volumes, fib_levels, decimals)
    
    swing_plan = calculate_grid_targets(current_price, fib_levels, highs, lows, closes, decimals)

    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)
    
    dow_status, dow_signal = get_dow_status(swing_highs, swing_lows, current_price, recent_closes, fib_levels)
    wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels, dow_status)

    overhead = [h for h in swing_highs if h > current_price]
    resistance = min(overhead) if overhead else (current_price + atr * 1.618)
    underlying = [l for l in swing_lows if l < current_price]
    support = max(underlying) if underlying else (current_price - atr * 1.618)

    final_buy_target = swing_plan["buy_target"]
    final_sell_target = swing_plan["sell_target"]

    if wyckoff_phase == "PHASE C" and fib_levels["fib_618"] < current_price:
        final_buy_target = fib_levels["fib_618"]
    elif wyckoff_phase == "PHASE D" and fib_levels["fib_236"] < current_price:
        final_buy_target = fib_levels["fib_236"]

    return {
        "price": round(current_price, decimals), "dow_status": dow_status, "dow_signal": dow_signal,
        "support": round(support, decimals) if support != "N/A" else "N/A", 
        "resistance": round(resistance, decimals) if resistance != "N/A" else "N/A",
        "buy_target": round(final_buy_target, decimals) if final_buy_target != "N/A" else "N/A", 
        "sell_target": round(final_sell_target, decimals) if final_sell_target != "N/A" else "N/A",
        "wyckoff_phase": wyckoff_phase, "wyckoff_hint": wyckoff_hint,
        "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], 
        "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"],
        "fib_weights": fib_weights  # 傳遞動態成交量權重給前端
    }

def analyze_tokenized_stock(stock_ticker, okx_prefix, is_mstr=False, btc_price=0, official_base_stock=1.0, official_base_mnav=1.21):
    current_price = 0.0
    highs, lows, closes, volumes = [], [], [], []
    headers = {"User-Agent": "Mozilla/5.0"}
    limit_days = 100

    okx_inst_ids = [f"{okx_prefix}-USDT", f"{okx_prefix}-USDT-SWAP"]
    for instId in okx_inst_ids:
        if current_price != 0.0: break
        try:
            okx_url = f"https://www.okx.com/api/v5/market/ticker?instId={instId}"
            res = requests.get(okx_url, headers=headers, timeout=4).json()
            if res.get("code") == "0" and len(res.get("data", [])) > 0:
                current_price = float(res["data"][0]["last"])
        except Exception: continue

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_ticker}?interval=1d&range={limit_days}d"
        res = requests.get(url, headers=headers, timeout=6).json()
        quotes = res['chart']['result'][0]['indicators']['quote'][0]
        valid = [(c, h, l, v) for c, h, l, v in zip(quotes['close'], quotes['high'], quotes['low'], quotes['volume']) if None not in (c, h, l, v)]
        if valid:
            closes, highs, lows, volumes = [x[0] for x in valid], [x[1] for x in valid], [x[2] for x in valid], [x[3] for x in valid]
            if current_price == 0.0: current_price = closes[-1]
    except Exception: pass

    if current_price == 0.0 or not closes:
        return {
            "price": "N/A", "dow_status": "N/A", "dow_signal": "API 連線失敗，數據缺失 (N/A)",
            "buy_target": "N/A", "sell_target": "N/A",
            "wyckoff_phase": "N/A", "wyckoff_hint": "🛑【數據異常】無法取得美股/代幣化資產行情。",
            "fib_236": "N/A", "fib_382": "N/A", "fib_500": "N/A", "fib_618": "N/A"
        }

    fib_levels = calculate_fibonacci_levels(highs, lows, 2)
    fib_levels, fib_weights = calculate_volume_profile_weights(highs, lows, closes, volumes, fib_levels, 2)
    
    swing_plan = calculate_grid_targets(current_price, fib_levels, highs, lows, closes, 2)
    
    recent_highs, recent_lows, recent_closes = highs[-45:], lows[-45:], closes[-45:]
    swing_highs, swing_lows, atr = find_fractal_pivots(recent_highs, recent_lows, recent_closes)

    dow_status, dow_signal = get_dow_status(swing_highs, swing_lows, current_price, recent_closes, fib_levels)
    final_buy_target, final_sell_target = swing_plan["buy_target"], swing_plan["sell_target"]

    if is_mstr:
        official_base_btc = 81240.0
        stock_ratio = current_price / official_base_stock
        btc_ratio = btc_price / official_base_btc if btc_price > 0 else 1.0
        mnav_multiple = round(official_base_mnav * (stock_ratio / btc_ratio), 2)
        
        stock_phase, stock_hint = analyze_mstr_mnav(mnav_multiple)

        return {
            "price": round(current_price, 2), "mnav_multiple": f"{mnav_multiple}x",
            "dow_status": dow_status, 
            "buy_target": round(final_buy_target, 2), "sell_target": round(final_sell_target, 2),
            "wyckoff_phase": stock_phase, "wyckoff_hint": stock_hint, 
            "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], 
            "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"],
            "fib_weights": fib_weights
        }
    
    else:
        wyckoff_phase, wyckoff_hint = analyze_wyckoff_vsa(highs, lows, closes, volumes, fib_levels, dow_status)

        return {
            "price": round(current_price, 2),
            "dow_status": dow_status, "dow_signal": dow_signal,
            "buy_target": round(final_buy_target, 2), "sell_target": round(final_sell_target, 2),
            "wyckoff_phase": wyckoff_phase, "wyckoff_hint": wyckoff_hint,
            "fib_236": fib_levels["fib_236"], "fib_382": fib_levels["fib_382"], 
            "fib_500": fib_levels["fib_500"], "fib_618": fib_levels["fib_618"],
            "fib_weights": fib_weights
        }

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
    print("Data.json updated successfully with Volume Profile Confluence Weights.")

if __name__ == "__main__":
    main()
