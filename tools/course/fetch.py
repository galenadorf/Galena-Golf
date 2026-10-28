"""Download the raw data for the course into .cache/ (skips anything already there).

  osm.json        OpenStreetMap, everything in the detail area (Overpass)
  naip.tif        USDA NAIP 2023 aerial (R, G, B, NIR), 0.5 m, local frame, detail area
  dem1m.tif       USGS 3DEP 1 m bare-earth DEM, local frame, detail area
  dem_wide.tif    the same DEM at 10 m over the wide (horizon) area
"""
import json
import os
import sys

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT

from common import DETAIL, LOCAL, UA, WIDE, bbox_lonlat, cache, course


def overpass():
    out = cache('osm.json')
    if os.path.exists(out):
        return
    w, s, e, n = bbox_lonlat(DETAIL, 100)
    q = f'[out:json][timeout:120];nwr({s},{w},{n},{e});out body;>;out skel qt;'
    r = requests.post('https://overpass-api.de/api/interpreter', data={'data': q}, headers=UA, timeout=300)
    r.raise_for_status()
    json.loads(r.text)
    open(out, 'w').write(r.text)
    print('osm.json', len(r.text))


def warp(src_url, out, area, res, bands=None, resampling=Resampling.bilinear, dtype=None):
    """Read a (remote) raster and warp the area onto the local frame at res metres."""
    if os.path.exists(out):
        return
    e0, n0, e1, n1 = area
    W, H = int(round((e1 - e0) / res)), int(round((n1 - n0) / res))
    tr = from_origin(e0, n1, res, res)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='4'):
        with rasterio.open(src_url) as src:
            with WarpedVRT(src, crs=LOCAL, transform=tr, width=W, height=H, resampling=resampling) as v:
                data = v.read(bands)
                prof = dict(driver='GTiff', width=W, height=H, count=data.shape[0], dtype=dtype or data.dtype, crs=LOCAL, transform=tr,
                            compress='deflate', nodata=v.nodata)
    with rasterio.open(out, 'w', **prof) as dst:
        dst.write(data.astype(prof['dtype']))
    print(os.path.basename(out), data.shape)


def naip():
    out = cache('naip.tif')
    if os.path.exists(out):
        return
    w, s, e, n = bbox_lonlat(DETAIL)
    body = {'collections': ['naip'], 'bbox': [w, s, e, n], 'limit': 10, 'sortby': [{'field': 'datetime', 'direction': 'desc'}]}
    feats = requests.post('https://planetarycomputer.microsoft.com/api/stac/v1/search', json=body, headers=UA, timeout=60).json()['features']
    year = feats[0]['properties']['datetime'][:4]
    feats = [f for f in feats if f['properties']['datetime'][:4] == year]
    print('NAIP', year, [f['id'] for f in feats])
    tok = requests.get('https://planetarycomputer.microsoft.com/api/sas/v1/token/naip', headers=UA, timeout=60).json()['token']
    parts = []
    for i, f in enumerate(feats):
        p = cache(f'naip_{i}.tif')
        warp('/vsicurl/' + f['assets']['image']['href'] + '?' + tok, p, DETAIL, .5, resampling=Resampling.cubic)
        parts.append(p)
    # mosaic: the first tile that has data wins
    with rasterio.open(parts[0]) as a:
        prof, acc = a.profile, a.read()
    for p in parts[1:]:
        with rasterio.open(p) as b:
            d = b.read()
        hole = acc.sum(0) == 0
        acc[:, hole] = d[:, hole]
    with rasterio.open(out, 'w', **prof) as dst:
        dst.write(acc)
    for p in parts:
        os.remove(p)
    print('naip.tif', acc.shape)


def dem_mosaic(tiles, out, area, res):
    """Warp each tile onto the local grid and merge (tiles don't overlap)."""
    if os.path.exists(out):
        return
    e0, n0, e1, n1 = area
    W, H = int(round((e1 - e0) / res)), int(round((n1 - n0) / res))
    acc = np.full((H, W), np.nan, np.float32)
    tr = from_origin(e0, n1, res, res)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='4'):
        for t in tiles:
            with rasterio.open('/vsicurl/' + t) as src:
                with WarpedVRT(src, crs=LOCAL, transform=tr, width=W, height=H, resampling=Resampling.bilinear if res <= 2 else Resampling.average,
                               src_nodata=src.nodata, nodata=np.nan, dtype='float32') as v:
                    d = v.read(1)
            ok = np.isfinite(d) & np.isnan(acc)
            acc[ok] = d[ok]
            print('  ', t.rsplit('/', 1)[1], f'{ok.mean():.0%} of {os.path.basename(out)}')
    with rasterio.open(out, 'w', driver='GTiff', width=W, height=H, count=1, dtype='float32', crs=LOCAL, transform=tr, compress='deflate', nodata=np.nan) as dst:
        dst.write(acc, 1)
    print(os.path.basename(out), acc.shape, 'missing', int(np.isnan(acc).sum()))


def dem_tiles():
    w, s, e, n = bbox_lonlat(WIDE)
    items = requests.get('https://tnmaccess.nationalmap.gov/api/v1/products',
                         params={'bbox': f'{w},{s},{e},{n}', 'datasets': 'Digital Elevation Model (DEM) 1 meter', 'outputFormat': 'JSON', 'max': 200},
                         headers=UA, timeout=120).json()['items']
    proj = course.DEM_PROJECT
    return sorted({i['downloadURL'] for i in items if proj in i['downloadURL']})


if __name__ == '__main__':
    what = sys.argv[1:] or ['osm', 'naip', 'dem']
    if 'osm' in what:
        overpass()
    if 'naip' in what:
        naip()
    if 'dem' in what:
        tiles = dem_tiles()
        print('DEM tiles:', [t.rsplit('/', 1)[1] for t in tiles])
        dem_mosaic(tiles, cache('dem1m.tif'), DETAIL, 1)
        dem_mosaic(tiles, cache('dem_wide.tif'), WIDE, 10)
