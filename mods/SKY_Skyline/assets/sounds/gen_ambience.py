#!/usr/bin/env python3
"""Procedural ambient loops (D65): hypermarket tube hum, sewer drips, Ferris-wheel creak.

    python mods/SKY_Skyline/assets/sounds/gen_ambience.py

Writes addons/sky_sounds/data/sky_hum.ogg, sky_drips.ogg, sky_creak.ogg (mono, 22.05 kHz, Vorbis q3).
Each loop is seamless: the tail is cross-faded into the head over XFADE s. Played by the client ambience
director (4_World/SKY/SKY_Ambience.c) on at most three nearby sources. Deterministic (fixed seeds).
"""
import os
import subprocess
import tempfile
import wave

import numpy as np

SR = 22050
XFADE = 0.5
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "addons", "sky_sounds", "data")


def loopable(x):
    n = int(XFADE * SR)
    head, tail = x[:n].copy(), x[-n:].copy()
    ramp = np.linspace(0, 1, n)
    x = x[:-n].copy()
    x[:n] = head * ramp + tail * (1 - ramp)
    return x


def hum(rng):
    t = np.arange(int(8.5 * SR)) / SR
    x = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((100, 1.0), (200, 0.45), (300, 0.25), (400, 0.12), (1200, 0.05)))
    buzz = rng.standard_normal(t.size) * (0.15 + 0.15 * (np.sin(2 * np.pi * 0.37 * t) > 0.97))   # a failing ballast
    x = x * (1 + 0.04 * np.sin(2 * np.pi * 0.2 * t)) + buzz
    return x


def drips(rng):
    t = np.arange(int(10.5 * SR)) / SR
    x = 0.04 * np.convolve(rng.standard_normal(t.size), np.ones(40) / 40, mode="same")      # distant trickle
    for _ in range(26):
        t0 = rng.uniform(0, t[-1] - 0.3)
        f = rng.uniform(900, 2200)
        i = int(t0 * SR)
        k = np.arange(int(0.18 * SR)) / SR
        d = np.sin(2 * np.pi * (f + 1800 * k) * k) * np.exp(-k * 38) * rng.uniform(0.3, 1.0)
        x[i:i + d.size] += d
    out = x.copy()
    for delay, g in ((0.07, 0.45), (0.15, 0.3), (0.31, 0.2), (0.52, 0.12)):                  # tunnel reverb
        n = int(delay * SR)
        out[n:] += g * x[:-n]
    return out


def creak(rng):
    t = np.arange(int(12.5 * SR)) / SR
    wind = np.convolve(rng.standard_normal(t.size), np.ones(120) / 120, mode="same") * (0.6 + 0.4 * np.sin(2 * np.pi * 0.08 * t))
    x = 0.5 * wind
    for _ in range(5):
        t0 = rng.uniform(0.5, t[-1] - 2.0)
        dur = rng.uniform(0.6, 1.4)
        k = np.arange(int(dur * SR)) / SR
        f = rng.uniform(140, 260) * (1 + 0.3 * np.sin(2 * np.pi * k / dur))
        ph = 2 * np.pi * np.cumsum(f) / SR
        stick = (np.sin(2 * np.pi * rng.uniform(18, 30) * k) > 0.2).astype(float)          # stick-slip
        c = (np.sign(np.sin(ph)) * 0.6 + np.sin(3 * ph) * 0.3) * stick * np.sin(np.pi * k / dur)
        i = int(t0 * SR)
        x[i:i + c.size] += 0.7 * c
    return x


def write(name, x):
    x = loopable(x)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.85
    pcm = (x * 32767).astype(np.int16)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, name + ".wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "3", "-map_metadata", "-1",
                        "-fflags", "+bitexact", "-flags:a", "+bitexact", os.path.join(OUT, name + ".ogg")], check=True)
    print("wrote", name + ".ogg")


def main():
    os.makedirs(OUT, exist_ok=True)
    write("sky_hum", hum(np.random.default_rng(651)))
    write("sky_drips", drips(np.random.default_rng(652)))
    write("sky_creak", creak(np.random.default_rng(653)))


if __name__ == "__main__":
    main()
