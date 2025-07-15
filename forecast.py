import os
from glob import glob
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import metpy.calc as mpcalc
import numpy as np
import pandas as pd
import xarray as xr
from metpy.units import units
import warnings
warnings.filterwarnings("ignore")

###############################################################################
# CONFIG                                                                      #
###############################################################################

INPUT_DIR = "/PUT/YOUR/PATH"
OUTPUT_DIR = "/PUT/YOUR/PATH"
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

EXTENT = (-80, -30, -60, 5) 

QUIVER_EVERY = 5  

import cmaps  
TEMP_CMAP = cmaps.temp_19lev
PRECIP_CMAP = cmaps.WhiteBlueGreenYellowRed
THICKNESS_CMAP = cmaps.BlueYellowRed
TEMP_LEVELS = np.arange(-5, 45, 1)  # °C
PRECIP_LEVELS = np.arange(1, 65, 5)  # mm
THICKNESS_LEVELS = np.arange(490,590,5) # dam
PRESSURE_LEVELS= np.arange(990,1030,3) # hPa

###############################################################################
# FUNCTIONS                                                                   #
###############################################################################

def _open_var(file: str | os.PathLike, short_name: str, **kw):
    return xr.open_dataset(
        file,
        engine="cfgrib",
        filter_by_keys={"shortName": short_name, **kw},
        backend_kwargs={"indexpath": ""},
    ).metpy.parse_cf()


def _format_datetime(time_val) -> tuple[str, str]:
    dt = pd.to_datetime(str(time_val))
    return dt.strftime("%Y%m%d_%H"), dt.strftime("%d %b %Y %H:%M UTC")


def _save(fig: plt.Figure, filename: str):
    out_path = Path(OUTPUT_DIR) / filename
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    try:
        rel = out_path.relative_to(Path.cwd())
    except ValueError:
        rel = out_path
    print(f" → {rel}")

###############################################################################
# MAIN                                                                        #
###############################################################################

grib_files = sorted(glob(os.path.join(INPUT_DIR, "gfs.t??z.pgrb2.0p25.f*")))
if not grib_files:
    raise FileNotFoundError(f"No GFS files found in {INPUT_DIR!s}.")

for grib in grib_files:
    base = os.path.basename(grib)
    print(f"Processing {base} …")
    try:
###############################################################################
# 2 METRE TEMPERATURE                                                         #
###############################################################################        
        t_ds = _open_var(grib, "2t", typeOfLevel="heightAboveGround")
        t = t_ds["t2m"].metpy.convert_units("degC")
        lat = t_ds["latitude"]
        lon = t_ds["longitude"]
        data_str, human_date = _format_datetime(t_ds["valid_time"].values)

        proj = ccrs.PlateCarree()
        fig, ax = plt.subplots(figsize=(12, 10), subplot_kw={"projection": proj})
        ax.set_extent(EXTENT, crs=proj)
        cf = ax.contourf(lon, lat, t, levels=TEMP_LEVELS, cmap=TEMP_CMAP, extend="both")
        cs = ax.contour(lon, lat, t, colors='white', linewidths=0.1, levels=TEMP_LEVELS)
        ax.coastlines("10m", linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5)
        gl = ax.gridlines(crs=ccrs.PlateCarree(), color='gray', alpha=1.0, linestyle='--', linewidth=0.25,
                          xlocs=np.arange(-180, 180, 10), ylocs=np.arange(-90, 90, 10), draw_labels=True)
        gl.top_labels = False
        gl.right_labels = False
        ax.set_title("2 Metre Temperature (°C)", loc="left", fontsize=10)
        ax.set_title(human_date, loc="right", fontsize=10)
        cbar = fig.colorbar(cf, ax=ax, orientation="vertical", pad=0.01, fraction=0.03)
        cbar.set_label("Temperature (°C)")
        _save(fig, f"Temp2m_{data_str}.png")
        
