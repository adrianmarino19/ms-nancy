"""
Ms. Nancy — M0: "Hello Nancy".

Goal of M0: open ONE live Realtime session, talk to her, hear her talk back.
No memory across restarts, no tools, no real personality yet.

THE ONE MENTAL MODEL:
    Voice is two streams at once.
      - UP:   mic frames stream continuously INTO the socket, from the mic's
              own audio thread (the `on_mic` callback below).
      - DOWN: her audio frames stream OUT; the main thread reads server events
              in a loop and plays audio deltas as they arrive.
    The server decides when you've stopped talking — that's why there's no
    push-to-talk button. See `turn_detection` below for how it decides.

Audio facts (OpenAI Realtime): PCM16, 24 kHz, mono. Raw int16 bytes,
base64-encoded up, base64-decoded down. sounddevice's Raw streams pass bytes
straight through — no numpy.

Run:  uv run main.py     (Ctrl-C to stop)
Use headphones. On open speakers she hears herself and interrupts herself.

Pi note: all hardware lives in audio.py. That file is the whole port.
"""

import base64
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from audio import SAMPLE_RATE, Speaker, open_mic

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-realtime"

DEBUG = bool(os.getenv("DEBUG"))

# ECHO PROBE. Unset for normal runs. Set to a negative dB to fake her voice
# leaking into the mic at that level below what the speaker played — see
# `open_mic` in audio.py. Wear headphones (so the only echo is the fake one) and
# sweep until she stops interrupting herself:
#
#     ECHO_DB=-20 DEBUG=1 uv run main.py     # expect self-interruption
#     ECHO_DB=-30 DEBUG=1 uv run main.py
#     ECHO_DB=-40 DEBUG=1 uv run main.py     # expect clean
#
# The level where it goes clean is the suppression the real mic array must beat.
ECHO_DB = float(os.environ["ECHO_DB"]) if os.getenv("ECHO_DB") else None

# M0 personality is deliberately almost nothing. One line. Fleshed out at M1.
INSTRUCTIONS = "You are Ms. Nancy, a warm librarian. Keep replies short and spoken-friendly."

_T0 = time.monotonic()


def log(msg: str) -> None:
    """Timestamped trace. Chatty lines are DEBUG-only; warnings always print."""
    print(f"[{time.monotonic() - _T0:7.2f}s] {msg}")


def trace(msg: str) -> None:
    if DEBUG:
        log(msg)


