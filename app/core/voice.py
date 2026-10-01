import os
import io
from typing import Optional, Union, BinaryIO
from openai import OpenAI

def transcribe_audio(
    audio_file_or_bytes: Union[BinaryIO, bytes, io.BytesIO],
    filename: str = "audio.wav",
    api_key: Optional[str] = None
) -> str:
    """
    Transcribes spoken user audio into text using OpenAI Whisper API (`whisper-1`).
    Accepts bytes, file-like objects, or file paths.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API Key not configured for Whisper transcription.")

    client = OpenAI(api_key=api_key)

    if isinstance(audio_file_or_bytes, bytes):
        audio_stream = io.BytesIO(audio_file_or_bytes)
        audio_stream.name = filename
    elif hasattr(audio_file_or_bytes, "read"):
        audio_stream = audio_file_or_bytes
        if not hasattr(audio_stream, "name"):
            audio_stream.name = filename
    else:
        raise ValueError("Unsupported audio input format. Expected bytes or file stream.")

    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_stream
    )

    return transcription.text.strip()
