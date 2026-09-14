import requests
from generation.prompts import build_prompt

class LLMGenerator:
    # Generic (language-neutral-ish, Hindi as broadest fallback) error
    # messages when the LLM can't be reached at all.
    CONNECTION_ERROR_MESSAGES = {
        "hi": "क्षमा करें, सिस्टम से कनेक्ट नहीं हो सका।",
        "gu": "માફ કરશો, સિસ્ટમ સાથે કનેક્ટ કરી શકાયું નથી.",
        "en": "Sorry, could not connect to the system.",
    }
    GENERIC_ERROR_MESSAGES = {
        "hi": "क्षमा करें, अभी मैं आपका जवाब नहीं दे पा रहा हूं। कृपया अपने नजदीकी कृषि विज्ञान केंद्र से संपर्क करें।",
        "gu": "માફ કરશો, અત્યારે હું તમારો જવાબ આપી શકતો નથી. કૃપા કરીને તમારા નજીકના કૃષિ વિજ્ઞાન કેન્દ્રનો સંપર્ક કરો.",
        "en": "Sorry, I'm unable to answer right now. Please contact your nearest Krishi Vigyan Kendra.",
    }

    def __init__(self, model_name="llama3.1", endpoint="http://localhost:11434/api/generate", timeout=180):
        """
        Uses local Ollama by default. Make sure Ollama is running and the model is pulled.
        e.g., `ollama serve` + `ollama pull llama3.1`
        For a production prototype, we might switch to a hosted Groq/Together endpoint for lower latency.
        timeout: generous default (180s) because a cold Ollama model load on
        CPU-only hardware can itself take 30-60s before the first token -
        a short timeout here causes spurious failures on the very first
        call of a demo/session, not genuine unavailability.
        """
        self.model_name = model_name
        self.endpoint = endpoint
        self.timeout = timeout

    def generate_response(self, query, passages, language="hi"):
        system_prompt, user_prompt = build_prompt(query, passages, language=language)

        payload = {
            "model": self.model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False
        }

        print(f"Generating response using {self.model_name} on {self.endpoint}...")
        try:
            response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to Ollama. Make sure Ollama is running locally.")
            return self.CONNECTION_ERROR_MESSAGES.get(language, self.CONNECTION_ERROR_MESSAGES["hi"])
        except Exception as e:
            print(f"LLM Generation Error: {e}")
            return self.GENERIC_ERROR_MESSAGES.get(language, self.GENERIC_ERROR_MESSAGES["hi"])

if __name__ == "__main__":
    generator = LLMGenerator()
    test_query = "કપાસમાં સફેદ માખી માટે શું કરવું?"
    test_passages = [
        {"answer": "સફેદ માખીના નિયંત્રણ માટે, એસીટામીપ્રીડ 20 SP 4 ગ્રામ 10 લીટર પાણીમાં ભેળવીને છંટકાવ કરવો."}
    ]
    
    print("--- Test Generation ---")
    response_text = generator.generate_response(test_query, test_passages)
    print(response_text)