def main() -> None:
    # Open the speaker once; we hand her audio to it as deltas arrive. play()
    # returns immediately, so this thread stays free to read the socket.
    speaker = Speaker()
    speaker.start()

    with client.realtime.connect(model=MODEL) as conn:
        # 1) CONFIGURE THE SESSION. One message, sent before anything else.
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": INSTRUCTIONS,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                        # TURN DETECTION — the hardest judgement call in the loop:
                        # is this silence a pause, or an ending?
                        #
                        # server_vad only measures silence, so a mid-thought pause
                        # past silence_duration_ms reads as "done". That one mistake
                        # chops your sentence into two turns, hands Whisper fragments
                        # to transcribe, and makes her lunge into your thinking pause.
                        #
                        # semantic_vad classifies the WORDS you have said so far to
                        # judge whether you are finished — so trailing off on "and..."
                        # or "ummm" waits, while a settled question fires fast.
                        # (Lexical, per OpenAI's docs. Not prosody — do not claim it
                        # listens to your intonation, that is unsupported.)
                        #
                        # eagerness tunes the maximum wait timeout. "low" because the
                        # two errors are not equally bad: answering early cuts you off,
                        # answering late costs a beat you barely notice. Bias to wait.
                        "turn_detection": {"type": "semantic_vad", "eagerness": "low"},
                        # Transcribes YOUR speech too, so the printed conversation
                        # has both sides. Costs one extra model call per turn.
                        "transcription": {"model": "whisper-1"},
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                        "voice": "marin",
                    },
                },
            }
        )

        # 2) START THE MIC. This callback runs on a separate audio thread and
        #    streams frames UP into the socket while the main thread reads DOWN.
        def on_mic(pcm: bytes) -> None:
            # THE MEASUREMENT. We are handed 20ms of audio every 20ms. If the
            # send takes longer than 20ms, we cannot keep up in real time and the
            # backlog grows without bound — the server's VAD is then judging audio
            # from seconds ago, and your barge-in arrives that late.
            t = time.monotonic()
            conn.input_audio_buffer.append(audio=base64.b64encode(pcm).decode("ascii"))
            took = (time.monotonic() - t) * 1000
            if took > 20:
                log(f"[lag] mic send blocked {took:.0f}ms")

        mic = open_mic(on_mic, echo=(speaker, ECHO_DB) if ECHO_DB is not None else None)

        print("Ms. Nancy is listening. Say hi. (Ctrl-C to stop)")
        if ECHO_DB is not None:
            print(f"[probe] faking {ECHO_DB:g}dB of echo into the mic — headphones only")

        # BARGE-IN STATE. The server sends her audio faster than realtime, so the
        # speaker queue runs "ahead" of what you've actually heard. We track which
        # item is playing; the speaker tracks how much of it the card really played.
        speaking: str | None = None  # item_id of the reply currently playing
        # Every item you barged in on. A set, not one slot: cuts can land within
        # a couple hundred ms of each other, and a single slot lets the older
        # item's stragglers through.
        cut: set[str] = set()

        # 3) THE EVENT LOOP. Everything the server sends arrives here; route by type.
        try:
            for event in conn:
                # Run with DEBUG=1 to see every event type the server sends.
                if event.type != "response.output_audio.delta":
                    trace(f"  <- {event.type}")

                if event.type == "response.output_audio.delta":
                    # Deltas already in flight when you barged in keep arriving for
                    # a beat afterwards. Playing them is an audible burp of her voice
                    # after she was supposed to have stopped. Drop them.
                    if event.item_id in cut:
                        continue
                    if speaking != event.item_id:
                        speaking = event.item_id
                        speaker.reset()  # new reply — start counting its playback
                        trace(f"audio starts ({event.item_id[-6:]})")
                    speaker.play(base64.b64decode(event.delta))

                elif event.type == "input_audio_buffer.speech_started":
                    still_audible = speaker.is_playing()
                    trace(f"speech_started (she was {'talking' if still_audible else 'silent'})")
                    # You started talking over her. Two halves, and both matter:
                    if speaking and still_audible:
                        # (a) LOCAL: drop every queued frame instantly, and get
                        #     back the ms the sound card actually played.
                        heard_ms = speaker.flush()
                        # (b) REMOTE: tell her she only got that far, so her memory
                        #     matches what you actually heard. Without this she'd
                        #     "remember" saying a paragraph you cut off after 2 words.
                        conn.conversation.item.truncate(
                            item_id=speaking,
                            content_index=0,
                            audio_end_ms=heard_ms,
                        )
                        trace(f"barge-in: cut after {heard_ms}ms heard")
                        cut.add(speaking)
                        speaking = None

                elif event.type == "response.done":
                    # Deliberately does NOT clear `speaking`. Generation finishing
                    # is not her mouth closing — the speaker still holds seconds of
                    # her voice. Clearing here was the whole barge-in bug: every
                    # interruption after this event found `speaking = None` and did
                    # nothing. `speaker.is_playing()` is the real "is she talking".
                    pass
                elif event.type == "conversation.item.input_audio_transcription.completed":
                    print(f"You:   {event.transcript.strip()}")
                elif event.type == "response.output_audio_transcript.done":
                    print(f"Nancy: {event.transcript}")
                elif event.type == "error":
                    print(f"[error] {event.error}")
        except KeyboardInterrupt:
            print("\nGoodnight.")
        finally:
            mic.stop()
            speaker.stop()


if __name__ == "__main__":
    main()
