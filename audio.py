"""
Mic and speaker for Ms. Nancy. The only file that touches hardware.

WHY THIS EXISTS: `RawOutputStream.write()` blocks in realtime — pushing 8
seconds of audio parks the caller for 8 seconds. When the caller is also the
thread reading the websocket, the socket goes unread for the whole reply, so
"stop talking" events arrive too late to act on. Interruption is impossible by
construction.

The fix is to stop pushing audio and start letting the sound card pull it.
`Speaker.play()` appends to a buffer and returns in microseconds; PortAudio's
own high-priority thread drains that buffer via `_on_speaker`. Nothing on the
main thread ever waits for the speaker again.

Pulling also gives us the truth for free: `_played` counts frames the sound
card actually consumed, so "how much did she really say" stops being a
wall-clock guess.

Pi note: this file is the port. Nothing else touches hardware.
"""

import threading
import time

import numpy as np
import sounddevice as sd

# Realtime audio is PCM16 / 24 kHz / mono — the only rate audio/pcm accepts.
SAMPLE_RATE = 24000
CHANNELS = 1
BYTES_PER_FRAME = 2  # int16 mono

# 20ms of mic per chunk. Was 100ms, which put a fifth of a second of dead air
# between you speaking and the server hearing it. 50 sends/sec is nothing.
MIC_BLOCK = 480

# How long a gap in her audio we forgive before calling her silent. Covers
# network jitter between deltas without waiting out a real end-of-reply.
GAP_GRACE = 0.25

# Rolling copy of what the card just played, for the echo probe (see `open_mic`).
# 100ms is far more than the ~1.5ms an acoustic path 0.5m away would add.
TAP_BYTES = SAMPLE_RATE // 10 * BYTES_PER_FRAME


