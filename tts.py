"""
tts.py
Reads output/script.txt and converts it to an mp3 using edge-tts
(Microsoft's free, unlimited text-to-speech engine — no API key needed).
"""

import asyncio
import edge_tts

TEXT_PATH = "output/script.txt"
AUDIO_OUTPUT_PATH = "output/podcast.mp3"

# Some good voice options:
#   en-US-AndrewNeural   - natural US male, conversational
#   en-US-AvaNeural      - natural US female
#   en-IN-NeerjaNeural   - Indian English female
#   en-IN-PrabhatNeural  - Indian English male
VOICE = "en-US-AndrewNeural"
RATE = "+0%"     # e.g. "+10%" to speak faster


async def generate_audio():
    with open(TEXT_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    communicate = edge_tts.Communicate(text, voice=VOICE, rate=RATE)
    await communicate.save(AUDIO_OUTPUT_PATH)
    print(f"Saved audio to {AUDIO_OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(generate_audio())
