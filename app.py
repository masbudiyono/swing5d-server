import asyncio
import os
import json
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import pandas as pd
import yfinance as yf

app = FastAPI(title="SWING5D Standalone Clone")
templates = Jinja2Templates(directory="templates")

# Cache data di memori / file
DATA_FILE = "data/screener.json"
os.makedirs("data", exist_ok=True)

WATCHLIST = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "ASII.JK", "TLKM.JK",
    "ADRO.JK", "PTBA.JK", "UNTR.JK", "MEDC.JK", "PGAS.JK", "AKRA.JK",
    "MAPI.JK", "ACES.JK", "AMRT.JK", "ICBP.JK", "INDF.JK", "MYOR.JK",
    "CPIN.JK", "JPFA.JK", "KLBF.JK", "INKP.JK", "TKIM.JK", "SMGR.JK",
    "INTP.JK", "ANTM.JK", "INCO.JK", "MDKA.JK", "TINS.JK", "BSSR.JK",
    "BRIS.JK", "BSDE.JK", "CTRA.JK", "PWON.JK", "SMRA.JK", "GOTO.JK"
]

def scan_stocks():
    results = []
    for ticker in WATCHLIST:
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="60d")
            if len(df) < 25:
                continue

            close = float(df['Close'].iloc[-1])
            vol20 = float(df['Volume'].iloc[-20:].mean())
            val20 = float((df['Close'] * df['Volume']).iloc[-20:].mean())

            is_very_liquid = vol20 >= 5_000_000 and val20 >= 25_000_000_000
            is_liquid = vol20 >= 1_000_000 or val20 >= 10_000_000_000
            if not (is_liquid or is_very_liquid):
                continue

            ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
            low20 = float(df['Low'].iloc[-20:].min())
            high20 = float(df['High'].iloc[-20:].max())

            sl = round(max(low20, close * 0.95), 0)
            tp = round(min(high20 * 1.05, close * 1.10), 0)
            risk = max(1.0, close - sl)
            reward = max(1.0, tp - close)
            rrr = round(reward / risk, 2)

            if close > high20 * 0.99:
                zone = "BREAKOUT"
            elif close <= ma20 * 1.02 and close >= ma20 * 0.97:
                zone = "IN_BUY_ZONE"
            elif close > ma20 * 1.02:
                zone = "HOLD"
            else:
                zone = "SELL"

            results.append({
                "symbol": ticker.replace(".JK", ""),
                "close": int(close),
                "potensi_naik": round(((tp - close) / close) * 100, 1),
                "risiko_turun": round(((close - sl) / close) * 100, 1),
                "liquidity": "Very Liquid" if is_very_liquid else "Liquid",
                "zone": zone,
                "pred": "UP" if close >= ma20 else "DOWN",
                "rrr": rrr,
                "tp": int(tp),
                "sl": int(sl)
            })
        except Exception:
            continue

    results.sort(key=lambda x: (x['zone'] == 'IN_BUY_ZONE', x['rrr'] >= 1.5, x['potensi_naik']), reverse=True)
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB"),
        "total_screened": len(WATCHLIST),
        "data": results
    }
    with open(DATA_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    return payload

# Background task per 5 menit
async def cron_loop():
    while True:
        try:
            scan_stocks()
        except Exception as e:
            print("Scan error:", e)
        await asyncio.sleep(300) # 5 menit

@app.on_event("startup")
async def startup_event():
    if not os.path.exists(DATA_FILE):
        scan_stocks()
    asyncio.create_task(cron_loop())

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
    return templates.TemplateResponse("index.html", {"request": request, "payload": data})

@app.get("/api/screener")
async def get_screener():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"data": []}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=10000, reload=False)
