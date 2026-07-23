#!/usr/bin/env python3
"""Task 5 — reference-event QC figures + automated interpretation pre-check.

For each selected event, renders one multi-panel PNG from Tier A (raw) and Tier B
(standardized): raw dynamic spectrum, original mask, frequency-integrated time
series with off-pulse shading, time-integrated spectrum, per-channel baseline &
noise, standardized spectrum, project mask, and a metadata/coordinate panel.

The pre-check programmatically verifies axis orientation, mask subsetting, burst
location, and preprocessing behaviour (standardized == data - baseline), writing a
machine "first pass" that focuses the human analysts. Two-analyst sign-off columns
remain for humans to complete.
"""
import argparse
import os

import h5py
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def rebin_freq(arr, valid, nbin=512):
    """Mask-aware average over the frequency axis for display."""
    nf, nt = arr.shape
    nbin = min(nbin, nf)
    edges = np.linspace(0, nf, nbin + 1).astype(int)
    out = np.full((nbin, nt), np.nan, np.float32)
    for i in range(nbin):
        a, b = edges[i], edges[i + 1]
        if b <= a:
            continue
        block = arr[a:b]
        vblock = valid[a:b]
        num = np.where(vblock, block, 0.0).sum(0)
        den = vblock.sum(0)
        with np.errstate(invalid="ignore"):
            out[i] = np.where(den > 0, num / den, np.nan)
    return out


def load_tier_a(path):
    with h5py.File(path, "r") as f:
        a = dict(f.attrs)
        return dict(
            data=f["data"][()].astype(np.float32),
            flag=f["flag"][()],
            good_freq=f["good_freq"][()],
            freqs=f["index_map/freqs"][()],
            times=f["index_map/times"][()],
            attrs=a,
        )


def load_tier_b(path):
    with h5py.File(path, "r") as f:
        return dict(
            standardized=f["standardized"][()].astype(np.float32),
            project_mask=f["mask/project_mask"][()],
            baseline=f["baseline/per_channel"][()],
            robust=f["noise/robust_std"][()],
            conv=f["noise/conventional_std"][()],
            offmask=f["offpulse/time_mask"][()],
            attrs=dict(f.attrs),
        )


def autocheck(A, B):
    """Return (ok, [messages]) verifying our interpretation is correct."""
    msgs = []
    fr = A["freqs"]
    if not (fr[1] > fr[0] and np.all(np.diff(fr) > 0)):
        msgs.append("freq axis not increasing/monotonic")
    if A["data"].shape[0] != 16384:
        msgs.append(f"freq axis len {A['data'].shape[0]} != 16384")
    if B is not None:
        if (B["project_mask"] & ~A["flag"]).any():
            msgs.append("project_mask marks a pixel usable that original masked")
        # standardized == data - baseline (spot-check)
        recon = A["data"] - B["baseline"][:, None].astype(np.float32)
        diff = np.abs(recon - B["standardized"])
        if np.nanmax(diff) > 1e-4:
            msgs.append(f"standardized != data-baseline (max diff {np.nanmax(diff):.2e})")
        on0 = int(B["attrs"].get("on_pulse_start", -1))
        on1 = int(B["attrs"].get("on_pulse_end", -1))
        nt = A["data"].shape[1]
        if not (0 <= on0 <= on1 < nt):
            msgs.append(f"on-pulse [{on0},{on1}] outside window [0,{nt})")
        # burst peak should fall within on-pulse span
        valid = A["flag"] & A["good_freq"][:, None]
        den = valid.sum(0).astype(float); den[den == 0] = 1
        prof = np.where(valid, A["data"], 0).sum(0) / den
        peak = int(np.argmax(prof))
        if not (on0 - 6 <= peak <= on1 + 6):
            msgs.append(f"profile peak {peak} far from on-pulse [{on0},{on1}]")
    return (len(msgs) == 0), msgs


