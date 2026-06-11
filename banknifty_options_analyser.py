"""
BankNifty Options Chain Analyser — CSV Mode
============================================
Reads the CSV you download from NSE. Sends full analysis to Telegram.

HOW TO USE:
1. Go to nseindia.com/option-chain
2. Select BANKNIFTY -> nearest expiry
3. Click Download CSV (top right of chain table)
4. Save as: banknifty_chain.csv in same folder as this script
5. Run: py banknifty_options_analyser.py
"""

import requests, os, math, csv, io, time, base64
import numpy as np
from datetime import datetime, date

BOT_TOKEN     = "8876359954:AAFfdyEKxrKPK6Q_k6HcCkjP0r4c8-L1tcg"
CHAT_ID       = "8635374747"
CHANNEL_ID    = "@geomacrodigest"
CSV_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banknifty_chain.csv")
X_THREAD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "x_thread_banknifty.txt")

GITHUB_TOKEN  = "YOUR_GITHUB_PAT_HERE"
GITHUB_REPO   = "geomacrodigest/geomacrodigest"
GITHUB_URL    = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
PAGES_BASE    = "https://geomacrodigest.github.io/geomacrodigest"

BANKNIFTY_DASHBOARD_DIR = os.path.expanduser("~/Downloads/BankNifty Dashboard")
HTML_FILE = os.path.join(
    BANKNIFTY_DASHBOARD_DIR if os.path.exists(BANKNIFTY_DASHBOARD_DIR) else os.path.dirname(os.path.abspath(__file__)),
    "banknifty_chain.html"
)

LOT_SIZE       = 30     # BankNifty lot size — update if changed
MIN_PREMIUM    = 30     # min LTP for naked sell suggestion (higher than Nifty)
SPREAD_WIDTH   = 500    # credit spread width in points (BankNifty moves faster)
MIN_CREDIT     = 30     # min net credit for spread
SL_MULTIPLIER  = 2.0   # SL = entry × this

def fmt_oi(oi_contracts):
    """Smart OI display: L if >=1L, K if >=1K, else raw contracts."""
    val = oi_contracts * LOT_SIZE
    if val >= 100000:
        return f"{val/100000:.1f}L".rstrip('0').rstrip('.')  + "L" if False else f"{val/100000:.1f}L"
    elif val >= 1000:
        return f"{int(val/1000)}K"
    else:
        return str(int(val))

def fmt_chg_oi(oi_contracts):
    """Same as fmt_oi but returns None if zero (to suppress display)."""
    if oi_contracts <= 0:
        return None
    return fmt_oi(oi_contracts)

# ── NSE Trading Holidays 2025–2026 ────────────────────────────────────────────
NSE_HOLIDAYS = {
    date(2026, 1, 15),  # Municipal Corporation Election - Maharashtra
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 3),   # Holi
    date(2026, 3, 26),  # Shri Ram Navami
    date(2026, 3, 31),  # Shri Mahavir Jayanti
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 5, 28),  # Bakri Id
    date(2026, 6, 26),  # Muharram
    date(2026, 9, 14),  # Ganesh Chaturthi
    date(2026, 10, 2),  # Mahatma Gandhi Jayanti
    date(2026, 10, 20), # Dussehra
    date(2026, 11, 10), # Diwali - Balipratipada
    date(2026, 11, 24), # Prakash Gurpurb Sri Guru Nanak Dev
    date(2026, 12, 25), # Christmas
}

def trading_days_until(expiry_date: date) -> int:
    from datetime import timedelta, datetime
    try:
        import pytz
        IST = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(IST)
    except ImportError:
        from datetime import timezone, timedelta as td
        now_ist = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(
            timezone(td(hours=5, minutes=30)))
    today = now_ist.date()

    if expiry_date <= today:
        return 0

    count = 0
    market_open_time = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    today_is_trading = today.weekday() < 5 and today not in NSE_HOLIDAYS
    if today_is_trading and now_ist < market_open_time:
        count += 1

    d = today + timedelta(days=1)
    while d <= expiry_date:
        if d.weekday() < 5 and d not in NSE_HOLIDAYS:
            count += 1
        d += timedelta(days=1)
    return max(count, 0)

def trading_days_between(start: date, end: date) -> int:
    from datetime import timedelta
    count = 0
    d = start + timedelta(days=1)
    while d <= end:
        if d.weekday() < 5 and d not in NSE_HOLIDAYS:
            count += 1
        d += timedelta(days=1)
    return max(count, 0)


# ── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    MAX = 3800
    chunks, cur = [], ""
    for line in msg.split("\n"):
        if len(cur) + len(line) + 1 > MAX:
            chunks.append(cur); cur = line
        else:
            cur += ("\n" if cur else "") + line
    if cur: chunks.append(cur)
    for i, chunk in enumerate(chunks):
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": chunk, "parse_mode": "HTML"}, timeout=10)
        print(f"  Telegram sent (part {i+1}/{len(chunks)})" if r.status_code == 200 else f"  Error: {r.text}")
        time.sleep(0.5)

