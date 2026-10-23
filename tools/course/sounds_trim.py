"""Trim the raw recordings in out/sounds/*.m4a to just the sound and write the game's files into ../../sounds/ (mono MP3, 96 kbps,
peak-normalised to -3 dBFS; the game sets each one's level). Needs PyAV (pip install av). Start: 12 ms before the sound first rises
above -48 dB of its peak; end: where the 5 ms envelope has dropped 60 dB below the peak, plus a short fade.
  out/sounds/Driver.m4a -> sounds/driver.mp3    3-wood.m4a -> wood.mp3    Irons.m4a -> iron.mp3 (Iron.m4a is a duplicate)
  Wedges.m4a -> wedge.mp3    Putter.m4a -> putter.mp3    Ball_in_hole.m4a -> cup.mp3
Music: out/sounds/Hole_7_background_music.m4a -> sounds/hole7.mp3, mono at 80 kbps, the silence before and after cut (the last second
holds the song's closing hit), a short fade at the end, peak at -1.5 dBFS; the game plays it at 60 % (HOLE_SONGS in index.html).
Rerun after replacing a recording; commit sounds/ (the game loads it, sw.js caches it)."""
import os
import sys

import av
import numpy as np

from common import OUT, HERE

SR = 48000
MAP = {'Driver': 'driver', '3-wood': 'wood', 'Irons': 'iron', 'Wedges': 'wedge', 'Putter': 'putter', 'Ball_in_hole': 'cup'}
DEST = os.path.join(os.path.dirname(os.path.dirname(HERE)) if os.path.basename(HERE) == 'course' else HERE, 'sounds')


def load(path):
    c = av.open(path)
    r = av.AudioResampler(format='fltp', layout='mono', rate=SR)
    return np.concatenate([o.to_ndarray()[0] for fr in c.decode(audio=0) for o in r.resample(fr)])


def trim(x):
    env = np.sqrt(np.convolve(x ** 2, np.ones(240) / 240, 'same'))
    pk = env.max(); ip = int(np.argmax(env))
    a = int(np.nonzero(env > pk * 10 ** (-48 / 20))[0][0])
    below = np.nonzero(env[ip:] < pk * 10 ** (-60 / 20))[0]
    # the cup recording rattles: the end is the LAST time it is above -60 dB
    above = np.nonzero(env > pk * 10 ** (-60 / 20))[0]
    b = int(above[-1]) if len(above) else ip + (int(below[0]) if len(below) else len(x))
    a = max(0, a - int(.012 * SR)); b = min(len(x), b + int(.03 * SR))
    y = x[a:b].copy(); f = int(.02 * SR); y[-f:] *= np.linspace(1, 0, f) ** 2; y[:int(.002 * SR)] *= np.linspace(0, 1, int(.002 * SR))
    return y / np.abs(y).max() * 10 ** (-3 / 20), a / SR, b / SR


def trim_music(x, lead=.05, tail=.4):
    env = np.sqrt(np.convolve(x ** 2, np.ones(2205) / 2205, 'same'))   # 46 ms rms
    on = np.nonzero(env > env.max() * 10 ** (-45 / 20))[0]
    a = max(0, int(on[0]) - int(lead * SR)); b = min(len(x), int(on[-1]) + int(tail * SR))
    y = x[a:b].copy(); f = int(.3 * SR); y[-f:] *= np.linspace(1, 0, f) ** 2
    return y / np.abs(y).max() * 10 ** (-1.5 / 20), a / SR, b / SR


def write(y, path, kbps=96):
    c = av.open(path, 'w', format='mp3')
    s = c.add_stream('libmp3lame', rate=SR); s.layout = 'mono'; s.bit_rate = kbps * 1000
    fr = av.AudioFrame.from_ndarray(y.astype(np.float32)[None, :], format='fltp', layout='mono'); fr.sample_rate = SR
    for p in s.encode(fr): c.mux(p)
    for p in s.encode(None): c.mux(p)
    c.close()


def music():
    p = os.path.join(OUT, 'sounds', 'Hole_7_background_music.m4a')
    if os.path.exists(p):
        y, a, b = trim_music(load(p))
        write(y, os.path.join(DEST, 'hole7.mp3'), 80)
        print(f'Hole_7_background_music -> sounds/hole7.mp3  kept {a:.2f}-{b:.2f} s  ({len(y) / SR:.1f} s, {os.path.getsize(os.path.join(DEST, "hole7.mp3")) / 1048576:.2f} MB)')


def main():
    music()
    os.makedirs(DEST, exist_ok=True)
    for src, dst in MAP.items():
        p = os.path.join(OUT, 'sounds', src + '.m4a')
        if not os.path.exists(p):
            print('missing', p); continue
        y, a, b = trim(load(p))
        write(y, os.path.join(DEST, dst + '.mp3'))
        print(f'{src:13s} -> sounds/{dst}.mp3  kept {a:.3f}-{b:.3f} s  ({len(y) / SR * 1000:.0f} ms, {os.path.getsize(os.path.join(DEST, dst + ".mp3")) / 1024:.1f} KB)')


if __name__ == '__main__':
    sys.exit(main())
