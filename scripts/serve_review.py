#!/usr/bin/env python3
"""Serve the FRB Catalog 2 review bundle with on-demand waterfall rendering.

Static assets (index.html, app.js, style.css, bursts.json, meta.json) are served
from the bundle dir. Per-burst images are produced lazily:

  GET /api/waterfall/<TNS>.png  -> render standardized dynamic spectrum from the
                                    Tier B .h5 (cached to <out>/cache/), or a
                                    placeholder if no Tier B file exists.
  GET /api/localization/<TNS>.png -> the pre-made localization PNG from disk.
  GET /api/pdf/<TNS>            -> the pre-made dynamic-spectrum data PDF.

Run on the desktop (needs matplotlib/h5py from the project venv)::

    ~/Projects/fastradiobursts/.venv/bin/python scripts/serve_review.py --port 8765

then from the Mac:  ssh -N -L 8765:localhost:8765 popos  ->  http://localhost:8765
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "src"))

import h5py  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402

from echo_frb.reference.make_plots import rebin_freq  # noqa: E402  (reused)

TNS_RE = re.compile(r"^FRB[0-9A-Za-z]+$")
_RENDER_LOCK = threading.Lock()


def _fig_to_png_bytes(fig) -> bytes:
    FigureCanvasAgg(fig)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


def _placeholder_png(text: str) -> bytes:
    fig = Figure(figsize=(7.5, 4.2), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#2c2c2a")
    ax.text(0.5, 0.5, text, ha="center", va="center", color="#c3c2b7",
            fontsize=15, transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])
    return _fig_to_png_bytes(fig)


def render_waterfall(tns: str, tierb_dir: str) -> bytes:
    path = os.path.join(tierb_dir, f"{tns}_tierb.h5")
    if not os.path.exists(path):
        return _placeholder_png("No Tier B waterfall for this burst")
    with h5py.File(path, "r") as f:
        std = f["standardized"][()].astype(np.float32)
        pmask = f["mask/project_mask"][()]
        freqs = f["coords/freqs"][()]
        times = f["coords/times"][()]
        attrs = dict(f.attrs)

    disp = rebin_freq(std, pmask, 256)           # mask-aware freq collapse (reused)
    vmax = np.nanpercentile(np.abs(disp), 99)
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 1.0
    tms = (times - times[0]) * 1e3
    ext = [float(tms[0]), float(tms[-1]), float(freqs[0]), float(freqs[-1])]

    fig = Figure(figsize=(7.5, 4.2), dpi=110)
    ax = fig.add_axes([0.11, 0.13, 0.86, 0.78])
    ax.imshow(disp, aspect="auto", origin="lower", extent=ext,
              vmin=-vmax, vmax=vmax, cmap="RdBu_r", interpolation="nearest")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Frequency (MHz)")
    dm = attrs.get("dm_incoherent")
    sub = f"  ·  DM={float(dm):.1f} pc cm⁻³" if dm is not None else ""
    ax.set_title(f"{tns}  ·  standardized dynamic spectrum{sub}", fontsize=11)
    return _fig_to_png_bytes(fig)


class Handler(SimpleHTTPRequestHandler):
    # injected by partial(): out_dir, tierb_dir, loc_dir, pdf_dir, cache_dir
    def _send_bytes(self, data: bytes, ctype: str, cache=True):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def _fail(self, code: int, msg: str):
        self.send_error(code, msg)

    def do_GET(self):  # noqa: N802
        p = self.path.split("?", 1)[0]

        if p.startswith("/api/waterfall/"):
            tns = os.path.basename(p)[: -len(".png")]
            if not TNS_RE.match(tns):
                return self._fail(400, "bad name")
            cache_png = os.path.join(self.cache_dir, f"{tns}.png")
            if os.path.exists(cache_png):
                with open(cache_png, "rb") as f:
                    return self._send_bytes(f.read(), "image/png")
            with _RENDER_LOCK:
                if os.path.exists(cache_png):          # double-check after wait
                    with open(cache_png, "rb") as f:
                        return self._send_bytes(f.read(), "image/png")
                try:
                    data = render_waterfall(tns, self.tierb_dir)
                except Exception as e:  # noqa: BLE001
                    return self._fail(500, f"render error: {e}")
                tmp = cache_png + ".part"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, cache_png)
            return self._send_bytes(data, "image/png")

        if p.startswith("/api/localization/"):
            tns = os.path.basename(p)[: -len(".png")]
            if not TNS_RE.match(tns):
                return self._fail(400, "bad name")
            fp = os.path.join(self.loc_dir, f"{tns}_localization.png")
            if not os.path.exists(fp):
                return self._fail(404, "no localization image")
            with open(fp, "rb") as f:
                return self._send_bytes(f.read(), "image/png")

        if p.startswith("/api/pdf/"):
            tns = os.path.basename(p)
            if not TNS_RE.match(tns):
                return self._fail(400, "bad name")
            fp = os.path.join(self.pdf_dir, f"{tns}_stokesi_dynamic_spectrum_data.pdf")
            if not os.path.exists(fp):
                return self._fail(404, "no pdf")
            with open(fp, "rb") as f:
                return self._send_bytes(f.read(), "application/pdf")

        return super().do_GET()


def main():
    home = os.path.expanduser("~")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(home, "frb_catalog2_prep", "review"),
                    help="bundle dir (static assets + bursts.json live here)")
    ap.add_argument("--tierb-dir",
                    default=os.path.join(home, "frb_catalog2_prep", "tier_b_standardized"))
    ap.add_argument("--loc-dir",
                    default=os.path.join(home, "frb_catalog2", "localizations", "plots"))
    ap.add_argument("--pdf-dir",
                    default=os.path.join(home, "frb_catalog2", "dynamic_spectra", "plots", "data"))
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()

    cache_dir = os.path.join(args.out, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    handler = partial(Handler, directory=args.out)
    # attach config as class attributes visible to instances
    Handler.out_dir = args.out
    Handler.tierb_dir = args.tierb_dir
    Handler.loc_dir = args.loc_dir
    Handler.pdf_dir = args.pdf_dir
    Handler.cache_dir = cache_dir

    srv = ThreadingHTTPServer((args.bind, args.port), handler)
    print(f"serving {args.out} at http://{args.bind}:{args.port}")
    print(f"  tier B: {args.tierb_dir}")
    print(f"  localizations: {args.loc_dir}")
    print("tunnel from the Mac:  ssh -N -L {0}:localhost:{0} popos".format(args.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        srv.shutdown()


if __name__ == "__main__":
    main()
