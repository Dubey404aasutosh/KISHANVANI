from gtts import gTTS
import os
import time

# gTTS language codes for every language our pipeline supports end-to-end
# (ASR detection -> generation -> guardrail messages -> TTS). All of these
# are natively supported by Google TTS.
SUPPORTED_LANGUAGES = {"gu", "hi", "pa", "mr", "bn", "ta", "te", "kn", "ml", "en"}

def text_to_speech(text, lang='hi', output_path=None):
    """
    Converts text to speech using Google TTS (gTTS) for fast prototyping.
    lang: short code matching the language the farmer was answered in
        (defaults to Hindi as the broadest national fallback, rather than
        assuming Gujarati).
    """
    if lang not in SUPPORTED_LANGUAGES:
        print(f"Warning: language '{lang}' not in SUPPORTED_LANGUAGES, falling back to 'hi'.")
        lang = 'hi'

    if not output_path:
        output_path = f"temp_tts_{int(time.time())}.mp3"

    print(f"Generating TTS ({lang}) for: {text[:50]}...")
    tts = gTTS(text=text, lang=lang)
    tts.save(output_path)
    return output_path

if __name__ == "__main__":
    import sys
    test_text = "નમસ્કાર કિસાન ભાઈ, આ કિસાન કોલ સેન્ટર છે."
    if len(sys.argv) > 1:
        test_text = sys.argv[1]
    
    out = text_to_speech(test_text)
    print(f"Saved to {out}")