def send_telegram_to(chat_id, msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    MAX = 3800
    chunks, cur = [], ""
    for line in msg.split("\n"):
        if len(cur) + len(line) + 1 > MAX:
            chunks.append(cur); cur = line
        else:
            cur += ("\n" if cur else "") + line
    if cur: chunks.append(cur)
    for i, chunk in enumerate(chunks):
        r = requests.post(url, data={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"}, timeout=10)
        print(f"  Sent (part {i+1}/{len(chunks)})" if r.status_code == 200 else f"  Error: {r.text}")
        time.sleep(0.5)


# ── CSV PARSER ────────────────────────────────────────────────────────────────

def clean(val):
    try:
        v = str(val).strip().replace(",", "").replace('"', "")
        return 0.0 if v in ["-", "", "NA"] else float(v)
    except:
        return 0.0

def parse_csv(filepath):
    with open(filepath, "r") as f:
        lines = f.read().split("\n")
    rows = []
    for line in lines[23:]:
        if not line.strip(): continue
        cols = next(csv.reader(io.StringIO(line)), None)
        if not cols or len(cols) < 12: continue
        try:
            strike = clean(cols[11])
            if not (30000 < strike < 80000): continue  # BankNifty range
            rows.append({
                "strike"    : strike,
                "ce_oi"     : clean(cols[1]),
                "ce_chg_oi" : clean(cols[2]),
                "ce_iv"     : clean(cols[4]),
                "ce_ltp"    : clean(cols[5]),
                "pe_ltp"    : clean(cols[17]) if len(cols) > 17 else 0,
                "pe_iv"     : clean(cols[18]) if len(cols) > 18 else 0,
                "pe_chg_oi" : clean(cols[20]) if len(cols) > 20 else 0,
                "pe_oi"     : clean(cols[21]) if len(cols) > 21 else 0,
            })
        except:
            continue
    return sorted(rows, key=lambda x: x["strike"])


# ── BLACK-SCHOLES (for EV calc) ───────────────────────────────────────────────

def _bs_delta(S, K, T, r, sigma, opt):
    try:
        from scipy.stats import norm
        if T <= 0 or sigma <= 0: return 0.0
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        return float(norm.cdf(d1) - 1) if opt == 'PE' else float(norm.cdf(d1))
    except:
        moneyness = (S - K) / S
        if opt == 'PE':
            return max(-0.5, min(-0.05, moneyness - 0.5))
        else:
            return max(0.05, min(0.5, moneyness + 0.5))

def compute_ev(ltp, delta_abs, spread_width=None):
    p_profit = 1 - delta_abs
    if spread_width:
        max_loss = spread_width - ltp
        ev = round((p_profit * ltp) - (delta_abs * max_loss), 2)
    else:
        max_loss = ltp * 5
        ev = round((p_profit * ltp) - (delta_abs * max_loss), 2)
    return ev, round(p_profit * 100, 1)


# ── 0 DTE SCALP MODE ──────────────────────────────────────────────────────────

def _get_0dte_suggestions(rows, spot, atm, bias):
    scalp_min, scalp_max = 2.0, 20.0  # BankNifty: slightly wider range
    suggestions = []

    if bias in ("BULLISH", "MILDLY BULLISH"):
        candidates = [x for x in rows
                      if x['strike'] < spot
                      and scalp_min <= x['pe_ltp'] <= scalp_max
                      and x['pe_oi'] > 0]
        candidates = sorted(candidates, key=lambda x: x['pe_oi'], reverse=True)
        if candidates:
            best = candidates[0]
            ltp  = best['pe_ltp']
            tgt  = round(ltp * 0.5, 2)
            gap  = int(spot - best['strike'])
            suggestions.append(
                f"\n🟢 <b>0DTE SCALP — SELL PE {int(best['strike']):,}</b>\n"
                f"   LTP ₹{ltp} | OI {int(best['pe_oi']):,} | {gap} pts OTM\n"
                f"   Target: ₹{tgt} (50% decay) | SL: spot breaks {int(best['strike']):,}\n"
                f"   ⏰ Exit by 3:15 PM regardless"
            )
            if len(candidates) > 1:
                b2  = candidates[1]
                tgt2 = round(b2['pe_ltp'] * 0.5, 2)
                gap2 = int(spot - b2['strike'])
                suggestions.append(
                    f"\n   Alt: Sell PE {int(b2['strike']):,} | LTP ₹{b2['pe_ltp']} | {gap2} pts OTM | Tgt ₹{tgt2}"
                )
        else:
            suggestions.append(f"\n⚠️ No PE strike in ₹{scalp_min}–₹{scalp_max} range — spot may be near support")

    elif bias == "BEARISH":
        candidates = [x for x in rows
                      if x['strike'] > spot
                      and scalp_min <= x['ce_ltp'] <= scalp_max
                      and x['ce_oi'] > 0]
        candidates = sorted(candidates, key=lambda x: x['ce_oi'], reverse=True)
        if candidates:
            best = candidates[0]
            ltp  = best['ce_ltp']
            tgt  = round(ltp * 0.5, 2)
            gap  = int(best['strike'] - spot)
            suggestions.append(
                f"\n🔴 <b>0DTE SCALP — SELL CE {int(best['strike']):,}</b>\n"
                f"   LTP ₹{ltp} | OI {int(best['ce_oi']):,} | {gap} pts OTM\n"
                f"   Target: ₹{tgt} (50% decay) | SL: spot breaks {int(best['strike']):,}\n"
                f"   ⏰ Exit by 3:15 PM regardless"
            )
            if len(candidates) > 1:
                b2  = candidates[1]
                tgt2 = round(b2['ce_ltp'] * 0.5, 2)
                gap2 = int(b2['strike'] - spot)
                suggestions.append(
                    f"\n   Alt: Sell CE {int(b2['strike']):,} | LTP ₹{b2['ce_ltp']} | {gap2} pts OTM | Tgt ₹{tgt2}"
                )
        else:
            suggestions.append(f"\n⚠️ No CE strike in ₹{scalp_min}–₹{scalp_max} range — spot may be near resistance")

    else:  # NEUTRAL
        pe_cands = sorted([x for x in rows if x['strike'] < spot and scalp_min <= x['pe_ltp'] <= scalp_max and x['pe_oi'] > 0],
                          key=lambda x: x['pe_oi'], reverse=True)
        ce_cands = sorted([x for x in rows if x['strike'] > spot and scalp_min <= x['ce_ltp'] <= scalp_max and x['ce_oi'] > 0],
                          key=lambda x: x['ce_oi'], reverse=True)
        for label, best_list, ltp_key, oi_key, color in [
            ("PE", pe_cands, "pe_ltp", "pe_oi", "🟢"),
            ("CE", ce_cands, "ce_ltp", "ce_oi", "🔴"),
        ]:
            if best_list:
                best = best_list[0]
                ltp  = best[ltp_key]
                tgt  = round(ltp * 0.5, 2)
                gap  = abs(int(spot - best['strike']))
                suggestions.append(
                    f"\n{color} <b>0DTE SCALP — SELL {label} {int(best['strike']):,}</b>\n"
                    f"   LTP ₹{ltp} | OI {int(best[oi_key]):,} | {gap} pts OTM\n"
                    f"   Target: ₹{tgt} (50% decay) | SL: spot breaks {int(best['strike']):,}\n"
                    f"   ⏰ Exit by 3:15 PM regardless"
                )

    result  = "\n\n<b>🎯 0DTE SCALP SUGGESTIONS</b>"
    result += "".join(suggestions)
    result += "\n\n⚠️ 0DTE only — gamma risk high after 2:30 PM. No spreads suggested (bid-ask too wide)."
    result += "\n<i>For educational purposes only. Not investment advice.</i>"
    return result


# ── TRADE SUGGESTIONS ─────────────────────────────────────────────────────────

def get_trade_suggestions(rows, spot, atm, bias, iv_pct, dte):
    if dte == 0:
        return _get_0dte_suggestions(rows, spot, atm, bias)

    T = max(dte / 365, 0.5/365)
    r = 0.065
    suggestions = []

    if bias in ("BULLISH", "MILDLY BULLISH"):
        pe_candidates = [x for x in rows
                         if x['strike'] < spot
                         and x['pe_ltp'] >= MIN_PREMIUM
                         and x['pe_oi'] > 0]
        if pe_candidates:
            best = sorted(pe_candidates, key=lambda x: x['pe_oi'], reverse=True)[0]
            ltp  = best['pe_ltp']
            iv   = best['pe_iv'] / 100 if best['pe_iv'] > 0 else iv_pct / 100
            delta_abs = abs(_bs_delta(spot, best['strike'], T, r, iv, 'PE'))
            ev, pp = compute_ev(ltp, delta_abs)
            sl   = round(ltp * SL_MULTIPLIER, 1)
            ev_tag = "✅ +EV" if ev > 0 else "⚠️ -EV"
            suggestions.append(
                f"\n🟢 <b>SELL PE {int(best['strike']):,}</b> | LTP ₹{ltp} | OI {int(best['pe_oi']):,}\n"
                f"   SL ₹{sl} ({int(SL_MULTIPLIER)}× premium) | P(profit) {pp}% | EV ₹{ev} {ev_tag}\n"
                f"   ⚠️ Naked sell — do not carry overnight"
            )
        else:
            suggestions.append(f"\n⚠️ No tradeable PE strike (LTP < ₹{MIN_PREMIUM}) — wait for dip")

    elif bias == "BEARISH":
        ce_candidates = [x for x in rows
                         if x['strike'] > spot
                         and x['ce_ltp'] >= MIN_PREMIUM
                         and x['ce_oi'] > 0]
        if ce_candidates:
            best = sorted(ce_candidates, key=lambda x: x['ce_oi'], reverse=True)[0]
            ltp  = best['ce_ltp']
            iv   = best['ce_iv'] / 100 if best['ce_iv'] > 0 else iv_pct / 100
            delta_abs = abs(_bs_delta(spot, best['strike'], T, r, iv, 'CE'))
            ev, pp = compute_ev(ltp, delta_abs)
            sl   = round(ltp * SL_MULTIPLIER, 1)
            ev_tag = "✅ +EV" if ev > 0 else "⚠️ -EV"
            suggestions.append(
                f"\n🔴 <b>SELL CE {int(best['strike']):,}</b> | LTP ₹{ltp} | OI {int(best['ce_oi']):,}\n"
                f"   SL ₹{sl} ({int(SL_MULTIPLIER)}× premium) | P(profit) {pp}% | EV ₹{ev} {ev_tag}\n"
                f"   ⚠️ Naked sell — do not carry overnight"
            )
        else:
            suggestions.append(f"\n⚠️ No tradeable CE strike (LTP < ₹{MIN_PREMIUM}) — wait for bounce")

    else:  # NEUTRAL
        pe_candidates = [x for x in rows if x['strike'] < spot and x['pe_ltp'] >= MIN_PREMIUM and x['pe_oi'] > 0]
        ce_candidates = [x for x in rows if x['strike'] > spot and x['ce_ltp'] >= MIN_PREMIUM and x['ce_oi'] > 0]
        for label, candidates, opt_type, ltp_key, oi_key, iv_key in [
            ("PE", pe_candidates, "PE", "pe_ltp", "pe_oi", "pe_iv"),
            ("CE", ce_candidates, "CE", "ce_ltp", "ce_oi", "ce_iv"),
        ]:
            if candidates:
                best = sorted(candidates, key=lambda x: x[oi_key], reverse=True)[0]
                ltp  = best[ltp_key]
                iv   = best[iv_key] / 100 if best[iv_key] > 0 else iv_pct / 100
                delta_abs = abs(_bs_delta(spot, best['strike'], T, r, iv, opt_type))
                ev, pp = compute_ev(ltp, delta_abs)
                sl   = round(ltp * SL_MULTIPLIER, 1)
                ev_tag = "✅ +EV" if ev > 0 else "⚠️ -EV"
                color = "🟢" if label == "PE" else "🔴"
                suggestions.append(
                    f"\n{color} <b>SELL {label} {int(best['strike']):,}</b> | LTP ₹{ltp} | OI {int(best[oi_key]):,}\n"
                    f"   SL ₹{sl} ({int(SL_MULTIPLIER)}× premium) | P(profit) {pp}% | EV ₹{ev} {ev_tag}\n"
                    f"   ⚠️ Naked sell — do not carry overnight"
                )

    # ── Credit spreads ─────────────────────────────────────────────────────
    spread_lines = []

    def find_spreads(opt_type, ltp_key, oi_key, iv_key, filter_fn):
        candidates = []
        r_rate = 0.065
        for row in rows:
            if not filter_fn(row): continue
            ltp_s = row[ltp_key]
            if ltp_s < MIN_CREDIT: continue
            K_long = row['strike'] - SPREAD_WIDTH if opt_type == 'PE' else row['strike'] + SPREAD_WIDTH
            hedge = next((x for x in rows if x['strike'] == K_long), None)
            if not hedge: continue
            ltp_l = hedge[ltp_key]
            credit = round(ltp_s - ltp_l, 2)
            if credit < MIN_CREDIT: continue
            max_loss = round(SPREAD_WIDTH - credit, 2)
            iv_val   = row[iv_key] / 100 if row[iv_key] > 0 else iv_pct / 100
            delta_abs = abs(_bs_delta(spot, row['strike'], T, r_rate, iv_val, opt_type))
            p_profit  = 1 - delta_abs
            ev = round((p_profit * credit) - (delta_abs * max_loss), 2)
            rr = round(max_loss / credit, 1)
            lot_credit  = round(credit * LOT_SIZE)
            lot_ml      = round(max_loss * LOT_SIZE)
            ev_tag = "✅ +EV" if ev > 0 else "⚠️ -EV"
            candidates.append({
                'sell': int(row['strike']), 'buy': int(K_long),
                'credit': credit, 'max_loss': max_loss,
                'ev': ev, 'rr': rr, 'p_profit': round(p_profit*100,1),
                'lot_credit': lot_credit, 'lot_ml': lot_ml,
                'ev_tag': ev_tag, 'opt_type': opt_type,
            })
        return sorted(candidates, key=lambda x: x['ev'], reverse=True)

    if bias in ("BULLISH", "MILDLY BULLISH"):
        spreads = find_spreads('PE', 'pe_ltp', 'pe_oi', 'pe_iv',
                               lambda x: x['strike'] < spot and x['pe_oi'] > 0)
        if not spreads:
            spread_lines.append(f"\n📐 No PE spread with credit ≥ ₹{MIN_CREDIT} — wait for better premium or skip")
    elif bias == "BEARISH":
        spreads = find_spreads('CE', 'ce_ltp', 'ce_oi', 'ce_iv',
                               lambda x: x['strike'] > spot and x['ce_oi'] > 0)
        if not spreads:
            spread_lines.append(f"\n📐 No CE spread with credit ≥ ₹{MIN_CREDIT} — wait for better premium or skip")
    else:
        pe_sp = find_spreads('PE', 'pe_ltp', 'pe_oi', 'pe_iv',
                             lambda x: x['strike'] < spot and x['pe_oi'] > 0)
        ce_sp = find_spreads('CE', 'ce_ltp', 'ce_oi', 'ce_iv',
                             lambda x: x['strike'] > spot and x['ce_oi'] > 0)
        spreads = (pe_sp[:1] + ce_sp[:1])

    if spreads:
        ic_tag = " (Iron Condor)" if bias not in ("BULLISH", "MILDLY BULLISH", "BEARISH") else ""
        spread_lines.append(f"\n📐 <b>Credit Spread — 500pt width{ic_tag}</b>")
        for s in spreads[:2]:
            spread_lines.append(
                f"  Sell {s['sell']:,}{s['opt_type']} / Buy {s['buy']:,}{s['opt_type']}\n"
                f"  Credit ₹{s['credit']} (₹{s['lot_credit']}/lot) | Max loss ₹{s['max_loss']} (₹{s['lot_ml']}/lot)\n"
                f"  R:R 1:{s['rr']} | P(profit) {s['p_profit']}% | EV ₹{s['ev']} {s['ev_tag']}"
            )
        spread_lines.append(f"  ✅ Risk defined — can be carried overnight. Max loss capped at spread width.")
    elif not spread_lines:
        spread_lines.append(f"\n📐 No spread with credit ≥ ₹{MIN_CREDIT} — premium too thin at current levels")

    # ── Bias flip exit warning ──────────────────────────────────────────────
    exit_warning = []
    if bias in ("BULLISH", "MILDLY BULLISH"):
        exit_warning.append(
            "\n\n⚡ <b>Bias flip alert:</b> If bias turns BEARISH → exit any open PE sells/spreads immediately."
        )
    elif bias == "BEARISH":
        exit_warning.append(
            "\n\n⚡ <b>Bias flip alert:</b> If bias turns BULLISH → exit any open CE sells/spreads immediately."
        )
    else:
        exit_warning.append(
            "\n\n⚡ <b>Bias flip alert:</b> If bias turns directional → exit the against-bias IC leg immediately."
        )

    result  = "\n\n<b>🎯 TRADE SUGGESTIONS</b>"
    result += "".join(suggestions)
    result += "\n" + "\n".join(spread_lines)
    result += "".join(exit_warning)
    result += "\n\n<i>For educational purposes only. Not investment advice.</i>"
    return result


# ── X THREAD + CHANNEL MESSAGE ───────────────────────────────────────────────

def build_channel_msg(rows, spot, atm, pcr, mp, iv, wm, bias, dte, ce_top, pe_top, suggestions_text=""):
    now        = datetime.now().strftime("%d %b %Y %H:%M")
    bias_emoji = "📈" if "BULL" in bias else "📉" if "BEAR" in bias else "⚖️"
    dte_label  = "Expiry today" if dte == 0 else f"DTE: {dte}"

    ce_lines = "\n".join(f"  {int(r['strike']):,} CE — {fmt_oi(r['ce_oi'])}" for r in ce_top)
    pe_lines = "\n".join(f"  {int(r['strike']):,} PE — {fmt_oi(r['pe_oi'])}" for r in pe_top)

    pcr_raw = get_pcr_analysis(rows, spot, pcr)
    pcr_clean = (pcr_raw.replace("<b>","").replace("</b>","")
                        .replace("<i>","").replace("</i>","").strip())
    pcr_section = f"\n━━━━━━━━━━━━━━━━━━━━━━\n{pcr_clean}\n"

    clean_suggestions = (suggestions_text
        .replace("<b>","").replace("</b>","")
        .replace("<i>","").replace("</i>","")
        .strip())

    suggestions_section = (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>TRADE SUGGESTIONS</b>\n"
        f"{clean_suggestions}\n"
    ) if clean_suggestions else ""

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 <b>BANKNIFTY INTRADAY UPDATE</b>\n"
        f"{now} | {dte_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📍 Spot: <b>{spot:,.0f}</b> | ATM: <b>{int(atm):,}</b>\n"
        f"PCR: <b>{pcr}</b> {bias_emoji} | Max Pain: <b>{mp:,}</b>\n"
        f"IV: <b>{iv}%</b> | Range: <b>{int(spot-wm):,}–{int(spot+wm):,}</b>\n\n"
        f"🔴 <b>Resistance</b>\n{ce_lines}\n\n"
        f"🟢 <b>Support</b>\n{pe_lines}\n"
        f"{pcr_section}"
        f"{suggestions_section}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>For educational purposes only. Not investment advice.</i>\n"
        f"🔔 <b>@geomacrodigest</b>\n"
        f"#BankNifty #OptionsChain #Intraday #GeoMacroDigest"
    )


def build_x_thread(rows, spot, atm, pcr, mp, iv, wm, bias, dte, ce_top, pe_top, suggestions_text=""):
    now        = datetime.now().strftime("%d %b %Y %H:%M")
    bias_emoji = "📈" if "BULL" in bias else "📉" if "BEAR" in bias else "⚖️"
    dte_label  = "Expiry today" if dte == 0 else f"DTE {dte}"

    t1 = (
        f"🔍 BankNifty Options Update — {now}\n\n"
        f"Spot: {spot:,.0f} | ATM: {int(atm):,} | {dte_label}\n"
        f"PCR: {pcr} | Near-ATM PCR: {round(sum(r['pe_oi'] for r in [r for r in rows if abs(r['strike']-spot)<=1000]) / max(sum(r['ce_oi'] for r in [r for r in rows if abs(r['strike']-spot)<=1000]),1), 2) if rows else pcr}\n"
        f"Max Pain: {mp:,} | IV: {iv}% | Range: {int(spot-wm):,}–{int(spot+wm):,}\n\n"
        f"{bias_emoji} Bias: {bias}"
    )

    ce_str = " | ".join(f"{int(r['strike']):,}CE ({fmt_oi(r['ce_oi'])})" for r in ce_top)
    pe_str = " | ".join(f"{int(r['strike']):,}PE ({fmt_oi(r['pe_oi'])})" for r in pe_top)
    t2 = (
        f"📊 OI Walls\n\n"
        f"🔴 Resistance: {ce_str}\n\n"
        f"🟢 Support: {pe_str}"
    )

    res = ce_top[0]['strike'] if ce_top else 0
    sup = pe_top[0]['strike'] if pe_top else 0

    clean_sugg = (suggestions_text
        .replace("<b>","").replace("</b>","")
        .replace("<i>","").replace("</i>","")
        .strip())
    sugg_lines = [l for l in clean_sugg.split('\n') if l.strip()]
    sugg_short = "\n".join(sugg_lines)

    t3 = (
        f"🧠 What OI is saying:\n\n"
        f"{'Put writers defending ' + str(int(sup)) + ' — floor holding.' if 'BULL' in bias else 'Call writers defending ' + str(int(res)) + ' — ceiling strong.' if 'BEAR' in bias else 'Range locked ' + str(int(sup)) + '–' + str(int(res)) + '.'}\n\n"
        f"Break above {int(res):,} → next leg up\n"
        f"Break below {int(sup):,} → downside accelerates"
    )

    t4 = (
        f"{sugg_short}\n\n"
        f"📌 For educational purposes only. Not investment advice."
    ) if sugg_short else (
        f"📌 For educational purposes only. Not investment advice.\n\n"
        f"🌐 geomacrodigest.github.io/geomacrodigest\n"
        f"🔔 t.me/geomacrodigest\n\n"
        f"#BankNifty #OptionsChain #Intraday #GeoMacroDigest #NSE"
    )

    t5 = (
        f"🌐 geomacrodigest.github.io/geomacrodigest\n"
        f"🔔 t.me/geomacrodigest\n\n"
        f"#BankNifty #OptionsChain #Intraday #GeoMacroDigest #NSE"
    )

    return [t1, t2, t3, t4, t5] if sugg_short else [t1, t2, t3, t4]


def save_x_thread(tweets):
    with open(X_THREAD_FILE, 'w', encoding='utf-8') as f:
        for i, t in enumerate(tweets, 1):
            f.write(f"{'='*40}\nTWEET {i} ({len(t)} chars)\n{'='*40}\n{t}\n\n")
    return X_THREAD_FILE


# ── MAIN ANALYSIS ─────────────────────────────────────────────────────────────

def analyse(rows, spot, dte):
    now  = datetime.now().strftime("%d %b %Y %H:%M")
    atm  = min(rows, key=lambda x: abs(x["strike"] - spot))["strike"]
    tpe  = sum(r["pe_oi"] for r in rows)
    tce  = sum(r["ce_oi"] for r in rows)
    pcr  = round(tpe / tce, 2) if tce > 0 else 0
    stk  = [r["strike"] for r in rows]
    pain = [
        sum((s - r["strike"]) * r["ce_oi"] for r in rows if r["strike"] < s) +
        sum((r["strike"] - s) * r["pe_oi"] for r in rows if r["strike"] > s)
        for s in stk
    ]
    mp   = int(stk[pain.index(min(pain))])
    ar   = next((r for r in rows if r["strike"] == atm), {})
    iv   = round((ar.get("ce_iv", 0) + ar.get("pe_iv", 0)) / 2, 2)
    wm   = round(spot * iv / 100 / math.sqrt(52))
    ce_top = sorted([r for r in rows if r["strike"] >= atm], key=lambda x: x["ce_oi"], reverse=True)[:3]
    pe_top = sorted([r for r in rows if r["strike"] <= atm], key=lambda x: x["pe_oi"], reverse=True)[:3]
    ce_fr  = sorted([r for r in rows if r["ce_chg_oi"] > 0], key=lambda x: x["ce_chg_oi"], reverse=True)[:3]
    pe_fr  = sorted([r for r in rows if r["pe_chg_oi"] > 0], key=lambda x: x["pe_chg_oi"], reverse=True)[:3]

    if pcr > 1.2:
        bias = "BULLISH"
    elif pcr < 0.8:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    def fmt_ce(r):
        chg = fmt_chg_oi(r['ce_chg_oi'])
        chg_str = f"  (+{chg} fresh)" if chg else ""
        return f"  {int(r['strike']):,} CE — {fmt_oi(r['ce_oi'])}{chg_str}"
    def fmt_pe(r):
        chg = fmt_chg_oi(r['pe_chg_oi'])
        chg_str = f"  (+{chg} fresh)" if chg else ""
        return f"  {int(r['strike']):,} PE — {fmt_oi(r['pe_oi'])}{chg_str}"

    personal_msg = (
        f"<b>BankNifty Options — {now}</b>\n\n"
        f"<b>Spot:</b> {spot:,.0f}  |  <b>ATM:</b> {int(atm):,}\n"
        f"<b>PCR:</b> {pcr}  |  <b>Max Pain:</b> {mp:,}\n"
        f"<b>IV:</b> {iv}%  |  <b>Range:</b> {int(spot-wm):,}–{int(spot+wm):,}\n"
        f"<b>Bias:</b> {bias}  |  <b>DTE:</b> {dte}\n\n"
        f"<b>Resistance:</b>\n" + "\n".join(fmt_ce(r) for r in ce_top) + "\n\n"
        f"<b>Support:</b>\n" + "\n".join(fmt_pe(r) for r in pe_top) + "\n\n"
        f"<b>Fresh CE:</b>\n" + "\n".join(f"  {int(r['strike']):,} CE +{fmt_oi(r['ce_chg_oi'])}" for r in ce_fr if r['ce_chg_oi'] > 0) + "\n\n"
        f"<b>Fresh PE:</b>\n" + "\n".join(f"  {int(r['strike']):,} PE +{fmt_oi(r['pe_chg_oi'])}" for r in pe_fr if r['pe_chg_oi'] > 0)
        + get_pcr_analysis(rows, spot, pcr)
        + get_trade_suggestions(rows, spot, atm, bias, iv, dte)
    )

    channel_msg = build_channel_msg(rows, spot, atm, pcr, mp, iv, wm, bias, dte, ce_top, pe_top,
                                    get_trade_suggestions(rows, spot, atm, bias, iv, dte))
    x_tweets    = build_x_thread(rows, spot, atm, pcr, mp, iv, wm, bias, dte, ce_top, pe_top,
                                  get_trade_suggestions(rows, spot, atm, bias, iv, dte))

    return personal_msg, channel_msg, x_tweets, bias


# ── PCR ANALYSIS ─────────────────────────────────────────────────────────────

def get_pcr_analysis(rows, spot, pcr) -> str:
    atm = min(rows, key=lambda x: abs(x["strike"] - spot))["strike"]
    atm_row = next((r for r in rows if r["strike"] == atm), {})

    total_ce = sum(r["ce_oi"] for r in rows)
    total_pe = sum(r["pe_oi"] for r in rows)

    atm_ce_oi = atm_row.get("ce_oi", 0)
    atm_pe_oi = atm_row.get("pe_oi", 0)
    atm_pcr   = round(atm_pe_oi / atm_ce_oi, 2) if atm_ce_oi > 0 else 0

    fresh_ce = sum(r["ce_chg_oi"] for r in rows if r["ce_chg_oi"] > 0)
    fresh_pe = sum(r["pe_chg_oi"] for r in rows if r["pe_chg_oi"] > 0)
    fresh_ratio = round(fresh_pe / fresh_ce, 2) if fresh_ce > 0 else 0

    # Near-ATM: ±1000 pts for BankNifty (wider than Nifty's 500)
    near = [r for r in rows if abs(r["strike"] - spot) <= 1000]
    near_ce = sum(r["ce_oi"] for r in near)
    near_pe = sum(r["pe_oi"] for r in near)
    near_pcr = round(near_pe / near_ce, 2) if near_ce > 0 else 0

    if pcr >= 1.5:
        pcr_read = "Extremely bullish — heavy put writing, sellers confident floor is in"
        pcr_signal = "🟢🟢 STRONG BUY SIGNAL"
    elif pcr >= 1.2:
        pcr_read = "Bullish — put writers dominant, market likely to hold or grind up"
        pcr_signal = "🟢 BULLISH"
    elif pcr >= 1.0:
        pcr_read = "Mildly bullish — slight put OI edge, range-bound with upward tilt"
        pcr_signal = "🟡 MILDLY BULLISH"
    elif pcr >= 0.8:
        pcr_read = "Neutral to mildly bearish — call writers and put writers balanced"
        pcr_signal = "⚖️ NEUTRAL"
    elif pcr >= 0.6:
        pcr_read = "Bearish — call writers dominant, resistance likely to hold"
        pcr_signal = "🔴 BEARISH"
    else:
        pcr_read = "Extremely bearish — heavy call writing, sellers betting on cap"
        pcr_signal = "🔴🔴 STRONG RESISTANCE SIGNAL"

    if fresh_ratio >= 1.3:
        skew_read = f"Fresh PE > CE ({fresh_ratio}×) — new money defending downside → bullish lean"
    elif fresh_ratio <= 0.7:
        skew_read = f"Fresh CE > PE ({fresh_ratio}×) — new money capping upside → bearish lean"
    else:
        skew_read = f"Fresh OI balanced (ratio {fresh_ratio}) — no directional conviction in new positions"

    if near_pcr >= 1.2:
        near_read = f"Near-ATM PCR {near_pcr} → put writers protecting ±1000pt zone (bullish)"
    elif near_pcr <= 0.8:
        near_read = f"Near-ATM PCR {near_pcr} → call writers capping ±1000pt zone (bearish)"
    else:
        near_read = f"Near-ATM PCR {near_pcr} → balanced near spot (range-bound)"

    if pcr >= 1.2 and near_pcr >= 1.0 and fresh_ratio >= 1.0:
        suggestion = "✅ All three signals aligned BULLISH — sell PE or buy CE dips"
    elif pcr <= 0.8 and near_pcr <= 1.0 and fresh_ratio <= 1.0:
        suggestion = "✅ All three signals aligned BEARISH — sell CE or buy PE bounces"
    elif pcr >= 1.2 and fresh_ratio < 1.0:
        suggestion = "⚠️ Overall PCR bullish but fresh OI bearish — conflicting. Prefer spreads over naked"
    elif pcr <= 0.8 and fresh_ratio > 1.0:
        suggestion = "⚠️ Overall PCR bearish but fresh OI bullish — conflicting. Prefer spreads over naked"
    else:
        suggestion = "📐 Mixed signals — iron condor or stay flat until clearer print"

    return (
        f"\n\n<b>📊 PCR / CALL-PUT RATIO ANALYSIS</b>\n"
        f"  Overall PCR:   <b>{pcr}</b>  ({fmt_oi(total_pe/LOT_SIZE)} PE / {fmt_oi(total_ce/LOT_SIZE)} CE)\n"
        f"  Near-ATM PCR:  <b>{near_pcr}</b>  (±1000pts from spot)\n"
        f"  ATM PCR:       <b>{atm_pcr}</b>  ({int(atm):,} strike only)\n"
        f"  Fresh OI Ratio:<b>{fresh_ratio}</b>  (+PE chg / +CE chg)\n\n"
        f"  Signal: {pcr_signal}\n"
        f"  Read:   {pcr_read}\n"
        f"  Skew:   {skew_read}\n"
        f"  Zone:   {near_read}\n\n"
        f"  💡 {suggestion}"
    )


# ── HTML BUILDER ──────────────────────────────────────────────────────────────

def build_options_html(rows, spot, atm, pcr, mp, iv, wm, bias, dte, ce_top, pe_top,
                       ce_fr, pe_fr, personal_msg, now):
    bias_color = "#2d7a2d" if "BULL" in bias else "#b91c1c" if "BEAR" in bias else "#b45309"
    bias_emoji = "📈" if "BULL" in bias else "📉" if "BEAR" in bias else "⚖️"

    ce_rows = ""
    for r in ce_top:
        chg = fmt_chg_oi(r['ce_chg_oi'])
        ce_rows += f"<tr><td>{int(r['strike']):,} CE</td><td>{fmt_oi(r['ce_oi'])}</td><td style='color:#378ADD'>{'+'+chg if chg else '—'}</td><td>₹{r['ce_ltp']}</td></tr>"

    pe_rows = ""
    for r in pe_top:
        chg = fmt_chg_oi(r['pe_chg_oi'])
        pe_rows += f"<tr><td>{int(r['strike']):,} PE</td><td>{fmt_oi(r['pe_oi'])}</td><td style='color:#4caf50'>{'+'+chg if chg else '—'}</td><td>₹{r['pe_ltp']}</td></tr>"

    # OI distribution chart data (near ATM ±2000 for BankNifty)
    chart_strikes = [r for r in rows if abs(r['strike'] - spot) <= 2000]
    chart_labels  = [str(int(r['strike'])) for r in chart_strikes]
    chart_ce      = [int(r['ce_oi'] * LOT_SIZE) for r in chart_strikes]
    chart_pe      = [int(r['pe_oi'] * LOT_SIZE) for r in chart_strikes]

    suggestions_clean = personal_msg.split('🎯')[1] if '🎯' in personal_msg else ""
    suggestions_clean = suggestions_clean.replace('<b>','').replace('</b>','').replace('<i>','').replace('</i>','')

    # PCR HTML variables
    atm_row      = next((r for r in rows if r["strike"] == atm), {})
    near_rows    = [r for r in rows if abs(r["strike"] - spot) <= 1000]
    near_ce      = sum(r["ce_oi"] for r in near_rows)
    near_pe      = sum(r["pe_oi"] for r in near_rows)
    near_pcr_val = round(near_pe / near_ce, 2) if near_ce > 0 else 0
    atm_ce_oi    = atm_row.get("ce_oi", 0)
    atm_pe_oi    = atm_row.get("pe_oi", 0)
    atm_pcr_val  = round(atm_pe_oi / atm_ce_oi, 2) if atm_ce_oi > 0 else 0
    fresh_ce     = sum(r["ce_chg_oi"] for r in rows if r["ce_chg_oi"] > 0)
    fresh_pe_oi  = sum(r["pe_chg_oi"] for r in rows if r["pe_chg_oi"] > 0)
    fresh_r      = round(fresh_pe_oi / fresh_ce, 2) if fresh_ce > 0 else 0

    def _pcr_color(v): return "#2d7a2d" if v >= 1.1 else "#b91c1c" if v < 0.9 else "#b45309"
    pcr_color      = _pcr_color(pcr)
    near_pcr_color = _pcr_color(near_pcr_val)
    atm_pcr_color  = _pcr_color(atm_pcr_val)
    fresh_color    = "#2d7a2d" if fresh_r >= 1.1 else "#b91c1c" if fresh_r < 0.9 else "#b45309"

    if pcr >= 1.5:   pcr_signal_html, pcr_read_html = "🟢🟢 STRONG BUY", "Extremely bullish — heavy put writing"
    elif pcr >= 1.2: pcr_signal_html, pcr_read_html = "🟢 BULLISH", "Put writers dominant — market likely to hold or grind up"
    elif pcr >= 1.0: pcr_signal_html, pcr_read_html = "🟡 MILDLY BULLISH", "Slight put OI edge — range-bound with upward tilt"
    elif pcr >= 0.8: pcr_signal_html, pcr_read_html = "⚖️ NEUTRAL", "Balanced — call and put writers in equilibrium"
    elif pcr >= 0.6: pcr_signal_html, pcr_read_html = "🔴 BEARISH", "Call writers dominant — resistance likely to hold"
    else:            pcr_signal_html, pcr_read_html = "🔴🔴 STRONG RESISTANCE", "Extremely bearish — heavy call writing"

    skew_read_html = (f"Fresh PE > CE ({fresh_r}×) — new money defending downside" if fresh_r >= 1.3
                      else f"Fresh CE > PE ({fresh_r}×) — new money capping upside" if fresh_r <= 0.7
                      else f"Fresh OI balanced ({fresh_r}) — no directional conviction")
    near_read_html = (f"Near-ATM PCR {near_pcr_val} — put writers protecting zone (bullish)" if near_pcr_val >= 1.2
                      else f"Near-ATM PCR {near_pcr_val} — call writers capping zone (bearish)" if near_pcr_val <= 0.8
                      else f"Near-ATM PCR {near_pcr_val} — balanced near spot")

    if pcr >= 1.2 and near_pcr_val >= 1.0 and fresh_r >= 1.0:
        suggestion_html = "All signals BULLISH — sell PE or buy CE dips"
    elif pcr <= 0.8 and near_pcr_val <= 1.0 and fresh_r <= 1.0:
        suggestion_html = "All signals BEARISH — sell CE or buy PE bounces"
    elif pcr >= 1.2 and fresh_r < 1.0:
        suggestion_html = "PCR bullish but fresh OI bearish — conflicting. Prefer spreads"
    elif pcr <= 0.8 and fresh_r > 1.0:
        suggestion_html = "PCR bearish but fresh OI bullish — conflicting. Prefer spreads"
    else:
        suggestion_html = "Mixed signals — iron condor or stay flat until clearer print"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BankNifty Options Chain — {now}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fa;color:#1a1a1a;padding:20px;font-size:14px}}
  .wrap{{max-width:1200px;margin:0 auto}}
  h1{{font-size:20px;font-weight:600;margin-bottom:4px}}
  .sub{{color:#666;font-size:13px;margin-bottom:20px}}
  .nav{{display:flex;gap:10px;margin-bottom:20px}}
  .nav a{{font-size:12px;color:#378ADD;text-decoration:none;padding:5px 12px;border:1px solid #378ADD;border-radius:8px}}
  .grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:20px}}
  .metric{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px}}
  .metric .lbl{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}
  .metric .val{{font-size:22px;font-weight:600}}
  .row{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
  .card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px}}
  .card h3{{font-size:12px;font-weight:600;color:#666;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse}}
  th{{background:#f3f4f6;padding:8px 10px;text-align:left;font-size:11px;font-weight:500;color:#666}}
  td{{padding:8px 10px;border-bottom:1px solid #f0f0f0;font-size:13px}}
  .bias-tag{{display:inline-block;padding:4px 14px;border-radius:20px;font-size:13px;font-weight:600;background:{bias_color}20;color:{bias_color}}}
  .chart-wrap{{height:220px;position:relative}}
  .suggestions{{background:#f9fafb;border-radius:8px;padding:14px;font-size:13px;white-space:pre-wrap;line-height:1.7;color:#333}}
  .footer{{margin-top:16px;font-size:12px;color:#999;text-align:center}}
  .tag{{font-size:11px;color:#b45309;background:#b4530920;padding:2px 10px;border-radius:20px;margin-left:8px}}
  .bnk-badge{{display:inline-block;background:#1F4E7920;color:#1F4E79;font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;margin-left:8px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>🏦 BankNifty Options Chain Analysis <span class="bnk-badge">LOT: {LOT_SIZE} | SPREAD: {SPREAD_WIDTH}pts</span></h1>
  <p class="sub">Generated: {now} &nbsp;|&nbsp; DTE: {dte} &nbsp;|&nbsp; Spot: {spot:,.0f}
    <span class="tag">Every 2 hours during market hours</span></p>

  <div class="nav">
    <a href="index.html">🏠 Home</a>
    <a href="options_chain.html">📊 Nifty Options</a>
    <a href="index_nifty.html">📈 EOD Dashboard</a>
    <a href="intraday.html">⚡ Stock Scanner</a>
  </div>

  <div class="grid">
    <div class="metric"><div class="lbl">ATM</div><div class="val" style="color:#378ADD">{int(atm):,}</div></div>
    <div class="metric"><div class="lbl">PCR</div><div class="val" style="color:{'#2d7a2d' if pcr>=1.1 else '#b91c1c' if pcr<0.9 else '#b45309'}">{pcr}</div></div>
    <div class="metric"><div class="lbl">Max Pain</div><div class="val" style="color:#b45309">{mp:,}</div></div>
    <div class="metric"><div class="lbl">IV</div><div class="val">{iv}%</div></div>
    <div class="metric"><div class="lbl">Range</div><div class="val" style="font-size:15px">{int(spot-wm):,}–{int(spot+wm):,}</div></div>
    <div class="metric"><div class="lbl">Bias</div><div class="val"><span class="bias-tag">{bias_emoji} {bias}</span></div></div>
  </div>

  <div class="row">
    <div class="card">
      <h3>🔴 CE Wall — Resistance</h3>
      <table><thead><tr><th>Strike</th><th>OI</th><th>Fresh</th><th>LTP</th></tr></thead>
      <tbody>{ce_rows}</tbody></table>
    </div>
    <div class="card">
      <h3>🟢 PE Wall — Support</h3>
      <table><thead><tr><th>Strike</th><th>OI</th><th>Fresh</th><th>LTP</th></tr></thead>
      <tbody>{pe_rows}</tbody></table>
    </div>
  </div>

  <div class="card" style="margin-bottom:20px">
    <h3>OI Distribution — CE vs PE (near ATM ±2000pts)</h3>
    <div class="chart-wrap"><canvas id="oiChart"></canvas></div>
  </div>

  <div class="card" style="margin-bottom:20px">
    <h3>📊 PCR / Call-Put Ratio Analysis</h3>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px">
      <div style="background:#f9fafb;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:11px;color:#888;margin-bottom:4px">OVERALL PCR</div>
        <div style="font-size:22px;font-weight:700;color:{pcr_color}">{pcr}</div>
      </div>
      <div style="background:#f9fafb;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:11px;color:#888;margin-bottom:4px">NEAR-ATM PCR (±1000)</div>
        <div style="font-size:22px;font-weight:700;color:{near_pcr_color}">{near_pcr_val}</div>
      </div>
      <div style="background:#f9fafb;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:11px;color:#888;margin-bottom:4px">ATM PCR</div>
        <div style="font-size:22px;font-weight:700;color:{atm_pcr_color}">{atm_pcr_val}</div>
      </div>
      <div style="background:#f9fafb;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:11px;color:#888;margin-bottom:4px">FRESH OI RATIO</div>
        <div style="font-size:22px;font-weight:700;color:{fresh_color}">{fresh_r}</div>
      </div>
    </div>
    <div style="background:#f9fafb;border-radius:8px;padding:12px;font-size:13px;line-height:1.8">
      <b>Signal:</b> {pcr_signal_html}<br>
      <b>Read:</b> {pcr_read_html}<br>
      <b>Fresh OI:</b> {skew_read_html}<br>
      <b>Near Zone:</b> {near_read_html}<br>
      <b style="color:#1F4E79">💡 {suggestion_html}</b>
    </div>
    <p style="font-size:11px;color:#999;margin-top:8px">For educational purposes only. Not investment advice.</p>
  </div>

  <div class="card" style="margin-bottom:20px">
    <h3>🎯 Trade Suggestions</h3>
    <div class="suggestions">{suggestions_clean}</div>
    <p style="font-size:11px;color:#999;margin-top:8px">For educational purposes only. Not investment advice.</p>
  </div>

  <div class="footer">Data: NSE Options Chain (CSV) &nbsp;·&nbsp; BankNifty Lot: {LOT_SIZE} | Spread Width: {SPREAD_WIDTH}pts &nbsp;·&nbsp; For educational purposes only</div>
</div>

<script>
const labels = {chart_labels};
const ceData = {chart_ce};
const peData = {chart_pe};
new Chart(document.getElementById('oiChart'), {{
  type: 'bar',
  data: {{
    labels,
    datasets: [
      {{label:'CE OI (L)', data:ceData, backgroundColor:'#378ADD80', borderColor:'#378ADD', borderWidth:1}},
      {{label:'PE OI (L)', data:peData, backgroundColor:'#D4537E80', borderColor:'#D4537E', borderWidth:1}}
    ]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{display:true,labels:{{font:{{size:11}}}}}}}},
    scales:{{
      x:{{grid:{{display:false}},ticks:{{font:{{size:10}},maxRotation:45}}}},
      y:{{ticks:{{font:{{size:10}}}}}}
    }}
  }}
}});
</script>
</body>
</html>"""


# ── GITHUB DEPLOY ─────────────────────────────────────────────────────────────

def upload_to_github(html_file: str):
    def sha(f):
        r = requests.get(f"{GITHUB_URL}/{f}",
                         headers={"Authorization": f"token {GITHUB_TOKEN}",
                                  "Accept": "application/vnd.github.v3+json"}, timeout=10)
        return r.json().get("sha") if r.status_code == 200 else None

    def put(f, data):
        s = sha(f)
        p = {"message": f"update {f}",
             "content": base64.b64encode(data if isinstance(data, bytes) else data.encode()).decode()}
        if s: p["sha"] = s
        r = requests.put(f"{GITHUB_URL}/{f}",
                         headers={"Authorization": f"token {GITHUB_TOKEN}",
                                  "Accept": "application/vnd.github.v3+json"},
                         json=p, timeout=30)
        if r.status_code not in (200, 201):
            print(f"    Error {r.status_code}: {r.text[:150]}")
        return r.status_code in (200, 201)

    print("  Deploying to GitHub Pages...")
    base = BANKNIFTY_DASHBOARD_DIR if os.path.exists(BANKNIFTY_DASHBOARD_DIR) else os.path.dirname(html_file)
    pages = {}
    with open(html_file, 'rb') as f:
        pages["banknifty_chain.html"] = f.read()

    # Also push companion pages if they exist alongside this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for fname, zname in [
        ("nifty_dashboard.html",    "index_nifty.html"),
        ("scanner_dashboard.html",  "scanner.html"),
        ("intraday_scanner.html",   "intraday.html"),
        ("options_chain.html",      "options_chain.html"),
        ("index.html",              "index.html"),
    ]:
        for search_dir in [base, script_dir]:
            p = os.path.join(search_dir, fname)
            if os.path.exists(p):
                with open(p, 'rb') as f:
                    pages[zname] = f.read()
                break

    for f, d in pages.items():
        ok = put(f, d)
        print(f"  {'✅' if ok else '⚠️'} {f}")
    print(f"  🌐 {PAGES_BASE}/banknifty_chain.html")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

def main():
    print("=" * 50 + "\n  BankNifty Options Analyser — CSV Mode\n" + "=" * 50)

    if not os.path.exists(CSV_FILE):
        print(f"\n  CSV not found: {CSV_FILE}")
        print("  1. nseindia.com/option-chain")
        print("  2. Select BANKNIFTY → nearest expiry")
        print("  3. Download CSV → save as banknifty_chain.csv in same folder")
        return

    mod = datetime.fromtimestamp(os.path.getmtime(CSV_FILE))
    print(f"\n  CSV updated: {mod.strftime('%H:%M:%S')}")

    rows = parse_csv(CSV_FILE)
    print(f"  Parsed {len(rows)} strikes")

    spot = float(input("\n  Enter BankNifty spot: ").strip().replace(",", ""))

    print("  Enter expiry date (e.g. 11 Jun 2026 or 11/06/2026): ", end="")
    exp_str = input().strip()
    try:
        for fmt in ("%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y"):
            try:
                expiry_date = datetime.strptime(exp_str, fmt).date()
                break
            except:
                continue
        dte = trading_days_until(expiry_date)
        today_is_expiry = (expiry_date == date.today())
        if today_is_expiry:
            dte = 0
        print(f"  ✅ Expiry: {expiry_date.strftime('%d %b %Y')} | Trading DTE: {dte} (weekends & holidays excluded)")
    except Exception:
        print("  ⚠️  Could not parse date — falling back to manual entry")
        dte = int(input("  Enter DTE manually: ").strip())

    personal_msg, channel_msg, x_tweets, bias = analyse(rows, spot, dte)

    clean = lambda s: s.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")
    print("\n" + clean(personal_msg))

    # Build HTML dashboard
    now = datetime.now().strftime("%d %b %Y %H:%M")
    atm     = min(rows, key=lambda x: abs(x["strike"]-spot))["strike"]
    tpe     = sum(r["pe_oi"] for r in rows)
    tce     = sum(r["ce_oi"] for r in rows)
    pcr     = round(tpe/tce,2) if tce>0 else 0
    stk     = [r["strike"] for r in rows]
    pain    = [sum((s-r["strike"])*r["ce_oi"] for r in rows if r["strike"]<s)+
               sum((r["strike"]-s)*r["pe_oi"] for r in rows if r["strike"]>s) for s in stk]
    mp      = int(stk[pain.index(min(pain))])
    ar      = next((r for r in rows if r["strike"]==atm),{})
    iv      = round((ar.get("ce_iv",0)+ar.get("pe_iv",0))/2,2)
    wm      = round(spot*iv/100/math.sqrt(52))
    ce_top  = sorted([r for r in rows if r["strike"]>=atm],key=lambda x:x["ce_oi"],reverse=True)[:5]
    pe_top  = sorted([r for r in rows if r["strike"]<=atm],key=lambda x:x["pe_oi"],reverse=True)[:5]
    ce_fr   = sorted([r for r in rows if r["ce_chg_oi"]>0],key=lambda x:x["ce_chg_oi"],reverse=True)[:3]
    pe_fr   = sorted([r for r in rows if r["pe_chg_oi"]>0],key=lambda x:x["pe_chg_oi"],reverse=True)[:3]

    print("\n  Building HTML dashboard...")
    html = build_options_html(rows, spot, atm, pcr, mp, iv, wm, bias, dte,
                              ce_top, pe_top, ce_fr, pe_fr, personal_msg, now)

    os.makedirs(os.path.dirname(HTML_FILE) if os.path.dirname(HTML_FILE) else ".", exist_ok=True)
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Saved → {HTML_FILE}")

    upload_to_github(HTML_FILE)

    thread_file = save_x_thread(x_tweets)
    print(f"\n  X thread saved → {thread_file}")

    if input("\n  Send to Telegram? (y/n): ").strip().lower() == "y":
        print("  Sending to personal chat...")
        send_telegram(personal_msg)
        print("  Sending to @geomacrodigest channel...")
        send_telegram_to(CHANNEL_ID, channel_msg)
        print("  ✅ Done")


if __name__ == "__main__":
    main()