###############################################################################
# 10 METRE WIND SPEED                                                         #
###############################################################################

        u_ds = _open_var(grib, "10u", typeOfLevel="heightAboveGround")
        v_ds = _open_var(grib, "10v", typeOfLevel="heightAboveGround")
        u = u_ds["u10"].metpy.convert_units("m/s")
        v = v_ds["v10"].metpy.convert_units("m/s")
        wspd = mpcalc.wind_speed(u, v).metpy.convert_units("m/s")
        

        fig, ax = plt.subplots(figsize=(12, 10), subplot_kw={"projection": proj})
        ax.set_extent(EXTENT, crs=proj)
        spd_cf = ax.contourf(lon, lat, wspd, levels=np.arange(0, 24, 2), cmap="Oranges", extend="max")
        qv = ax.quiver(
            lon.values[::QUIVER_EVERY],
            lat.values[::QUIVER_EVERY],
            u.values[::QUIVER_EVERY, ::QUIVER_EVERY],
            v.values[::QUIVER_EVERY, ::QUIVER_EVERY],
            scale=700,
            width=0.002,
        )
        ax.quiverkey(qv, 0.88, -0.06, 20, "20 m s$^{-1}$", labelpos="E")
        ax.coastlines("10m", linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5)
        gl = ax.gridlines(crs=ccrs.PlateCarree(), color='gray', alpha=1.0, linestyle='--', linewidth=0.25,
                          xlocs=np.arange(-180, 180, 10), ylocs=np.arange(-90, 90, 10), draw_labels=True)
        gl.top_labels = False
        gl.right_labels = False
        ax.set_title("10 Metre Wind (m s$^{-1}$)", loc="left", fontsize=10)
        ax.set_title(human_date, loc="right", fontsize=10)
        cbar = fig.colorbar(spd_cf, ax=ax, orientation="vertical", pad=0.01, fraction=0.03)
        cbar.set_label("Wind speed (m s$^{-1}$)")
        _save(fig, f"Wind10m_{data_str}.png")
        
###############################################################################
# THICKNESS (1000-500 hPa) + SEA LEVEL PRESSURE                               #
###############################################################################       
        msl_ds = _open_var(grib, "prmsl", typeOfLevel="meanSea")
        mslp = msl_ds["prmsl"].metpy.convert_units("hPa")
        
        gh1000_ds = _open_var(grib, "gh", typeOfLevel="isobaricInhPa", level=1000)
        gh500_ds = _open_var(grib, "gh", typeOfLevel="isobaricInhPa", level=500)

        z1000 = gh1000_ds["gh"]
        z500 = gh500_ds["gh"]
        
        espessura = z500 - z1000  
        espessura = espessura/10
        
        proj = ccrs.PlateCarree()
        fig, ax = plt.subplots(figsize=(12, 10), subplot_kw={"projection": proj})
        ax.set_extent(EXTENT, crs=proj)
        cf = ax.contourf(lon, lat, espessura, levels=THICKNESS_LEVELS, cmap=THICKNESS_CMAP, extend="both", alpha=0.8)
        cs = ax.contour(lon, lat, mslp, colors='black',linestyles='dashed', linewidths=0.8, levels=PRESSURE_LEVELS)
        ax.clabel(cs, inline=1, inline_spacing=0, fontsize='10',fmt = '%1.0f')
        ax.coastlines("10m", linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5)
        gl = ax.gridlines(crs=ccrs.PlateCarree(), color='gray', alpha=1.0, linestyle='--', linewidth=0.25,
                          xlocs=np.arange(-180, 180, 10), ylocs=np.arange(-90, 90, 10), draw_labels=True)
        gl.top_labels = False
        gl.right_labels = False
        ax.set_title("Thickness 1000hPa-500 hPa + Sea Level Pressure (hPa)", loc="left", fontsize=10)
        ax.set_title(human_date, loc="right", fontsize=10)
        cbar = fig.colorbar(cf, ax=ax, orientation="vertical", pad=0.01, fraction=0.03)
        cbar.set_label(" Thickness 1000hPa-500hPa (dam)")
        _save(fig, f"pressure_thickness_{data_str}.png")

###############################################################################
# TOTAL PRECIPITATION                                                         #
###############################################################################         

        tp = None
        try:
            tp_ds = _open_var(grib, "tp", typeOfLevel="surface", stepType="accum")
            tp = tp_ds["tp"]
        except (FileNotFoundError, ValueError, RuntimeError):
            print("  ! 'tp' not found – skipping total precipitation plot.")
            tp = None

        if tp is not None:
            fig, ax = plt.subplots(figsize=(12, 10), subplot_kw={"projection": proj})
            ax.set_extent(EXTENT, crs=proj)
            cf = ax.contourf(lon, lat, tp, levels=PRECIP_LEVELS, cmap=PRECIP_CMAP, extend="max")
            ax.coastlines("10m", linewidth=0.8)
            ax.add_feature(cfeature.BORDERS, linewidth=0.5)
            gl = ax.gridlines(crs=ccrs.PlateCarree(), color='gray', alpha=1.0, linestyle='--', linewidth=0.25,
                              xlocs=np.arange(-180, 180, 10), ylocs=np.arange(-90, 90, 10), draw_labels=True)
            gl.top_labels = False
            gl.right_labels = False
            ax.set_title("Total Precipitation (mm)", loc="left", fontsize=10)
            ax.set_title(human_date, loc="right", fontsize=10)
            cbar = fig.colorbar(cf, ax=ax, orientation="vertical", pad=0.01, fraction=0.03, ticks=np.arange(0,65,5))
            cbar.set_label("Accumulated precipitation (mm)")
            _save(fig, f"TotPrec_{data_str}.png")

    except Exception as err:
        print(f"Error processing {base}: {err}")


