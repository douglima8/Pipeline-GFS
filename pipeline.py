from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import smtplib
import subprocess
import sys
import time as _time
import zipfile
from email.message import EmailMessage
from pathlib import Path
from typing import List, Sequence

###############################################################################
# HELPERS                                                                     #
###############################################################################

def _latest_mtime(path: Path) -> dt.datetime | None:
    mtimes: list[float] = [
        p.stat().st_mtime
        for p in path.rglob("*")
        if "grb2" in p.name.lower() or "grib2" in p.name.lower()
    ]
    if not mtimes:
        return None
    return dt.datetime.fromtimestamp(max(mtimes), tz=dt.timezone.utc)


def _should_skip_download(data_dir: Path, max_age_hours: int) -> bool:
    latest = _latest_mtime(data_dir)
    if latest is None:
        return False

    now = dt.datetime.now(tz=dt.timezone.utc)
    fresh_enough = (now - latest).total_seconds() < max_age_hours * 3600
    same_day = latest.date() == now.date()
    return fresh_enough or same_day

###############################################################################
# SUBPROCESS WRAPPERS                                                         #
###############################################################################

def run_gfs_download(
    data_dir: str | os.PathLike = "DATA",
    python_executable: str = sys.executable,
    gfs_script: str | os.PathLike = "GFS.py",
    extra_env: dict[str, str] | None = None,
    max_age_hours: int = 6,
    force_download: bool = False,
) -> None:
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    if not force_download and _should_skip_download(data_path, max_age_hours):
        print(f"(1/3) GRIBs are up‑to‑date — skipping download.")
        return

    env = os.environ.copy()
    env["DATA_DIR"] = str(data_path.resolve())
    if extra_env:
        env.update(extra_env)

    t0 = _time.time()
    subprocess.run([python_executable, str(gfs_script)], check=True, env=env)
    print(f"GFS.py finished in {_time.time() - t0:.1f}s.")


def run_forecast_plot(
    input_dir: str | os.PathLike = "DATA",
    output_dir: str | os.PathLike = "FIGS",
    python_executable: str = sys.executable,
    forecast_script: str | os.PathLike = "forecast.py",
    extra_env: dict[str, str] | None = None,
) -> None:

    print("(2/3) Creating figures with forecast.py …")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["INPUT_DIR"] = str(Path(input_dir).resolve())
    env["OUTPUT_DIR"] = str(Path(output_dir).resolve())
    if extra_env:
        env.update(extra_env)

    t0 = _time.time()
    subprocess.run([python_executable, str(forecast_script)], check=True, env=env)
    print(f"forecast.py produced figures in {_time.time() - t0:.1f} s.")

###############################################################################
# ZIP HELPER                                                                  #
###############################################################################

def _zip_images(image_paths: Sequence[Path]) -> bytes:

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in image_paths:
            zf.write(path, arcname=path.name)
    buf.seek(0)
    return buf.read()

###############################################################################
# EMAIL STAGE                                                                 #
###############################################################################

def send_images_via_email(
    image_dir: str | os.PathLike = "FIGS",
    sender: str | None = None,
    recipients: List[str] | None = None,
    subject: str = "GFS Forecast Plots",
    body: str = (
        "Good morning,\n\nAttached you will find the latest forecast figure set "
        "generated from GFS.\n\nKind regards,"
    ),
    smtp_server: str = "smtp.gmail.com",
    port: int = 465,
    password: str | None = None,
    zip_name: str = "Forecast_Figures.zip",
) -> None:

    if not sender or not recipients:
        raise ValueError("`sender` and `recipients` are required for e‑mail sending.")

    pw = password or os.getenv("EMAIL_PASSWORD")
    if pw is None:
        raise ValueError("Set `EMAIL_PASSWORD` in the environment or pass `--password`.")

    png_paths = sorted(Path(image_dir).glob("*.png"))
    if not png_paths:
        raise FileNotFoundError(f"No PNG files found in {image_dir!s}.")

    print(f"(3/3) Sending {len(png_paths)} images (zipped) to {', '.join(recipients)} …")

    zip_bytes = _zip_images(png_paths)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(
        zip_bytes,
        maintype="application",
        subtype="zip",
        filename=zip_name,
    )

    with smtplib.SMTP_SSL(smtp_server, port) as smtp:
        smtp.login(sender, pw)
        smtp.send_message(msg)
    print("E‑mail sent successfully.")

###############################################################################
# PIPELINE ORCHESTRATOR                                                       #
###############################################################################

def run_pipeline(args: argparse.Namespace) -> None:

    extra_env: dict[str, str] = {}
    if args.env:
        for kv in args.env:
            if "=" not in kv:
                raise ValueError("Environment variables via --env must be in KEY=value form.")
            k, v = kv.split("=", 1)
            extra_env[k] = v

    run_gfs_download(
        data_dir=args.data_dir,
        gfs_script=args.gfs_script,
        extra_env=extra_env,
        max_age_hours=args.max_age_hours,
        force_download=args.force_download,
    )

    run_forecast_plot(
        input_dir=args.data_dir,
        output_dir=args.fig_dir,
        forecast_script=args.forecast_script,
        extra_env=extra_env,
    )

    if args.send_email:
        send_images_via_email(
            image_dir=args.fig_dir,
            sender=args.sender,
            recipients=args.recipients,
            subject=args.subject,
            body=args.body,
            smtp_server=args.smtp_server,
            port=args.port,
            password=args.password,
            zip_name=args.zip_name,
        )

    print("Pipeline finished.")

###############################################################################
# CLI                                                                         #
###############################################################################

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "GFS→Forecast→E‑mail pipeline: runs GFS.py and forecast.py then sends the figures."
        )
    )
    p.add_argument("--data-dir", default="DATA", help="Directory where GRIB2 files are saved (GFS.py)")
    p.add_argument("--fig-dir", default="FIGS", help="Directory for generated figures (forecast.py)")
    p.add_argument("--gfs-script", default="GFS.py", help="Path to GFS.py")
    p.add_argument("--forecast-script", default="forecast.py", help="Path to forecast.py")
    p.add_argument(
        "--env",
        nargs="*",
        help="Extra environment variables for the subprocesses (KEY=value).",
    )

    # Download logic
    p.add_argument("--max-age-hours", type=int, default=6, help="Skip download if files are newer than this.")
    p.add_argument("--force-download", action="store_true", help="Always download even if fresh data exists.")

    # E‑mail options
    p.add_argument("--send-email", action="store_true", help="Send the images via e‑mail after creation.")
    p.add_argument("--sender", help="Sender e‑mail address")
    p.add_argument("--recipients", nargs="+", help="Recipient address list")
    p.add_argument("--subject", default="GFS Forecast", help="E‑mail subject")
    p.add_argument(
        "--body",
        default=(
            "Good morning,\n\nAttached you will find the latest forecast figure set generated "
            "from GFS.\n\nKind regards,"
        ),
        help="E‑mail body text",
    )
    p.add_argument("--smtp-server", default="smtp.gmail.com", help="SMTP server")
    p.add_argument("--port", type=int, default=465, help="SMTP port (SSL)")
    p.add_argument("--password", help="Sender password/token; if omitted uses EMAIL_PASSWORD env var")
    p.add_argument("--zip-name", default="PVU_Figures.zip", help="Filename for the attached ZIP archive")

    return p


def main() -> None:
    args = _build_arg_parser().parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