def make_figure(A, B, meta, out_png):
    tms = (A["times"] - A["times"][0]) * 1e3
    fr = A["freqs"]
    ext = [tms[0], tms[-1], fr[0], fr[-1]]
    valid = A["flag"] & A["good_freq"][:, None]

    fig, ax = plt.subplots(3, 3, figsize=(16, 12))
    fig.suptitle(f"{meta['tns_name']}   [{meta['categories']}]   status={meta['status']}",
                 fontsize=13, fontweight="bold")

    # 1 raw dynamic spectrum
    disp = rebin_freq(A["data"], valid, 512)
    vmax = np.nanpercentile(np.abs(disp), 99)
    ax[0, 0].imshow(disp, aspect="auto", origin="lower", extent=ext,
                    vmin=-vmax, vmax=vmax, cmap="RdBu_r")
    ax[0, 0].set_title("1. Raw dynamic spectrum (freq x time)")
    ax[0, 0].set_ylabel("Frequency (MHz)"); ax[0, 0].set_xlabel("Time (ms)")

    # 2 original mask
    maskdisp = rebin_freq((~A["flag"]).astype(np.float32),
                          np.ones_like(A["flag"]), 512)
    ax[0, 1].imshow(maskdisp, aspect="auto", origin="lower", extent=ext,
                    vmin=0, vmax=1, cmap="Greys")
    mp = 1 - A["flag"].mean()
    ax[0, 1].set_title(f"2. Original mask (masked frac={mp:.2f})")
    ax[0, 1].set_xlabel("Time (ms)")

    # 3 frequency-integrated time series + off-pulse shading
    den = valid.sum(0).astype(float); den[den == 0] = 1
    prof = np.where(valid, A["data"], 0).sum(0) / den
    ax[0, 2].plot(tms, prof, lw=0.8)
    if B is not None:
        off = B["offmask"]
        ax[0, 2].fill_between(tms, prof.min(), prof.max(), where=~off,
                              color="orange", alpha=0.25, label="on-pulse")
        ax[0, 2].fill_between(tms, prof.min(), prof.max(), where=off,
                              color="green", alpha=0.10, label="off-pulse")
        ax[0, 2].legend(fontsize=8)
    ax[0, 2].set_title("3. Frequency-integrated time series")
    ax[0, 2].set_xlabel("Time (ms)")

    # 4 time-integrated spectrum
    spec = np.where(valid, A["data"], np.nan)
    with np.errstate(all="ignore"):
        spec_mean = np.nanmean(spec, axis=1)
    fr_reb = fr[::32]
    ax[1, 0].plot(fr_reb, np.nanmean(spec_mean[:len(fr_reb) * 32].reshape(-1, 32), 1),
                  lw=0.6)
    ax[1, 0].set_title("4. Time-integrated spectrum")
    ax[1, 0].set_xlabel("Frequency (MHz)")

    # 5 baseline + noise per channel
    if B is not None:
        ax[1, 1].plot(fr, B["baseline"], lw=0.5, label="baseline", color="k")
        ax[1, 1].set_ylabel("baseline"); ax[1, 1].legend(loc="upper left", fontsize=8)
        axb = ax[1, 1].twinx()
        axb.plot(fr, B["robust"], lw=0.5, color="tab:red", label="robust sigma")
        axb.plot(fr, B["conv"], lw=0.5, color="tab:blue", alpha=0.6, label="conv sigma")
        axb.set_ylabel("noise sigma"); axb.legend(loc="upper right", fontsize=8)
    ax[1, 1].set_title("5. Per-channel baseline & noise")
    ax[1, 1].set_xlabel("Frequency (MHz)")

    # 6 standardized dynamic spectrum
    if B is not None:
        sdisp = rebin_freq(B["standardized"], valid, 512)
        vmax2 = np.nanpercentile(np.abs(sdisp), 99)
        ax[1, 2].imshow(sdisp, aspect="auto", origin="lower", extent=ext,
                        vmin=-vmax2, vmax=vmax2, cmap="RdBu_r")
    ax[1, 2].set_title("6. Standardized dynamic spectrum (Tier B)")
    ax[1, 2].set_xlabel("Time (ms)")

    # 7 project mask
    if B is not None:
        pdisp = rebin_freq((~B["project_mask"]).astype(np.float32),
                           np.ones_like(B["project_mask"]), 512)
        ax[2, 0].imshow(pdisp, aspect="auto", origin="lower", extent=ext,
                        vmin=0, vmax=1, cmap="Greys")
        pm = 1 - B["project_mask"].mean()
        ax[2, 0].set_title(f"7. Project mask (masked frac={pm:.2f})")
    ax[2, 0].set_xlabel("Time (ms)"); ax[2, 0].set_ylabel("Frequency (MHz)")

    # 8 noise histogram / off-pulse sanity
    if B is not None:
        off = B["offmask"]
        offvals = A["data"][:, off][A["flag"][:, off]]
        ax[2, 1].hist(offvals[np.isfinite(offvals)], bins=200, color="gray")
        ax[2, 1].set_title("8. Off-pulse value distribution")
        ax[2, 1].set_yscale("log")
    ax[2, 1].set_xlabel("normalized intensity")

    # 9 text panel: coords + metadata + autocheck
    ok, msgs = autocheck(A, B)
    a = A["attrs"]
    lines = [
        f"num_freq x num_time: 16384 x {A['data'].shape[1]}",
        f"freq: {fr[0]:.2f}-{fr[-1]:.2f} MHz  (increasing={fr[1] > fr[0]})",
        f"res_time: {float(a.get('res_time', 0)) * 1e3:.4f} ms",
        f"DM(incoh): {float(a.get('dm_incoherent', float('nan'))):.2f}",
        f"S/N: {meta.get('catalog_snr')}",
        f"usable BW: {meta.get('usable_bandwidth_mhz')}",
        f"morphology: {meta.get('morphology_label')} (n_sub={meta.get('n_subbursts')})",
        f"repeater: {meta.get('is_repeater')}",
        f"scat_time: {meta.get('scat_time')}",
        "",
        f"AUTO-CHECK: {'OK' if ok else 'FLAGS'}",
    ] + [f"  - {m}" for m in msgs]
    ax[2, 2].axis("off")
    ax[2, 2].text(0.0, 1.0, "\n".join(lines), va="top", ha="left",
                  family="monospace", fontsize=9,
                  color="darkgreen" if ok else "darkred")
    ax[2, 2].set_title("9. Coordinates / metadata / auto-check")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_png, dpi=90)
    plt.close(fig)
    return ok, msgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-csv", required=True)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--tier-b-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    idx = pd.read_csv(args.index_csv)
    results = []
    for i, row in idx.iterrows():
        tns = row["tns_name"]
        src = os.path.join(args.source_root, f"{tns}_stokesi_dynamic_spectrum.h5")
        tb = os.path.join(args.tier_b_dir, f"{tns}_tierb.h5")
        A = load_tier_a(src)
        B = load_tier_b(tb) if os.path.exists(tb) else None
        out_png = os.path.join(args.out_dir, f"{tns}_refqc.png")
        ok, msgs = make_figure(A, B, row.to_dict(), out_png)
        idx.at[i, "plot_path"] = os.path.relpath(out_png, args.out_dir)
        idx.at[i, "interp_autocheck"] = "OK" if ok else "; ".join(msgs)
        results.append((tns, ok, msgs))
        print(f"[refplot] {i+1}/{len(idx)} {tns} {'OK' if ok else 'FLAGS: '+';'.join(msgs)}",
              flush=True)

    idx.to_csv(args.index_csv, index=False)
    nflag = sum(1 for _, ok, _ in results if not ok)
    print(f"\n[refplot] {len(results)} figures, auto-check flagged {nflag}")
    for tns, ok, msgs in results:
        if not ok:
            print(f"  FLAG {tns}: {msgs}")


if __name__ == "__main__":
    main()
