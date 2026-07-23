#!/usr/bin/env python3
"""Decode the structure of a CHIME/FRB Catalog 2 dynamic-spectrum .h5 file.

Read-only. Dumps the full HDF5 tree: groups, datasets (shape/dtype),
and every attribute, so we can design the manifest (Task 3) and schema
tests (Task 4) against the real layout.

Usage: inspect_h5.py FILE.h5 [FILE2.h5 ...]
"""
import sys
import h5py
import numpy as np


def summarize_array(name, dset, indent):
    pad = "  " * indent
    info = f"{pad}DATASET {name}: shape={dset.shape} dtype={dset.dtype}"
    print(info)
    # For small arrays, show a value sample; for large, show min/max/finite stats.
    try:
        if dset.size == 0:
            print(f"{pad}  (empty)")
        elif dset.size <= 12:
            print(f"{pad}  values={dset[()]}")
        else:
            arr = dset[()]
            if np.issubdtype(arr.dtype, np.number):
                finite = np.isfinite(arr)
                nfin = int(finite.sum())
                print(f"{pad}  n_finite={nfin}/{arr.size} "
                      f"nan={int(np.isnan(arr).sum())} inf={int(np.isinf(arr).sum())}")
                if nfin:
                    fv = arr[finite]
                    print(f"{pad}  min={fv.min():.6g} max={fv.max():.6g} "
                          f"mean={fv.mean():.6g}")
                    # First few along each axis edge to see orientation
                    if arr.ndim == 1:
                        print(f"{pad}  head={arr[:4]} tail={arr[-4:]}")
            else:
                print(f"{pad}  (non-numeric) head={arr.flat[:4]}")
    except Exception as e:  # noqa: BLE001
        print(f"{pad}  <could not read values: {e}>")
    dump_attrs(dset, indent + 1)


def dump_attrs(obj, indent):
    pad = "  " * indent
    for k, v in obj.attrs.items():
        vs = v
        if isinstance(v, (bytes, np.bytes_)):
            vs = v.decode("utf-8", "replace")
        elif isinstance(v, np.ndarray):
            vs = f"ndarray shape={v.shape} dtype={v.dtype} sample={v.flat[:4]}"
        print(f"{pad}@ {k} = {vs}")


def walk(name, obj, indent=0):
    pad = "  " * indent
    if isinstance(obj, h5py.Group):
        print(f"{pad}GROUP {name if name else '/'}")
        dump_attrs(obj, indent + 1)
        for k in obj:
            walk(k, obj[k], indent + 1)
    elif isinstance(obj, h5py.Dataset):
        summarize_array(name, obj, indent)


def main():
    for path in sys.argv[1:]:
        print("=" * 78)
        print(f"FILE: {path}")
        print("=" * 78)
        with h5py.File(path, "r") as f:
            print("--- root attributes ---")
            dump_attrs(f, 1)
            print("--- tree ---")
            for k in f:
                walk(k, f[k], 1)
        print()


if __name__ == "__main__":
    main()
