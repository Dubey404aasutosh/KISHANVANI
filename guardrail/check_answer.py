import json
import re
from pathlib import Path

POP_TABLE_PATH = Path("guardrail/pop_table.json")

class Guardrail:
    def __init__(self):
        with open(POP_TABLE_PATH, 'r', encoding='utf-8') as f:
            self.pop_data = json.load(f)
            
        self.approved_chemicals = set([c.lower() for c in self.pop_data["approved_chemicals"]])
        self.banned_chemicals = set([c.lower() for c in self.pop_data["banned_chemicals"]])
        self.max_dosages = self.pop_data["approved_dosages_max"]
        
    def check_answer(self, answer_text, language="hi"):
        """
        Scans generated answer and verifies against pop_table.json.
        Works across all languages in the PoP table (Gujarati, Hindi, Punjabi,
        Bengali, Tamil, Telugu, Kannada, English), since chemical/unit names
        are matched as plain substrings regardless of script.
        Returns: (is_safe, final_answer)
        """
        text_lower = answer_text.lower()

        # 1. Check for explicitly banned chemicals
        for banned in self.banned_chemicals:
            if banned in text_lower:
                return False, self.get_fallback_message(language)

        # 2. Check dosages. E.g. find "50 મિલી", "100 gm", "30 மில்லி"
        # Regex to find numbers followed by a unit token (with optional space),
        # built dynamically from every unit key in pop_table.json so newly
        # added languages' unit words are picked up automatically.
        unit_alternation = "|".join(re.escape(u) for u in self.max_dosages.keys())
        dosage_pattern = rf'(\d+(?:\.\d+)?)\s*({unit_alternation})'
        matches = re.findall(dosage_pattern, text_lower)

        for amount_str, unit in matches:
            amount = float(amount_str)
            if unit in self.max_dosages:
                if amount > self.max_dosages[unit]:
                    print(f"Guardrail triggered: Dosage {amount} {unit} exceeds safe maximum {self.max_dosages[unit]} {unit}")
                    return False, self.get_fallback_message(language)

        # If it passed the basic heuristics, we consider it safe
        return True, answer_text

    # Fallback safety message per language, always paired with the
    # national Kisan Call Centre number so a farmer always has a next step
    # regardless of which language they called in.
    FALLBACK_MESSAGES = {
        "gu": "માફ કરશો, આ રસાયણ અથવા માત્રા સલામત નથી. કૃપા કરીને તમારા નજીકના કૃષિ વિજ્ઞાન કેન્દ્રનો સંપર્ક કરો અથવા કિસાન કોલ સેન્ટર 1800-180-1551 પર કૉલ કરો.",
        "hi": "क्षमा करें, यह रसायन या मात्रा सुरक्षित नहीं है। कृपया अपने नजदीकी कृषि विज्ञान केंद्र से संपर्क करें या किसान कॉल सेंटर 1800-180-1551 पर कॉल करें।",
        "pa": "ਮਾਫ਼ ਕਰਨਾ, ਇਹ ਰਸਾਇਣ ਜਾਂ ਮਾਤਰਾ ਸੁਰੱਖਿਅਤ ਨਹੀਂ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੇ ਨਜ਼ਦੀਕੀ ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ ਜਾਂ ਕਿਸਾਨ ਕਾਲ ਸੈਂਟਰ 1800-180-1551 'ਤੇ ਕਾਲ ਕਰੋ।",
        "bn": "দুঃখিত, এই রাসায়নিক বা মাত্রা নিরাপদ নয়। অনুগ্রহ করে আপনার নিকটতম কৃষি বিজ্ঞান কেন্দ্রের সাথে যোগাযোগ করুন অথবা কিষাণ কল সেন্টার 1800-180-1551 নম্বরে কল করুন।",
        "ta": "மன்னிக்கவும், இந்த வேதிப்பொருள் அல்லது அளவு பாதுகாப்பானது அல்ல. தயவுசெய்து உங்கள் அருகிலுள்ள வேளாண் அறிவியல் மையத்தை தொடர்பு கொள்ளவும் அல்லது கிசான் கால் சென்டர் 1800-180-1551 ஐ அழைக்கவும்.",
        "te": "క్షమించండి, ఈ రసాయనం లేదా మోతాదు సురక్షితం కాదు. దయచేసి మీ సమీప కృషి విజ్ఞాన కేంద్రాన్ని సంప్రదించండి లేదా కిసాన్ కాల్ సెంటర్ 1800-180-1551కి కాల్ చేయండి.",
        "kn": "ಕ್ಷಮಿಸಿ, ಈ ರಾಸಾಯನಿಕ ಅಥವಾ ಪ್ರಮಾಣ ಸುರಕ್ಷಿತವಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹತ್ತಿರದ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ ಅಥವಾ ಕಿಸಾನ್ ಕಾಲ್ ಸೆಂಟರ್ 1800-180-1551 ಗೆ ಕರೆ ಮಾಡಿ.",
        "en": "Sorry, this chemical or dosage is not safe. Please contact your nearest Krishi Vigyan Kendra or call the Kisan Call Centre at 1800-180-1551.",
    }

    def get_fallback_message(self, language="hi"):
        return self.FALLBACK_MESSAGES.get(language, self.FALLBACK_MESSAGES["hi"])

if __name__ == "__main__":
    guardrail = Guardrail()
    
    safe_text = "કપાસમાં સફેદ માખીના નિયંત્રણ માટે એસીટામીપ્રીડ ૨૦ મિલી ૧૦ લીટર પાણીમાં ભેળવી છંટકાવ કરો."
    # We use english numerals for regex simplicity in the prototype
    safe_text_eng_num = "કપાસમાં સફેદ માખીના નિયંત્રણ માટે એસીટામીપ્રીડ 20 મિલી 10 લીટર પાણીમાં ભેળવી છંટકાવ કરો."
    
    unsafe_text_1 = "તમારે મોનોક્રોટોફોસ 10 મિલી છાંટવું જોઈએ." # Contains banned chemical
    unsafe_text_2 = "ક્વિનાલફોસ 100 મિલી 10 લીટર પાણીમાં ભેળવી છંટકાવ કરો." # Dosage too high
    
    tests = [safe_text_eng_num, unsafe_text_1, unsafe_text_2]
    
    for t in tests:
        is_safe, final = guardrail.check_answer(t)
        print(f"Original: {t}\nSafe: {is_safe}\nFinal: {final}\n")
