"""Trim the raw recordings in sounds_raw/*.m4a to just the sound and write the game's files into ../../sounds/ (mono MP3, 96 kbps,
peak-normalised to -3 dBFS; the game sets each one's level). Needs PyAV (pip install av). Start: 12 ms before the sound first rises
above -48 dB of its peak; end: where the 5 ms envelope has dropped 60 dB below the peak, plus a short fade.
  sounds_raw/Driver.m4a -> sounds/driver.mp3    3-wood.m4a -> wood.mp3    Irons.m4a -> iron.mp3 (Iron.m4a is a duplicate)
  Wedges.m4a -> wedge.mp3    Putter.m4a -> putter.mp3    Ball_in_hole.m4a -> cup.mp3
Music: sounds_raw/Hole_7_background_music.m4a -> sounds/hole7-q.mp3, mono at 80 kbps, the silence before and after cut (the last second
holds the song's closing hit), a short fade at the end, the playing level is baked into the file (MUSIC_PEAK_DB), so it is quiet even where the browser ignores the game's volume setting (HOLE_SONGS vol is 1).
Around_the_world.mp3 -> sounds/cartmusic.mp3: the radio on the moving golf cart (`cartMusic*` in index.html). Mono at 64 kbps, 44.1 kHz, peak
-12 dBFS (the game scales it by distance from the cart and by the Song volume setting), leading and trailing silence cut, a short fade at the end.
Fart_01..07.m4a and Penis.m4a -> sounds/fart1..8.mp3: trimmed like the strikes, mono at 96 kbps, the playing level baked in (FART_RMS_DB: the same loudness as the
hole-7 song at its Med setting, measured as RMS over the trimmed clip), so the game plays them at gain 1 (a pool, one picked at random: `fartTick`).
Truck_horn.m4a -> sounds/truckhorn.mp3, Truck_rumble.m4a -> sounds/truckrumble.mp3: trimmed like the strikes, mono at 96 kbps (the rumble at 64), peak -3 dBFS;
the truck on the road plays one of the two at random (`SFX.honk`, TRUCK_SND), each with its own level there.
Rerun after replacing a recording; commit sounds/ (the game loads it, sw.js caches it)."""
import os
import sys

import av
import numpy as np

from common import HERE, SOUNDS_RAW

SR = 48000
MUSIC_PEAK_DB = -15.5   # the song's loudest peak: -1.5 dBFS at full scale, 14 dB (a factor of .2) down
FART_RMS_DB = -44.8     # the song's RMS over the whole file is -35.7 dB; Med is x.35 (-9.1 dB)
FARTS = ['Fart_01', 'Fart_02', 'Fart_03', 'Fart_04', 'Fart_05', 'Fart_06', 'Fart_07', 'Penis']   # fart1.mp3 ... in this order
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
    return y / np.abs(y).max() * 10 ** (MUSIC_PEAK_DB / 20), a / SR, b / SR


def write(y, path, kbps=96, sr=SR):
    c = av.open(path, 'w', format='mp3')
    s = c.add_stream('libmp3lame', rate=sr); s.layout = 'mono'; s.bit_rate = kbps * 1000
    fr = av.AudioFrame.from_ndarray(y.astype(np.float32)[None, :], format='fltp', layout='mono'); fr.sample_rate = sr
    for p in s.encode(fr): c.mux(p)
    for p in s.encode(None): c.mux(p)
    c.close()


def music():
    p = os.path.join(SOUNDS_RAW, 'Hole_7_background_music.m4a')
    if os.path.exists(p):
        y, a, b = trim_music(load(p))
        write(y, os.path.join(DEST, 'hole7-q.mp3'), 80)
        print(f'Hole_7_background_music -> sounds/hole7-q.mp3  kept {a:.2f}-{b:.2f} s  ({len(y) / SR:.1f} s, {os.path.getsize(os.path.join(DEST, "hole7-q.mp3")) / 1048576:.2f} MB)')


def cartmusic():
    p = os.path.join(SOUNDS_RAW, 'Around_the_world.mp3')
    if not os.path.exists(p):
        print('missing', p); return
    c = av.open(p); r = av.AudioResampler(format='fltp', layout='mono', rate=44100)
    x = np.concatenate([o.to_ndarray()[0] for fr in c.decode(audio=0) for o in r.resample(fr)])
    env = np.sqrt(np.convolve(x ** 2, np.ones(2205) / 2205, 'same')); on = np.nonzero(env > env.max() * 10 ** (-45 / 20))[0]
    y = x[max(0, int(on[0]) - 2205):min(len(x), int(on[-1]) + 17640)].copy(); f = int(.3 * 44100); y[-f:] *= np.linspace(1, 0, f) ** 2
    y = y / np.abs(y).max() * 10 ** (-12 / 20)
    d = os.path.join(DEST, 'cartmusic.mp3'); write(y, d, 64, 44100)
    print(f'Around_the_world -> sounds/cartmusic.mp3  ({len(y) / 44100:.1f} s, {os.path.getsize(d) / 1048576:.2f} MB)')


def farts():
    for i, nm in enumerate(FARTS, 1):
        p = os.path.join(SOUNDS_RAW, nm + '.m4a')
        if not os.path.exists(p):
            print('missing', p); continue
        y, a, b = trim(load(p))
        y = y / np.sqrt((y ** 2).mean()) * 10 ** (FART_RMS_DB / 20)
        assert np.abs(y).max() < 10 ** (-12 / 20), p
        d = os.path.join(DEST, f'fart{i}.mp3'); write(y, d)
        print(f'{nm} -> sounds/fart{i}.mp3  kept {a:.2f}-{b:.2f} s  (peak {20 * np.log10(np.abs(y).max()):.1f} dB, {os.path.getsize(d) / 1024:.1f} KB)')


def trucks():
    for nm, dst, kbps in (('Truck_horn', 'truckhorn', 96), ('Truck_rumble', 'truckrumble', 64)):
        p = os.path.join(SOUNDS_RAW, nm + '.m4a')
        if not os.path.exists(p):
            print('missing', p); continue
        y, a, b = trim(load(p)); d = os.path.join(DEST, dst + '.mp3'); write(y, d, kbps)
        print(f'{nm} -> sounds/{dst}.mp3  kept {a:.2f}-{b:.2f} s  (rms {20 * np.log10(np.sqrt((y ** 2).mean())):.1f} dB, {os.path.getsize(d) / 1024:.1f} KB)')


def main():
    music()
    cartmusic()
    farts()
    trucks()
    os.makedirs(DEST, exist_ok=True)
    for src, dst in MAP.items():
        p = os.path.join(SOUNDS_RAW, src + '.m4a')
        if not os.path.exists(p):
            print('missing', p); continue
        y, a, b = trim(load(p))
        write(y, os.path.join(DEST, dst + '.mp3'))
        print(f'{src:13s} -> sounds/{dst}.mp3  kept {a:.3f}-{b:.3f} s  ({len(y) / SR * 1000:.0f} ms, {os.path.getsize(os.path.join(DEST, dst + ".mp3")) / 1024:.1f} KB)')


if __name__ == '__main__':
    sys.exit(main())
