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
    Server VAD decides when you've stopped talking — that's why there's no
    push-to-talk button.

Audio facts (OpenAI Realtime): PCM16, 24 kHz, mono. Raw int16 bytes,
base64-encoded up, base64-decoded down. sounddevice's Raw streams pass bytes
straight through — no numpy.

Run:  uv run main.py     (Ctrl-C to stop)
Use headphones. On open speakers she hears herself and interrupts herself.

Pi note: every microphone/speaker line lives in this file for now. When we port
to the Pi, this audio code is all that changes — extract it to audio.py then.
"""

import base64
import os
import time

import sounddevice as sd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Realtime audio is PCM16 / 24kHz / mono. Don't change these without reason —
# 24000 is the only rate the API's audio/pcm format accepts.
SAMPLE_RATE = 24000
CHANNELS = 1
BLOCK = 2400

MODEL = "gpt-realtime"

DEBUG = bool(os.getenv("DEBUG"))

# M0 personality is deliberately almost nothing. One line. Fleshed out at M1.
INSTRUCTIONS = "You are Ms. Nancy, a warm librarian. Keep replies short and spoken-friendly."


def main() -> None:
    # Open the speaker once; we write her audio into it as deltas arrive.
    speaker = sd.RawOutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16")
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
                        # Server VAD: the server watches audio volume and decides
                        # when your turn ended. Swap to {"type": "semantic_vad"} if
                        # she cuts you off mid-thought — it waits on meaning, not volume.
                        "turn_detection": {"type": "server_vad"},
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
        def on_mic(indata, frames, time_info, status) -> None:
            if status:
                print(f"[mic] {status}")
            conn.input_audio_buffer.append(audio=base64.b64encode(bytes(indata)).decode("ascii"))

        mic = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK,
            callback=on_mic,
        )
        mic.start()

        print("Ms. Nancy is listening. Say hi. (Ctrl-C to stop)")

        # BARGE-IN STATE. The server sends her audio faster than realtime, so the
        # speaker queue runs "ahead" of what you've actually heard. To cut her off
        # we need to know which item is playing and roughly how far in we are.
        speaking: str | None = None  # item_id of the reply currently playing
        started_at = 0.0  # wall clock when its first frame hit the speaker

        # 3) THE EVENT LOOP. Everything the server sends arrives here; route by type.
        try:
            for event in conn:
                # Run with DEBUG=1 to see every event type the server sends.
                if DEBUG and event.type != "response.output_audio.delta":
                    print(f"  <- {event.type}")

                if event.type == "response.output_audio.delta":
                    if speaking != event.item_id:
                        speaking, started_at = event.item_id, time.monotonic()
                    speaker.write(base64.b64decode(event.delta))

                elif event.type == "input_audio_buffer.speech_started":
                    # You started talking over her. Two halves, and both matter:
                    if speaking:
                        # (a) LOCAL: abort() drops queued frames instantly.
                        #     stop() would politely drain them — the exact bug.
                        speaker.abort()
                        speaker.start()
                        # (b) REMOTE: tell her she only got this far, so her memory
                        #     matches what you actually heard. Without this she'd
                        #     "remember" saying a paragraph you cut off after 2 words.
                        # ponytail: wall-clock elapsed as a stand-in for true playback
                        # position. Accurate while the queue never underruns, which
                        # holds when audio arrives faster than realtime. If truncation
                        # lands visibly wrong, track frames written vs. consumed instead.
                        conn.conversation.item.truncate(
                            item_id=speaking,
                            content_index=0,
                            audio_end_ms=int((time.monotonic() - started_at) * 1000),
                        )
                        speaking = None

                elif event.type == "response.done":
                    speaking = None
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
