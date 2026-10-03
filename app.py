import asyncio
import os
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import pandas as pd
import yfinance as yf

app = FastAPI(title="SWING5D Standalone Clone")

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

async def cron_loop():
    while True:
        try:
            scan_stocks()
        except Exception as e:
            print("Scan error:", e)
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    if not os.path.exists(DATA_FILE):
        scan_stocks()
    asyncio.create_task(cron_loop())

HTML_UI = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SWING5D - Serverless Mirror</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <div class="max-w-6xl mx-auto px-4 py-8">
    <header class="flex justify-between items-center border-b border-slate-800 pb-4 mb-8">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-emerald-400">SWING5D</h1>
        <p class="text-xs text-slate-400">Horizon Swing 1–5 Hari | IHSG Liquid</p>
      </div>
      <div id="last-update" class="text-xs text-slate-500 font-mono">Memuat data...</div>
    </header>

    <section class="mb-8">
      <div class="flex justify-between items-center mb-4">
        <div>
          <h2 class="text-lg font-semibold text-slate-200">Watchlist Saham Liquid & Buy Zone</h2>
          <p class="text-sm text-slate-400">Disaring berdasarkan Likuiditas (AvgVol20 &ge; 1M), RRR &ge; 1.5x</p>
        </div>
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
          Auto-Scan 5m Aktif
        </span>
      </div>
      
      <div class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60">
        <table class="w-full text-left text-sm">
          <thead class="bg-slate-900 text-slate-400 text-xs uppercase border-b border-slate-800">
            <tr>
              <th class="px-4 py-3">Ticker</th>
              <th class="px-4 py-3">Close</th>
              <th class="px-4 py-3">Potensi</th>
              <th class="px-4 py-3">Risiko</th>
              <th class="px-4 py-3">RRR</th>
              <th class="px-4 py-3">Zona</th>
              <th class="px-4 py-3">Likuiditas</th>
              <th class="px-4 py-3">Plan (TP/SL)</th>
            </tr>
          </thead>
          <tbody id="table-body" class="divide-y divide-slate-800">
            <tr><td colspan="8" class="text-center py-6 text-slate-500">Memuat hasil screening...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <footer class="text-center text-xs text-slate-600 border-t border-slate-900 pt-6 mt-12">
      SWING5D Standalone Engine &bull; Render Cloud
    </footer>
  </div>

  <script>
    async function loadData() {
      try {
        const res = await fetch('/api/screener');
        const json = await res.json();
        document.getElementById('last-update').innerText = 'Update: ' + (json.updated_at || '-');
        const tbody = document.getElementById('table-body');
        tbody.innerHTML = '';

        if (!json.data || json.data.length === 0) {
          tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-500">Tidak ada emiten di Buy Zone saat ini.</td></tr>';
          return;
        }

        json.data.forEach(item => {
          const tr = document.createElement('tr');
          tr.className = "hover:bg-slate-800/40 transition";
          
          let zoneBadge = "bg-slate-800 text-slate-300";
          if (item.zone === "IN_BUY_ZONE") zoneBadge = "bg-emerald-950 text-emerald-300 border border-emerald-800";
          else if (item.zone === "BREAKOUT") zoneBadge = "bg-blue-950 text-blue-300 border border-blue-800";
          else if (item.zone === "HOLD") zoneBadge = "bg-amber-950 text-amber-300 border border-amber-800";

          tr.innerHTML = `
            <td class="px-4 py-3 font-bold text-white">${item.symbol}</td>
            <td class="px-4 py-3 font-mono">${item.close.toLocaleString('id-ID')}</td>
            <td class="px-4 py-3 font-semibold text-emerald-400">+${item.potensi_naik}%</td>
            <td class="px-4 py-3 font-semibold text-rose-400">-${item.risiko_turun}%</td>
            <td class="px-4 py-3 font-mono text-cyan-300">${item.rrr}x</td>
            <td class="px-4 py-3"><span class="px-2 py-0.5 rounded text-xs ${zoneBadge}">${item.zone}</span></td>
            <td class="px-4 py-3 text-xs text-slate-400">${item.liquidity}</td>
            <td class="px-4 py-3 text-xs font-mono text-slate-300">TP: ${item.tp} | SL: ${item.sl}</td>
          `;
          tbody.appendChild(tr);
        });
      } catch (e) {
        document.getElementById('table-body').innerHTML = '<tr><td colspan="8" class="text-center py-6 text-rose-500">Gagal memuat data screener.</td></tr>';
      }
    }
    loadData();
    setInterval(loadData, 60000);
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML_UI)

@app.get("/api/screener")
async def get_screener():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"data": []}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
