import os
import hashlib
import time
from asr.transcribe import ASRTranscriber
from retrieval.retrieve import HybridRetriever
from generation.generate import LLMGenerator
from guardrail.check_answer import Guardrail
from tts.speak import text_to_speech

class KisanvaniOrchestrator:
    def __init__(self):
        print("Initializing KISANVANI Pipeline...")
        # Start all components
        self.transcriber = ASRTranscriber(model_id="openai/whisper-small")
        self.retriever = HybridRetriever()
        self.generator = LLMGenerator()
        self.guardrail = Guardrail()
        print("Initialization Complete.")
        
    # "Couldn't hear you" message per language, used when ASR returns empty text.
    NO_SPEECH_MESSAGES = {
        "gu": "માફ કરશો, તમારો અવાજ સંભળાયો નથી.",
        "hi": "क्षमा करें, आपकी आवाज़ सुनाई नहीं दी।",
        "pa": "ਮਾਫ਼ ਕਰਨਾ, ਤੁਹਾਡੀ ਆਵਾਜ਼ ਸੁਣਾਈ ਨਹੀਂ ਦਿੱਤੀ।",
        "bn": "দুঃখিত, আপনার কণ্ঠস্বর শোনা যায়নি।",
        "ta": "மன்னிக்கவும், உங்கள் குரல் கேட்கவில்லை.",
        "te": "క్షమించండి, మీ స్వరం వినిపించలేదు.",
        "kn": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಧ್ವನಿ ಕೇಳಿಸಲಿಲ್ಲ.",
        "en": "Sorry, we could not hear your voice.",
    }

    def handle_call(self, audio_file_path, caller_id="unknown_caller", language=None, crop=None, state=None):
        """
        End-to-end pipeline for KISANVANI, national and multi-crop:
        language: optional short code (e.g. "hi", "ta") if known from an IVR
            menu; otherwise auto-detected from the audio by Whisper.
        crop/state: optional hints (e.g. from caller registration or an IVR
            menu) to narrow retrieval to the farmer's actual crop/region.
        """
        # Milestone 8: Privacy - Hash Caller ID
        hashed_caller_id = hashlib.sha256(caller_id.encode()).hexdigest()
        print(f"\n[Call Started] Caller: {hashed_caller_id[:8]}...")

        # 1. ASR (auto-detects language nationally unless one is already known)
        print("[Step 1] Transcribing Audio...")
        try:
            query_text, detected_language = self.transcriber.transcribe(audio_file_path, language=language)
            print(f"User Query ({detected_language}): {query_text}")
        except Exception as e:
            print(f"ASR Error: {e}")
            query_text, detected_language = "", (language or "hi")

        # Milestone 8: Privacy - Delete Audio File immediately after transcription
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            print(f"Deleted raw audio file for privacy.")

        if not query_text:
            fallback = self.NO_SPEECH_MESSAGES.get(detected_language, self.NO_SPEECH_MESSAGES["hi"])
            return fallback, text_to_speech(fallback, lang=detected_language), detected_language

        # 2. Retrieval (national corpus, optionally narrowed by crop/state)
        print("[Step 2] Retrieving Context...")
        passages = self.retriever.retrieve(query_text, k=3, crop=crop, state=state)

        # 3. Generation (answers in the same language the farmer used)
        print("[Step 3] Generating Response...")
        raw_response = self.generator.generate_response(query_text, passages, language=detected_language)

        # 4. Guardrail
        print("[Step 4] Checking Safety Guardrails...")
        is_safe, final_response = self.guardrail.check_answer(raw_response, language=detected_language)
        if not is_safe:
            print("Guardrail Check Failed. Using fallback.")

        # 5. TTS (spoken back in the farmer's own language)
        print("[Step 5] Synthesizing Speech...")
        audio_out = text_to_speech(final_response, lang=detected_language)

        print("[Call Ended Successfully]")
        return final_response, audio_out, detected_language

# Global instance so we don't reload models for every call in the webhook
# In a real scalable app, we'd use a pool of workers or GPU servers.
try:
    orchestrator_instance = KisanvaniOrchestrator()
except Exception as e:
    print(f"Failed to load orchestrator completely. (e.g. if index is missing): {e}")
    orchestrator_instance = None

if __name__ == "__main__":
    if orchestrator_instance:
        print("Orchestrator ready!")
