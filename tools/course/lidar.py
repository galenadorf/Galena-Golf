"""Canopy height from USGS lidar, read straight from the public AWS copy (Entwine Point Tile).

The 2025 survey (IL_22County_D25) is only on rockyweb.usgs.gov, which doesn't answer from here; the 2019 survey, the same
flight as the 1 m DEM, is on s3://usgs-lidar-public as IL_8County_PlusChampaign_B2_2019. Only the octree nodes over the
course are fetched (cached in .cache/ept/).

  .cache/chm.tif   1 m canopy height (m above the DEM) over the detail area, local frame; 0 where there's no vegetation
"""
import os
from concurrent.futures import ThreadPoolExecutor

import laspy
import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.transform import from_origin
from scipy import ndimage as ndi

from common import DETAIL, LOCAL, UA, bbox_lonlat, cache, course

EPT = 'https://s3-us-west-2.amazonaws.com/usgs-lidar-public/' + course.LIDAR_EPT
os.makedirs(cache('ept'), exist_ok=True)


def get(url, binary=False):
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    return r.content if binary else r.json()


def nodes_in(box3857):
    meta = get(EPT + '/ept.json')
    b = meta['bounds']
    x0, y0, x1, y1 = box3857
    out = []

    def walk(key, bounds, hier):
        if key not in hier:
            return
        n = hier[key]
        if n == -1:  # its subtree is in its own hierarchy file
            hier.update(get(f'{EPT}/ept-hierarchy/{key}.json'))
            n = hier[key]
        if n > 0:
            out.append(key)
        d, X, Y, Z = map(int, key.split('-'))
        mx, my, mz = [(bounds[i] + bounds[i + 3]) / 2 for i in range(3)]
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    nb = [bounds[0] if not dx else mx, bounds[1] if not dy else my, bounds[2] if not dz else mz,
                          mx if not dx else bounds[3], my if not dy else bounds[4], mz if not dz else bounds[5]]
                    if nb[3] < x0 or nb[0] > x1 or nb[4] < y0 or nb[1] > y1:
                        continue
                    walk(f'{d + 1}-{2 * X + dx}-{2 * Y + dy}-{2 * Z + dz}', nb, hier)

    walk('0-0-0-0', b, get(EPT + '/ept-hierarchy/0-0-0-0.json'))
    return out


def fetch(key):
    p = cache('ept', key + '.laz')
    if not os.path.exists(p):
        data = get(f'{EPT}/ept-data/{key}.laz', binary=True)
        open(p + '.part', 'wb').write(data)
        os.replace(p + '.part', p)
    return p


def main():
    out = cache('chm.tif')
    if os.path.exists(out):
        print('chm.tif exists')
        return
    w, s, e, n = bbox_lonlat(DETAIL)
    t = Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True)
    (x0, y0), (x1, y1) = t.transform(w, s), t.transform(e, n)
    keys = nodes_in((x0, y0, x1, y1))
    print(len(keys), 'octree nodes')
    with ThreadPoolExecutor(8) as ex:
        paths = list(ex.map(fetch, keys))
    to_local = Transformer.from_crs('EPSG:3857', LOCAL, always_xy=True)
    e0, n0, e1, n1 = DETAIL
    W, H = int(e1 - e0), int(n1 - n0)
    top = np.full((H, W), -1e9, np.float32)
    npts = 0
    with rasterio.open(cache('dem1m.tif')) as s:
        dem = s.read(1)
    for p in paths:
        las = laspy.read(p)
        cls = np.asarray(las.classification)
        keep = (cls >= 3) & (cls <= 5) | (cls == 1)  # vegetation (and unclassified, which the canopy filter below sorts out)
        if not keep.any():
            continue
        E, N = to_local.transform(np.asarray(las.x)[keep], np.asarray(las.y)[keep])
        Z = np.asarray(las.z)[keep]
        c = np.floor(E - e0).astype(int)
        r = np.floor(n1 - N).astype(int)
        ok = (c >= 0) & (c < W) & (r >= 0) & (r < H)
        np.maximum.at(top, (r[ok], c[ok]), Z[ok])
        npts += ok.sum()
    chm = np.where(top > -1e8, top - dem, 0)
    chm = np.clip(chm, 0, 45)
    # fill single-pixel gaps inside crowns
    chm = np.maximum(chm, ndi.grey_closing(chm, size=3) * (ndi.maximum_filter(chm, 3) > 2))
    with rasterio.open(out, 'w', driver='GTiff', width=W, height=H, count=1, dtype='float32', crs=LOCAL, transform=from_origin(e0, n1, 1, 1), compress='deflate') as d:
        d.write(chm.astype(np.float32), 1)
    print(f'chm.tif from {npts} vegetation points, {np.mean(chm > 2):.1%} above 2 m')


if __name__ == '__main__':
    main()
