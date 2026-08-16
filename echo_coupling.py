"""
Measure how much of the speaker gets into the mic. The other half of the probe.

`ECHO_DB` in main.py told us the TARGET: echo must land at or below roughly
-40dB of what the speaker played, or the server mistakes her for you. This
script measures where a given physical setup actually SITS, in the same units.

    coupling (measured here)  +  AEC suppression (bought)  <=  target (-40dB)

Without this number "buy something with AEC" is unfalsifiable — a datasheet
claiming 30dB of suppression is either plenty or useless depending on whether
the box leaks at -20dB or -5dB, and nobody knows which until it is measured.

Run it on the MacBook to anchor a known-broken device. Run it again on the real
mic array and speaker to find out whether the hardware actually clears the bar.

    uv run echo_coupling.py          # SPEAKERS ON, headphones off, quiet room
    uv run echo_coupling.py --check  # arithmetic self-test, no hardware needed

Set the system volume to what you would really use at night BEFORE running, and
write it down with the result: coupling is a property of the volume too, and
halving the volume moves this number as surely as changing the enclosure does.
"""

import sys

import numpy as np
import sounddevice as sd

from audio import SAMPLE_RATE

SECONDS = 3.0
# -20dBFS RMS, roughly where speech sits. Crest factor of noise puts peaks near
# -8dBFS, so the speaker is driven hard but not clipped.
TEST_RMS = 0.1
# Ignore the start and end of the recording: the speaker ramps up, and the
# playback and capture streams do not begin on the same sample.
EDGE = 0.4


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def db(ratio: float) -> float:
    """Ratio to dB, floored so a silent recording prints instead of exploding."""
    return 20 * np.log10(max(ratio, 1e-9))


def coupling_db(recorded: float, floor: float, played: float) -> float | None:
    """How far below the played signal the leaked signal landed.

    The room's own noise is in `recorded` too, and at low coupling it dominates.
    Powers add, so subtract it as power — and if what is left is not meaningfully
    above the floor, return None rather than a number that is really just noise.
    """
    leak_power = recorded**2 - floor**2
    if leak_power <= 0 or recorded < floor * 1.4:  # <3dB over the floor is not a signal
        return None
    return db(np.sqrt(leak_power) / played)


def measure() -> None:
    print(f"Quiet, please — measuring the room for {SECONDS:g}s.")
    floor = rms(sd.rec(int(SECONDS * SAMPLE_RATE), SAMPLE_RATE, 1, blocking=True))
    print(f"  noise floor: {db(floor):.1f} dBFS")

    rng = np.random.default_rng(0)
    noise = (rng.standard_normal((int(SECONDS * SAMPLE_RATE), 1)) * TEST_RMS).astype(np.float32)
    print(f"Playing {SECONDS:g}s of noise out loud. Do not talk, do not move the laptop.")
    heard = sd.playrec(noise, SAMPLE_RATE, channels=1, blocking=True)

    edge = int(EDGE * SAMPLE_RATE)
    played, recorded = rms(noise[edge:-edge]), rms(heard[edge:-edge])
    print(f"  played:   {db(played):.1f} dBFS")
    print(f"  recorded: {db(recorded):.1f} dBFS")

    c = coupling_db(recorded, floor, played)
    if c is None:
        print("\nThe mic heard nothing above the room. Raise the volume or check the")
        print("output device — a real coupling measurement needs the speaker audible.")
        return

    print(f"\n  COUPLING: {c:.1f} dB")
    # -40dB is where ECHO_DB stopped breaking turn detection. See main.py.
    need = -40 - c
    if need <= 0:
        print("  Already below the -40dB target. This setup needs no echo cancellation.")
    else:
        print(f"  Needs {need:.0f} dB of echo cancellation to reach the -40dB target.")


def check() -> None:
    """Arithmetic only — the hardware path is the user's job to run."""
    assert abs(db(0.1) + 20) < 1e-9
    # Clean case: leak 20dB under the played signal, negligible room noise.
    assert abs(coupling_db(0.01, 1e-6, 0.1) - -20) < 0.01
    # The floor must be removed as power, not ignored: equal parts leak and noise
    # read 3dB hot, and taking that at face value would flatter the hardware.
    assert abs(coupling_db(np.sqrt(2) * 0.01, 0.01, 0.1) - -20) < 0.01
    # Buried in noise is not a measurement.
    assert coupling_db(0.010, 0.0099, 0.1) is None
    print("ok")


if __name__ == "__main__":
    check() if "--check" in sys.argv else measure()
