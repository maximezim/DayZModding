#!/usr/bin/env python3
"""Procedural guard-dog bark for the SKY kennel (D62, ROADMAP idea 5).

    python mods/SKY_Skyline/assets/sounds/gen_bark.py [--wav out.wav]

Writes addons/sky_sounds/data/sky_bark.ogg (mono, 22.05 kHz, Vorbis q4, ~2.2 s): a big dog's double bark
and a growl tail. Each bark is a glottal pulse train (fundamental ~ 260 Hz falling to 180 Hz) through three
formant resonators (~ 600 / 1300 / 2500 Hz) with breath noise and a sharp attack; the yard gives a short
slap-back echo. Deterministic (fixed seed); numpy only; ffmpeg encodes. Played by SKY_KennelSound
(4_World/SKY/SKY_CreatureLife.c) through SKY_Bark_SoundSet (sky_sounds/config.cpp).
"""
import argparse
import os
import subprocess
import tempfile
import wave

import numpy as np

SR = 22050
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "addons", "sky_sounds", "data", "sky_bark.ogg")


def resonator(x, f, bw):
    """Two-pole band-pass (formant)."""
    r = np.exp(-np.pi * bw / SR)
    c1, c2 = 2 * r * np.cos(2 * np.pi * f / SR), -r * r
    y = np.zeros_like(x)
    for i in range(2, x.size):
        y[i] = x[i] + c1 * y[i - 1] + c2 * y[i - 2]
    return y


def bark(rng, dur, f0, f1, gain):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 + (f1 - f0) * (t / dur) ** 0.6
    ph = 2 * np.pi * np.cumsum(f) / SR
    pulses = np.maximum(0, np.sin(ph)) ** 6                      # glottal-ish pulse train
    src = pulses + 0.35 * rng.standard_normal(n)                 # breath / rasp
    out = 1.0 * resonator(src, 620, 180) + 0.7 * resonator(src, 1350, 260) + 0.35 * resonator(src, 2600, 400)
    env = np.minimum(1.0, t / 0.012) * np.exp(-t / (dur * 0.45))
    return gain * out * env


def growl(rng, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(95 + 12 * np.sin(2 * np.pi * 7 * t)) / SR
    src = (np.maximum(0, np.sin(ph)) ** 4) * (1 + 0.6 * np.sin(2 * np.pi * 31 * t)) + 0.5 * rng.standard_normal(n)
    out = resonator(src, 420, 160) + 0.5 * resonator(src, 900, 300)
    env = np.minimum(1.0, t / 0.15) * np.minimum(1.0, (dur - t) / 0.3)
    return 0.35 * out * env


def synth():
    rng = np.random.default_rng(62)
    total = np.zeros(int(2.2 * SR))
    for start, dur, f0, f1, g in ((0.0, 0.22, 280, 190, 1.0), (0.34, 0.26, 300, 175, 1.1)):
        b = bark(rng, dur, f0, f1, g)
        i = int(start * SR)
        total[i:i + b.size] += b
    g = growl(rng, 1.3)
    i = int(0.8 * SR)
    total[i:i + g.size] += g[: total.size - i]
    out = total.copy()
    for delay, gain in ((0.045, 0.3), (0.09, 0.15)):              # yard slap-back
        d = int(delay * SR)
        out[d:] += gain * total[:-d]
    out /= np.max(np.abs(out)) + 1e-9
    return (out * 0.89 * 32767).astype(np.int16)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wav", help="also keep the WAV here (preview)")
    a = ap.parse_args()
    pcm = synth()
    with tempfile.TemporaryDirectory() as td:
        wav = a.wav or os.path.join(td, "sky_bark.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "4",
                        "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact", os.path.abspath(OUT)], check=True)
    print("wrote", os.path.relpath(os.path.abspath(OUT)))


if __name__ == "__main__":
    main()
