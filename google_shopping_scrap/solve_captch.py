import os
import argparse
from faster_whisper import WhisperModel

def solve_audio_captcha(audio_file_path = "captcha_audio.mp4", model_size = "base"):
    """
    Transcribes an audio file using the faster-whisper model.

    Args:
        audio_file_path: The absolute or relative path to the audio file.
        model_size: The size of the whisper model to use. 
                    "base" or "tiny" are usually sufficient and fastest for CAPTCHAs.

    Returns:
        The transcribed text as a single string.
    """
    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    # Initialize the model. 
    # device="cpu" is used for maximum compatibility. If you have an NVIDIA GPU, 
    # you can change this to device="cuda" and compute_type="float16" for even faster speeds.
    # The compute_type="int8" reduces memory usage on CPU.
    print(f"Loading '{model_size}' model...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transcribing '{audio_file_path}'...")
    # beam_size=5 is the default for faster-whisper, providing a good balance 
    # of speed and accuracy.
    segments, info = model.transcribe(audio_file_path, beam_size=5)

    print(f"Detected language: '{info.language}' with probability {info.language_probability:.2f}")

    # Segments is a generator, so we iterate through it to build the final text
    transcription = ""
    for segment in segments:
        transcription += segment.text

    # Clean up the transcription (remove leading/trailing spaces and newlines)
    final_text = transcription.strip()
    return final_text
