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

import sounddevice as sd

# Realtime audio is PCM16 / 24 kHz / mono — the only rate audio/pcm accepts.
SAMPLE_RATE = 24000
CHANNELS = 1
BYTES_PER_FRAME = 2  # int16 mono

# 20ms of mic per chunk. Was 100ms, which put a fifth of a second of dead air
# between you speaking and the server hearing it. 50 sends/sec is nothing.
MIC_BLOCK = 480


class Speaker:
    """Non-blocking playback with an instant, exact flush."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._played = 0  # frames the sound card has actually consumed
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
        """True while the sound card still has audio of hers left to play.

        THIS is what "she is still talking" means — not the server's
        `response.done`, which only says generation finished. Audio arrives
        faster than realtime, so the server is done seconds before your ear is.
        """
        with self._lock:
            return bool(self._buf)

    def flush(self) -> int:
        """Drop everything unplayed. Returns ms actually heard, then resets.

        The return value is what the server needs to trim her transcript to
        match reality — she should only remember the part you let her finish.
        """
        with self._lock:
            self._buf.clear()
            ms = self._played * 1000 // SAMPLE_RATE
            self._played = 0
            return ms

    def stop(self) -> None:
        self._stream.stop()
        self._stream.close()


def open_mic(on_chunk) -> sd.RawInputStream:
    """Start the mic. `on_chunk(bytes)` runs on the audio thread — keep it fast.

    ponytail: on_chunk does its websocket send inline on the audio thread. Fine
    at this size; if you ever see `[mic] input overflow`, hand the bytes to a
    queue and let a sender thread do the socket work.
    """

    def callback(indata, frames, time_info, status) -> None:
        if status:
            print(f"[mic] {status}")
        on_chunk(bytes(indata))

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


def demo() -> None:
    """Self-check: play() must not block, and flush() must report real time."""
    import time

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
    sp.stop()
    print(f"ok — pushed 10s in {elapsed*1000:.1f}ms, reported {ms}ms played")


if __name__ == "__main__":
    demo()