class Speaker:
    """Non-blocking playback with an instant, exact flush."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._tap = bytearray()  # echo probe only; see recently_played()
        self._played = 0  # frames the sound card has actually consumed
        self._last_audio = 0.0  # when the card last got real audio, not silence
        self._lock = threading.Lock()
        self._stream = sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._on_speaker,
            # Ask CoreAudio for the smallest buffer it will give us. This is the
            # floor on how fast a flush can take effect — audio already handed to
            # the driver is gone, we can't recall it.
            latency="low",
        )

    def start(self) -> None:
        self._stream.start()

    def _on_speaker(self, outdata, frames, time_info, status) -> None:
        # Runs on PortAudio's thread. Must never block and must always fill
        # `outdata` completely — a short write is an audible click.
        need = frames * BYTES_PER_FRAME
        with self._lock:
            chunk = bytes(self._buf[:need])
            del self._buf[:need]
            self._played += len(chunk) // BYTES_PER_FRAME
            self._tap += chunk
            del self._tap[:-TAP_BYTES]
            if chunk:
                self._last_audio = time.monotonic()
        # Underrun (she isn't talking, or the network stalled) — silence is correct.
        outdata[:] = chunk + b"\x00" * (need - len(chunk))

    def play(self, pcm: bytes) -> None:
        with self._lock:
            self._buf += pcm

    def reset(self) -> None:
        """Zero the played counter without touching queued audio.

        Separate from flush() on purpose: a new reply starting is not a reason
        to throw away audio that's still playing.
        """
        with self._lock:
            self._played = 0

    def is_playing(self) -> bool:
        """True while she is still audibly talking.

        THIS is what "she is still talking" means — not the server's
        `response.done`, which only says generation finished. Audio arrives
        faster than realtime, so the server is done seconds before your ear is.

        An empty buffer alone is NOT proof she stopped: it empties briefly
        whenever the next delta is late, which is routine at the start of a
        reply and on any network stall. Answering False there silently disables
        barge-in for the rest of the reply — the exact bug this method exists to
        fix. So we stay "talking" through a short gap.

        ponytail: 250ms grace, tuned on a Mac over good wifi. A Pi on flaky
        wifi may need more; raise it if interruptions start getting ignored
        mid-reply.
        """
        with self._lock:
            return bool(self._buf) or (time.monotonic() - self._last_audio) < GAP_GRACE

    def recently_played(self, nbytes: int) -> bytes:
        """The last `nbytes` the sound card actually played. Echo probe only.

        Left-padded with silence when she has not been talking that long, so the
        caller always gets exactly `nbytes` back and never has to size-match.
        """
        with self._lock:
            return bytes(self._tap[-nbytes:]).rjust(nbytes, b"\x00")

    def flush(self) -> int:
        """Drop everything unplayed. Returns ms actually heard, then resets.

        The return value is what the server needs to trim her transcript to
        match reality — she should only remember the part you let her finish.
        """
        with self._lock:
            self._buf.clear()
            ms = self._played * 1000 // SAMPLE_RATE
            self._played = 0
            self._last_audio = 0.0  # cut means cut: she is not talking any more
            return ms

    def stop(self) -> None:
        self._stream.stop()
        self._stream.close()


def open_mic(on_chunk, echo: tuple["Speaker", float] | None = None) -> sd.RawInputStream:
    """Start the mic. `on_chunk(bytes)` runs on the audio thread — keep it fast.

    `echo=(speaker, db)` runs the ECHO PROBE: mix a copy of what the speaker just
    played back into the mic at `db` below its original level, simulating her
    voice leaking into the mic acoustically. Wear headphones so the only echo in
    the system is this one, and sweep `db` to find the level at which the server
    stops mistaking her for you. That threshold is the amount of suppression the
    real hardware has to buy us — see `specs/hardware-decision-brief.md`.

    It is a deliberate under-model: real echo is also delayed, colored by the
    speaker and room, and smeared by reverb, all of which make it *less*
    intelligible than this clean copy. So the number it reports is pessimistic,
    which is the safe direction to be wrong in when writing a shopping list.

    ponytail: on_chunk does its websocket send inline on the audio thread. Fine
    at this size; if you ever see `[mic] input overflow`, hand the bytes to a
    queue and let a sender thread do the socket work.
    """

    def callback(indata, frames, time_info, status) -> None:
        if status:
            print(f"[mic] {status}")
        pcm = bytes(indata)
        if echo:
            speaker, db = echo
            pcm = mix(pcm, speaker.recently_played(len(pcm)), db)
        on_chunk(pcm)

    mic = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=MIC_BLOCK,
        latency="low",
        callback=callback,
    )
    mic.start()
    return mic


def mix(mic: bytes, leak: bytes, db: float) -> bytes:
    """`mic` plus `leak` attenuated by `db`. Both PCM16, same length.

    int32 in the middle because two int16s can sum past int16 — wrapping there
    would turn a quiet echo into a loud click, which is the opposite of the
    thing we are trying to measure.
    """
    a = np.frombuffer(mic, np.int16).astype(np.int32)
    b = np.frombuffer(leak, np.int16) * (10 ** (db / 20))
    return np.clip(a + b, -32768, 32767).astype(np.int16).tobytes()


def demo() -> None:
    """Self-check: play() must not block, and flush() must report real time."""
    sp = Speaker()
    sp.start()
    one_sec = bytes(SAMPLE_RATE * BYTES_PER_FRAME)

    t = time.monotonic()
    for _ in range(10):  # 10 seconds of audio, pushed as fast as we can
        sp.play(one_sec)
    elapsed = time.monotonic() - t
    assert elapsed < 0.1, f"play() blocked for {elapsed:.2f}s — the whole bug is back"

    time.sleep(0.5)
    # The barge-in bug in one assert: 9 seconds still queued, so she is audibly
    # talking — even though the server called this response "done" long ago.
    assert sp.is_playing(), "is_playing() must be true while audio is still queued"

    ms = sp.flush()
    assert 300 < ms < 900, f"expected ~500ms actually played, got {ms}ms"
    assert sp.flush() == 0, "flush() must reset the counter"
    assert not sp.is_playing(), "flush() must leave nothing queued"

    # A gap between deltas must NOT read as "she stopped" — that silently
    # disables barge-in for the rest of the reply.
    sp.play(bytes(SAMPLE_RATE // 100 * BYTES_PER_FRAME))  # 10ms, drains at once
    time.sleep(0.1)
    assert sp.is_playing(), "a 100ms gap in her audio must still count as talking"
    time.sleep(GAP_GRACE)
    assert not sp.is_playing(), "a gap past GAP_GRACE means she really stopped"

    sp.stop()

    # Echo probe: -20dB must be a tenth of the original, and mixing must not wrap.
    loud = np.full(480, 20000, np.int16).tobytes()
    assert mix(bytes(960), loud, -20) == np.full(480, 2000, np.int16).tobytes()
    assert mix(loud, loud, 0) == np.full(480, 32767, np.int16).tobytes(), "must clip, not wrap"
    assert mix(loud, loud, -120) == loud, "silence in, mic out untouched"

    print(f"ok — pushed 10s in {elapsed*1000:.1f}ms, reported {ms}ms played")


if __name__ == "__main__":
    demo()
