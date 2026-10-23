"""Speech in / speech out for push-to-talk. Separate from the chat LLM, which may be a local Ollama model
with no audio endpoints. Needs an OpenAI-compatible provider that serves transcription and TTS.

Configuration: VOICE_API_KEY (falls back to OPENAI_API_KEY, then LLM_API_KEY when LLM_BASE_URL is OpenAI),
VOICE_BASE_URL, VOICE_STT_MODEL, VOICE_TTS_MODEL, VOICE_TTS_VOICE.
"""
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_URL = "https://api.openai.com/v1"
GROQ_URL = "https://api.groq.com/openai/v1"

# Per-provider defaults. Orpheus on Groq accepts short inputs only (about 200 characters) and returns WAV.
PROFILES = {
    OPENAI_URL: dict(stt="gpt-4o-mini-transcribe", tts="gpt-4o-mini-tts", voice="alloy", fmt="mp3",
                     mime="audio/mpeg", chars=600),
    GROQ_URL: dict(stt="whisper-large-v3-turbo", tts="canopylabs/orpheus-v1-english", voice="hannah", fmt="wav",
                   mime="audio/wav", chars=190),
}

# Biases transcription toward the vocabulary the agent understands (codes are otherwise often misheard).
STT_PROMPT = ("US airports and aviation: ORD, JFK, LAX, SNA, SFO, ANC, BOS, BDL, PVD, terminal expansion, "
              "congestion, long-haul flights, unmet demand, New England.")


def _base_url() -> str:
    explicit = os.getenv("VOICE_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    llm = os.getenv("LLM_BASE_URL", "").rstrip("/")
    return llm if llm in PROFILES else OPENAI_URL


def _api_key() -> str | None:
    key = os.getenv("VOICE_API_KEY")
    if key:
        return key
    if _base_url() == os.getenv("LLM_BASE_URL", "").rstrip("/"):  # same provider as the chat model
        return os.getenv("LLM_API_KEY")
    return os.getenv("OPENAI_API_KEY")


def speakable(text: str, limit: int = 600) -> str:
    """Strip markdown and keep only the opening sentence; the full answer stays on screen."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`#>|]+", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    # The narration opens with a one-sentence direct answer; that bottom line is all that is read aloud.
    text = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text, maxsplit=1)[0]
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut.rsplit(" ", 1)[0] + "."


class Voice:
    def __init__(self):
        base = _base_url()
        prof = PROFILES.get(base, PROFILES[OPENAI_URL])
        self.stt_model = os.getenv("VOICE_STT_MODEL", prof["stt"])
        self.tts_model = os.getenv("VOICE_TTS_MODEL", prof["tts"])
        self.tts_voice = os.getenv("VOICE_TTS_VOICE", prof["voice"])
        self.fmt, self.mime, self.chars = prof["fmt"], prof["mime"], prof["chars"]
        self.client = OpenAI(base_url=base, api_key=_api_key(), timeout=60, max_retries=2)

    @staticmethod
    def available() -> bool:
        return bool(_api_key())

    def transcribe(self, audio) -> str:
        """`audio` is the file-like object from st.audio_input (a WAV with a name)."""
        resp = self.client.audio.transcriptions.create(
            model=self.stt_model, file=(getattr(audio, "name", None) or "speech.wav", audio.getvalue()),
            prompt=STT_PROMPT, language="en")
        return resp.text.strip()

    def speak(self, text: str) -> bytes:
        resp = self.client.audio.speech.create(model=self.tts_model, voice=self.tts_voice,
                                               input=speakable(text, self.chars), response_format=self.fmt)
        return resp.read()
