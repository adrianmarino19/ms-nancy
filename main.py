"""
Ms. Nancy — M0: "Hello Nancy".

Goal of M0: open ONE live Realtime session, talk to her, hear her talk back.
No memory, no tools, no real personality yet. If talking to her feels good,
M0 is done and everything else is additive.

THE ONE MENTAL MODEL for M0:
    Voice is two streams at once.
      - UP:   your mic frames stream continuously INTO the socket.
      - DOWN: her audio frames stream continuously OUT of the socket.
    They run concurrently. The mic runs on its own audio thread (the
    `on_mic` callback below). The main thread just reads server events in a
    loop and plays whatever audio comes down. Server VAD (voice-activity
    detection) decides when you've stopped talking — that's why there's no
    push-to-talk button.

Audio facts (OpenAI Realtime): PCM16, 24 kHz, mono. We move raw int16 bytes,
base64-encoded on the way up, base64-decoded on the way down. Using
sounddevice's Raw streams means we pass bytes straight through — no numpy.

Run:  uv run main.py     (Ctrl-C to stop)

Pi note: every microphone/speaker line lives in this file for now. When we
port to the Pi, this audio code is all that changes — extract it to audio.py
then. Not now (YAGNI).
"""

import base64
import os

import sounddevice as sd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Realtime audio is PCM16 / 24kHz / mono. Don't change these without reason.
SAMPLE_RATE = 24000
CHANNELS = 1
BLOCK = 2400  # ~100ms of mic audio per chunk sent up

# TODO(you): the real Realtime model id (you said you'd look it up).
MODEL = "TODO-realtime-model-id"

# M0 personality is deliberately almost nothing. One line. We flesh this out at M1.
INSTRUCTIONS = "You are Ms. Nancy, a warm librarian. Keep replies short and spoken-friendly."


def main():
    # Open the speaker once; we write her audio into it as deltas arrive.
    speaker = sd.RawOutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16")
    speaker.start()

    with client.realtime.connect(model=MODEL) as conn:
        # 1) CONFIGURE THE SESSION.
        # TODO(you): fill the session config. You want, at minimum:
        #   - audio output enabled + a voice (e.g. "alloy" / "marin" — pick one)
        #   - turn_detection set to server VAD, so SHE decides when you stopped talking
        #   - input/output audio format = pcm16
        # Hint: conn.session.update(session={ ... }). Read the RealtimeSessionResource
        # docstring / the session_update param types if unsure what keys it takes.
        conn.session.update(session={
            # TODO: your config here
        })

        # 2) START THE MIC. Its callback runs on a separate audio thread and streams
        #    frames UP into the socket. (conn's send is thread-safe, so this is fine.)
        def on_mic(indata, frames, time_info, status):
            # `indata` is a buffer of raw int16 bytes (because RawInputStream).
            # TODO(you): base64-encode these bytes and append them to the input buffer.
            #   b64 = base64.b64encode(bytes(indata)).decode("ascii")
            #   conn.input_audio_buffer.append(audio=b64)
            pass

        mic = sd.RawInputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
            blocksize=BLOCK, callback=on_mic,
        )
        mic.start()

        print("Ms. Nancy is listening. Say hi. (Ctrl-C to stop)")

        # 3) THE EVENT LOOP. Everything the server sends comes through here.
        #    Route by event.type. For M0 you only need a handful.
        try:
            for event in conn:
                # TODO(you): handle these event types (print event.type first to SEE them):
                #   - "response.output_audio.delta": her audio chunk. Decode + play:
                #       speaker.write(base64.b64decode(event.delta))
                #   - "response.output_audio_transcript.done" (optional): print what she said
                #   - "error": print event.error so failures aren't silent
                # Start by just: print(event.type)  ... then fill in the branches.
                pass
        except KeyboardInterrupt:
            print("\nGoodnight.")
        finally:
            mic.stop()
            speaker.stop()


if __name__ == "__main__":
    main()
