# Pipeline-GFS
Automate the full “data → plot → deliver” workflow for NOAA’s **Global Forecast System (GFS)**:

1. **Download** regional GRIB2 files straight from the NOMADS server (`GFS.py`).
2. **Post‑process & plot** 2 m temperature, 10 m wind, 1000–500 hPa thickness + sea‑level pressure, and total precipitation (`forecast.py`).
3. **Package & e‑mail** the resulting PNGs as a single ZIP archive (`pipeline.py`).

The default domain covers South America ( 80°S–18°N, 93°W–25°W ), but any bounding box can be set by editing **`GFS.py`**. :contentReference[oaicite:0]{index=0}

---

## Features
- 🔁 **Idempotent** — skips the download step when fresh data (≤ 6 h) already exist. :contentReference[oaicite:1]{index=1}  
- 🗺️ **High‑quality cartography** with Cartopy and custom color maps (temperature, precip, thickness). :contentReference[oaicite:2]{index=2}  
- ✉️ **Secure mail delivery** (SSL) with configurable sender/recipients and `EMAIL_PASSWORD` env‑var fallback. :contentReference[oaicite:3]{index=3}  
- 🐚 **CLI‑first**: every option—resolution, run cycle, max‑age, SMTP server—available as flags.  
- 🛠️ **Composable**: each stage can be run stand‑alone or orchestrated end‑to‑end.

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/<user>/gfs-forecast-pipeline.git
cd gfs-forecast-pipeline

# 2. Create environment (Python ≥ 3.9)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # see list below

# 3. Run the full pipeline
python pipeline.py --send-email \
  --sender "you@example.com" \
  --recipients "team@example.com" \
  --subject "Latest GFS maps"
