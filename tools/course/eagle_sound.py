"""Synthesise the eagle's screech -> ../../sounds/eagle.mp3 (the "EAGLE!" and albatross cards, `SFX.eagle` in index.html).

No recording is used (every public-domain eagle recording found is a quiet bald-eagle chitter, not the hawk-style scream films use for an eagle), so the file
is made here and nothing needs a licence: a harmonic tone that jumps up to ~2.8 kHz, hangs there with a slow shake and falls away to ~1.4 kHz over
about two seconds, with a light rasp, a little breath noise and a soft formant lift near 3 kHz, then low-passed at 5.5 kHz so it is not harsh. Mono, 44.1 kHz, 96 kbps, peak -6 dBFS.
Run it again after changing the recipe; commit sounds/eagle.mp3."""
import os

import numpy as np
from scipy.signal import butter, lfilter

from sounds_trim import DEST, write

SR = 44100


def screech(seed=7):
    rng = np.random.default_rng(seed)
    n = int(2.0 * SR); t = np.arange(n) / SR
    # pitch: a quick jump from 1.7 to ~3.2 kHz in 0.1 s, a shaky hold, then a long fall to ~1.4 kHz
    jump = 1 - np.exp(-t / .035)
    fall = np.clip((t - .25) / 1.6, 0, 1) ** 1.35
    f0 = 1600 + 1200 * jump - 1500 * fall
    f0 *= 1 + .02 * np.sin(2 * np.pi * 24 * t) * np.clip(t / .15, 0, 1) + .012 * np.sin(2 * np.pi * 6 * t)
    jit = lfilter(*butter(2, 300 / (SR / 2)), rng.standard_normal(n)); f0 *= 1 + .006 * jit / (np.abs(jit).max() + 1e-9) * 3
    ph = 2 * np.pi * np.cumsum(f0) / SR
    x = np.zeros(n)
    for h in range(1, 7):
        a = 1 / h ** 1.5
        fh = f0 * h
        x += a * np.sin(h * ph) * (fh < SR * .45)
    # rasp: a fast amplitude flutter and breath noise
    x *= 1 + .1 * np.sin(2 * np.pi * 48 * t + 2 * np.sin(2 * np.pi * 5 * t))
    b, a = butter(2, [1800 / (SR / 2), 6500 / (SR / 2)], 'band')
    noise = lfilter(b, a, rng.standard_normal(n)); x += .3 * noise / np.abs(noise).max() * np.abs(x).max() * .35
    # formant lift near 3 kHz
    b, a = butter(2, [2200 / (SR / 2), 3800 / (SR / 2)], 'band'); x += .35 * lfilter(b, a, x)
    # envelope: a fast attack, a loud body, a long falling tail
    env = np.minimum(t / .09, 1) * np.where(t < .55, 1, np.exp(-(t - .55) / .6)) * np.minimum((2.0 - t) / .08, 1)
    x *= env
    b, a = butter(3, 5500 / (SR / 2)); x = lfilter(b, a, x)   # no fizz above 5.5 kHz
    return x / np.abs(x).max() * 10 ** (-6 / 20)


if __name__ == '__main__':
    y = screech()
    d = os.path.join(DEST, 'eagle.mp3'); write(y, d)
    print(f'eagle screech -> sounds/eagle.mp3 ({len(y) / SR:.1f} s, {os.path.getsize(d) / 1024:.1f} KB)')
