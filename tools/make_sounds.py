#!/usr/bin/env python3
"""Render the key-press sounds in ``sounds/`` from scratch.

These are synthesised here rather than sourced from a sample library so the
whole pack is unambiguously original and can be released CC0. Each one is a
short envelope over a handful of sine partials plus, where the sound wants a
mechanical edge, a filtered noise transient — the same approach the app's
built-in sounds use, aimed at four characters the built-ins don't cover.

Needs ffmpeg on PATH for the WAV -> MP3 step.

    python3 tools/make_sounds.py
"""

from __future__ import annotations

import math
import random
import struct
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sounds"
SAMPLE_RATE = 44_100


def envelope(index: int, total: int, decay_ms: float, attack_ms: float = 2.0) -> float:
    """Exponential decay with a short fade-in, so the onset doesn't click."""
    t = index / SAMPLE_RATE
    env = math.exp(-t * 1000.0 / decay_ms)
    attack = int(SAMPLE_RATE * attack_ms / 1000)
    if attack and index < attack:
        env *= index / attack
    return env


def render(
    duration_ms: int,
    decay_ms: float,
    partials: list[tuple[float, float, float]],
    noise: float = 0.0,
    noise_decay_ms: float = 6.0,
    square: bool = False,
    seed: int = 0,
) -> list[int]:
    """One sound. ``partials`` is a list of (start_hz, end_hz, gain)."""
    rng = random.Random(seed)
    n = SAMPLE_RATE * duration_ms // 1000
    phases = [0.0] * len(partials)
    mix = [0.0] * n
    peak = 0.0

    for i in range(n):
        sample = 0.0
        for j, (start_hz, end_hz, gain) in enumerate(partials):
            hz = start_hz + (end_hz - start_hz) * i / n
            phases[j] += 2.0 * math.pi * hz / SAMPLE_RATE
            wave_value = math.sin(phases[j])
            if square:
                wave_value = 1.0 if wave_value >= 0 else -1.0
            sample += gain * wave_value
        sample *= envelope(i, n, decay_ms)

        if noise:
            # A separate, much faster envelope: the transient is the "hit",
            # the partials are the body that rings after it.
            sample += noise * rng.uniform(-1.0, 1.0) * envelope(i, n, noise_decay_ms, 0.5)

        mix[i] = sample
        peak = max(peak, abs(sample))

    norm = (0.85 / peak) if peak else 0.0
    return [max(-32768, min(32767, int(v * norm * 32767))) for v in mix]


def write_wav(path: Path, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(struct.pack(f"<{len(samples)}h", *samples))


# (file stem, description, render kwargs)
SOUNDS: list[tuple[str, str, dict]] = [
    (
        "typewriter",
        "Mechanical typebar strike: a hard noise transient over a short woody thunk.",
        dict(
            duration_ms=110,
            decay_ms=22,
            partials=[(210.0, 150.0, 1.0), (420.0, 300.0, 0.25)],
            noise=0.9,
            noise_decay_ms=5.0,
            seed=1,
        ),
    ),
    (
        "marimba",
        "Soft wooden mallet: a warm fundamental with its characteristic ringing fourth harmonic.",
        dict(
            duration_ms=220,
            decay_ms=70,
            partials=[(523.25, 523.25, 1.0), (2093.0, 2093.0, 0.30)],
            noise=0.18,
            noise_decay_ms=3.0,
            seed=2,
        ),
    ),
    (
        "droplet",
        "Water drop: a fast upward pitch bend, no transient at all.",
        dict(
            duration_ms=130,
            decay_ms=34,
            partials=[(620.0, 1450.0, 1.0)],
            seed=3,
        ),
    ),
    (
        "blip",
        "Retro square-wave blip, 8-bit handheld flavour.",
        dict(
            duration_ms=70,
            decay_ms=20,
            partials=[(880.0, 880.0, 1.0)],
            square=True,
            seed=4,
        ),
    ),
]


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for stem, description, kwargs in SOUNDS:
        wav = OUT / f"{stem}.wav"
        mp3 = OUT / f"{stem}.mp3"
        write_wav(wav, render(**kwargs))
        result = subprocess.run(
            # Mono, 64 kbps, 44.1 kHz: these are ~100 ms clips, anything more
            # is bytes the keyboard has to load for no audible gain.
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
             "-codec:a", "libmp3lame", "-b:a", "64k", "-ac", "1", str(mp3)],
            capture_output=True,
            text=True,
        )
        wav.unlink()
        if result.returncode != 0:
            print(f"ffmpeg failed for {stem}: {result.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"{mp3.relative_to(ROOT)}  {mp3.stat().st_size:>7,} bytes  — {description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
