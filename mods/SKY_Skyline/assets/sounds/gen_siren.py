#!/usr/bin/env python3
"""Procedural civil-defence siren for the SKY city alarm (D61, ROADMAP idea 20).

    python mods/SKY_Skyline/assets/sounds/gen_siren.py [--wav out.wav]

Writes addons/sky_sounds/data/sky_siren.ogg (mono, 22.05 kHz, Vorbis q4, 60 s) through ffmpeg.
Model: a two-rotor mechanical siren (10 and 12 ports, so two tones a minor third apart) spinning up
to about 520 Hz, holding, and winding down - three wails in a minute, as the Soviet-era towers do.
Each rotor tone is a sawtooth-ish harmonic stack with port-rate roughness; a few comb-filter echoes
give the street canyon reverb. Deterministic (fixed seed); numpy only. The engine sound shader
(sky_sounds/config.cpp) sets the 2.5 km range; the script plays it once per alarm (SKY_CityLife.c).
"""
import argparse
import os
import subprocess
import tempfile
import wave

import numpy as np

SR = 22050
DUR = 60.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "addons", "sky_sounds", "data", "sky_siren.ogg")


def rotor_speed(t):
    """Rotor speed 0..1 over time: three wails (spin-up 7 s, hold 6 s, wind-down 7 s)."""
    s = np.zeros_like(t)
    for start in (0.0, 20.0, 40.0):
        u = t - start
        up = np.clip(u / 7.0, 0, 1)
        up = 1 - (1 - up) ** 2                     # motor torque: fast start, slow approach
        down = np.clip((u - 13.0) / 7.0, 0, 1)
        down = down ** 0.7
        w = np.where((u >= 0) & (u < 20.0), up * (1 - down), 0.0)
        s = np.maximum(s, w)
    return s


def tone(phase, n_harm=7):
    out = np.zeros_like(phase)
    for k in range(1, n_harm + 1):
        out += np.sin(k * phase) / (k ** 1.15)
    return out


def synth():
    rng = np.random.default_rng(61)
    t = np.arange(int(SR * DUR)) / SR
    spd = rotor_speed(t)
    f_lo = 40.0 + 440.0 * spd                       # 10-port rotor
    f_hi = f_lo * 1.2                               # 12-port rotor (minor third)
    ph_lo = 2 * np.pi * np.cumsum(f_lo) / SR
    ph_hi = 2 * np.pi * np.cumsum(f_hi) / SR
    sig = tone(ph_lo) + 0.8 * tone(ph_hi)
    rough = 1.0 + 0.12 * np.sin(ph_lo / 10.0 * 3.0)  # port-rate amplitude ripple
    air = rng.standard_normal(t.size)
    air = np.convolve(air, np.ones(24) / 24, mode="same")   # wind rush of the rotor
    sig = sig * rough + 0.6 * air * spd
    sig *= np.clip(spd * 1.6, 0, 1) ** 1.3           # silent when stopped
    out = sig.copy()                                 # street canyon: a few late echoes
    for delay, gain in ((0.11, 0.35), (0.23, 0.25), (0.41, 0.18), (0.67, 0.12)):
        d = int(delay * SR)
        out[d:] += gain * sig[:-d]
    fade = np.minimum(1.0, np.minimum(t / 0.05, (DUR - t) / 0.5))
    out *= fade
    out /= np.max(np.abs(out)) + 1e-9
    return (out * 0.89 * 32767).astype(np.int16)


def write_wav(path, pcm):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wav", help="also keep the WAV here (preview)")
    a = ap.parse_args()
    pcm = synth()
    with tempfile.TemporaryDirectory() as td:
        wav = a.wav or os.path.join(td, "sky_siren.wav")
        write_wav(wav, pcm)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "4",
                        "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact", os.path.abspath(OUT)], check=True)
    print("wrote", os.path.relpath(os.path.abspath(OUT)), "%.1f s" % DUR)


if __name__ == "__main__":
    main()
