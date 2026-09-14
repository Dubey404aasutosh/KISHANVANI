import torch
import sys
from transformers import pipeline

class ASRTranscriber:
    def __init__(self, model_id="openai/whisper-small", device=None):
        """
        Initializes the Whisper ASR pipeline.
        Defaulting to 'openai/whisper-small' for fast prototyping.
        To use the full fallback mentioned in the brief, pass model_id="openai/whisper-large-v3".
        """
        if device is None:
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            
        print(f"Loading ASR model {model_id} on {device}...")
        
        # We use pipeline for robust and easy ASR with huggingface models
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            chunk_length_s=30,
            device=device,
        )
        
    # Maps our internal short codes (used across generation/guardrail/tts) to
    # the full language names Whisper's generate_kwargs expects.
    WHISPER_LANGUAGE_NAMES = {
        "gu": "gujarati", "hi": "hindi", "pa": "punjabi", "mr": "marathi",
        "bn": "bengali", "ta": "tamil", "te": "telugu", "kn": "kannada",
        "ml": "malayalam", "en": "english",
    }

    def transcribe(self, audio_path, language=None):
        """
        Transcribe the audio file.
        language: short code (e.g. "gu", "hi", "ta") if known ahead of time
            (e.g. from an IVR "press 1 for Hindi" menu). If None, Whisper
            auto-detects the spoken language from the audio itself, which is
            what makes this usable nationally instead of assuming Gujarati.
        Returns: (text, detected_language_code)
        """
        print(f"Transcribing {audio_path}...")
        if language:
            whisper_lang = self.WHISPER_LANGUAGE_NAMES.get(language, language)
            result = self.pipe(audio_path, generate_kwargs={"language": whisper_lang, "task": "transcribe"})
            detected_code = language
        else:
            # No language hint: ask Whisper to auto-detect. We request the
            # language token back so we know which language was spoken -
            # needed downstream to answer in the same language via TTS.
            result = self.pipe(
                audio_path,
                generate_kwargs={"task": "transcribe", "return_language": True},
            )
            whisper_lang_name = None
            chunks = result.get("chunks")
            if chunks:
                whisper_lang_name = chunks[0].get("language")
            detected_code = self._map_whisper_lang_to_code(whisper_lang_name)
        return result["text"].strip(), detected_code

    def _map_whisper_lang_to_code(self, whisper_lang_name):
        if not whisper_lang_name:
            return "hi"  # national default fallback when detection is inconclusive
        reverse_map = {v: k for k, v in self.WHISPER_LANGUAGE_NAMES.items()}
        return reverse_map.get(whisper_lang_name.lower(), "hi")

if __name__ == "__main__":
    # Test script usage
    # Note: Use 'small' or 'tiny' for local quick testing, 'large-v3' for the actual demo
    test_model_id = "openai/whisper-small" 
    transcriber = ASRTranscriber(model_id=test_model_id)
    
    if len(sys.argv) > 1:
        text, lang = transcriber.transcribe(sys.argv[1])
        print("\n--- Transcription Result ---")
        print(f"Detected language: {lang}")
        print(text)
    else:
        print("Usage: python transcribe.py <audio_file_path>")
