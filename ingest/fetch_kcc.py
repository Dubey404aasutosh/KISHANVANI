"""
KCC (Kisan Call Centre) national dataset ingestion.

Primary source: data.gov.in's KCC query dataset via their public API.
    Resource: "Kisan Call Centre - Farmer Query Data"
    API docs: https://api.data.gov.in/  (resource id set in KCC_RESOURCE_ID)

To use the real API:
    1. Register a free account at https://data.gov.in/user/register
    2. Generate an API key at https://data.gov.in/user (My Account -> API keys)
    3. Set it as an environment variable before running this script:
           Windows (PowerShell):  $env:DATA_GOV_IN_API_KEY = "your-key-here"
           bash:                  export DATA_GOV_IN_API_KEY="your-key-here"
    4. Run: python ingest/fetch_kcc.py

If no API key is set (or the request fails for any reason — rate limit, network,
resource id changed upstream, etc.) this script automatically falls back to a
hand-curated, KCC-realistic seed dataset covering multiple states, crops and
languages, so the rest of the pipeline (retrieval/generation/guardrail) always
has something to run against. The fallback is clearly labeled in the output
records via "source": "seed" vs "source": "data.gov.in".
"""

import json
import os
import time
from pathlib import Path

import requests

# --- data.gov.in API config -------------------------------------------------
DATA_GOV_IN_BASE = "https://api.data.gov.in/resource"
# Resource ID for the KCC farmer-query dataset on data.gov.in.
# NOTE: data.gov.in periodically republishes datasets under new resource ids;
# if this id 404s, search https://data.gov.in/catalogs?title=kisan%20call%20centre
# for the current one and update this constant (or pass --resource-id).
KCC_RESOURCE_ID = os.environ.get("KCC_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
API_KEY = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
PAGE_LIMIT = 500

RAW_DATA_PATH = Path("data/raw/kcc_data.csv")
PROCESSED_DATA_PATH = Path("data/processed/kcc_national.json")

# National scope: top ~15 crops by KCC call volume, spanning multiple
# agro-climatic zones so retrieval/generation isn't Gujarat/cotton-only.
TARGET_CROPS = [
    "cotton", "rice", "wheat", "sugarcane", "maize", "soybean", "groundnut",
    "chilli", "tomato", "onion", "potato", "banana", "mustard", "gram", "tea",
]
TARGET_STATES = [
    "gujarat", "maharashtra", "punjab", "uttar pradesh", "madhya pradesh",
    "karnataka", "tamil nadu", "andhra pradesh", "west bengal", "bihar",
    "rajasthan", "haryana", "assam",
]

# ---------------------------------------------------------------------------
# Hand-curated national seed set (used when the live API is unavailable).
# Deliberately spans multiple states/crops/languages/intents rather than a
# single crop+district, so the rest of the pipeline can be demoed nationally
# even before a data.gov.in key is wired in.
# ---------------------------------------------------------------------------
SEED_DATA = [
    {
        "query": "મારો કપાસ નો પાક ૬૦ દિવસ નો છે અને તેમાં ગુલાબી ઈયળ નો ઉપદ્રવ જોવા મળે છે. શું કરવું?",
        "answer": "કપાસમાં ગુલાબી ઈયળના નિયંત્રણ માટે, 5 ટકા લીંબોળીનો અર્ક અથવા ક્વિનાલફોસ 20 મિલી 10 લીટર પાણીમાં ભેળવી છંટકાવ કરો. જો ઉપદ્રવ વધુ હોય તો પ્રોફેનોફોસ 50 EC 20 મિલી પ્રતિ 10 લીટર પાણીમાં છાંટો.",
        "crop": "cotton", "state": "gujarat", "district": "surat", "language": "gu",
        "month": "august", "intent": "pest/disease",
    },
    {
        "query": "કપાસમાં સફેદ માખીનો ત્રાસ વધી ગયો છે, પાંદડા પીળા પડી રહ્યા છે. કોઈ દવા બતાવો.",
        "answer": "સફેદ માખીના નિયંત્રણ માટે, એસીટામીપ્રીડ 20 SP 4 ગ્રામ અથવા ડાયફેન્થિયુરોન 50 WP 10 ગ્રામ 10 લીટર પાણીમાં ભેળવીને છંટકાવ કરવો. ખેતરમાં પીળા ચીકણા જાળ (Yellow sticky traps) પણ લગાવો.",
        "crop": "cotton", "state": "gujarat", "district": "surat", "language": "gu",
        "month": "september", "intent": "pest/disease",
    },
    {
        "query": "कपास के पत्तों पर छोटे हरे कीड़े (Jassids) लग गए हैं, पत्ते मुड़ रहे हैं।",
        "answer": "हरे मच्छर (तड़तड़िया) के नियंत्रण के लिए, इमिडाक्लोप्रिड 17.8 SL 5 मिली या थियामेथोक्सम 25 WG 4 ग्राम 10 लीटर पानी में मिलाकर छिड़काव करें।",
        "crop": "cotton", "state": "maharashtra", "district": "nagpur", "language": "hi",
        "month": "july", "intent": "pest/disease",
    },
    {
        "query": "ਝੋਨੇ ਦੀ ਫਸਲ ਵਿੱਚ ਭੂਰਾ ਟਿੱਡਾ (Brown Plant Hopper) ਦਿਖਾਈ ਦੇ ਰਿਹਾ ਹੈ, ਕੀ ਕਰੀਏ?",
        "answer": "ਭੂਰੇ ਟਿੱਡੇ ਦੀ ਰੋਕਥਾਮ ਲਈ ਇਮੀਡਾਕਲੋਪ੍ਰਿਡ 17.8 SL 100 ਮਿਲੀਲੀਟਰ ਪ੍ਰਤੀ ਏਕੜ ਦੀ ਵਰਤੋਂ ਕਰੋ ਅਤੇ ਖੇਤ ਵਿੱਚ ਪਾਣੀ ਦਾ ਪੱਧਰ ਘਟਾਓ।",
        "crop": "rice", "state": "punjab", "district": "ludhiana", "language": "pa",
        "month": "september", "intent": "pest/disease",
    },
    {
        "query": "धान की फसल में पत्ती लपेटक कीट (Leaf Folder) का प्रकोप है, उपाय बताएं।",
        "answer": "पत्ती लपेटक कीट के नियंत्रण के लिए क्लोरएंट्रानिलिप्रोल 18.5 SC 3 मिली प्रति 10 लीटर पानी में मिलाकर छिड़काव करें। खेत में नाइट्रोजन उर्वरक की अधिक मात्रा से बचें।",
        "crop": "rice", "state": "uttar pradesh", "district": "gorakhpur", "language": "hi",
        "month": "august", "intent": "pest/disease",
    },
    {
        "query": "गेहूं की फसल में पीला रतुआ (Yellow Rust) रोग लग गया है, पत्तियों पर पीले धब्बे हैं।",
        "answer": "पीले रतुआ के नियंत्रण के लिए प्रोपिकोनाजोल 25 EC 1 मिली प्रति लीटर पानी में मिलाकर छिड़काव करें। संक्रमित पौधों को तुरंत खेत से हटा दें।",
        "crop": "wheat", "state": "punjab", "district": "amritsar", "language": "hi",
        "month": "february", "intent": "disease",
    },
    {
        "query": "गन्ने की फसल में शीर्ष बेधक (Top Borer) कीट का हमला हो गया है।",
        "answer": "शीर्ष बेधक के नियंत्रण के लिए क्लोरएंट्रानिलिप्रोल 18.5 SC 150 मिली प्रति एकड़ ड्रिप सिंचाई से दें या क्लोरपायरीफॉस 20 EC का छिड़काव करें।",
        "crop": "sugarcane", "state": "uttar pradesh", "district": "meerut", "language": "hi",
        "month": "june", "intent": "pest/disease",
    },
    {
        "query": "मक्का की फसल में फॉल आर्मीवर्म (Fall Armyworm) कीट दिख रहा है, पत्तों में छेद हैं।",
        "answer": "फॉल आर्मीवर्म के नियंत्रण के लिए इमामेक्टिन बेंजोएट 5 SG 4 ग्राम प्रति 10 लीटर पानी में मिलाकर शाम के समय छिड़काव करें।",
        "crop": "maize", "state": "madhya pradesh", "district": "indore", "language": "hi",
        "month": "july", "intent": "pest/disease",
    },
    {
        "query": "ಶೇಂಗಾ ಬೆಳೆಯಲ್ಲಿ ಎಲೆ ಚುಕ್ಕೆ ರೋಗ (Leaf Spot) ಕಂಡುಬಂದಿದೆ, ಏನು ಮಾಡಬೇಕು?",
        "answer": "ಎಲೆ ಚುಕ್ಕೆ ರೋಗ ನಿಯಂತ್ರಣಕ್ಕೆ ಮ್ಯಾಂಕೋಜೆಬ್ 75 WP 25 ಗ್ರಾಂ ಅನ್ನು 10 ಲೀಟರ್ ನೀರಿನಲ್ಲಿ ಬೆರೆಸಿ ಸಿಂಪಡಿಸಿ.",
        "crop": "groundnut", "state": "karnataka", "district": "bellary", "language": "kn",
        "month": "october", "intent": "disease",
    },
    {
        "query": "மிளகாய் பயிரில் திரிப்ஸ் (Thrips) பூச்சி தாக்குதல் அதிகமாக உள்ளது.",
        "answer": "திரிப்ஸ் கட்டுப்பாட்டிற்கு அசிடமிபிரிட் 20 SP 4 கிராம் அல்லது ஸ்பினோசாட் 45 SC 3 மில்லி 10 லிட்டர் தண்ணீரில் கலந்து தெளிக்கவும்.",
        "crop": "chilli", "state": "tamil nadu", "district": "madurai", "language": "ta",
        "month": "november", "intent": "pest/disease",
    },
    {
        "query": "టమాటా పంటలో కాయ తొలుచు పురుగు (Fruit Borer) ఆశించింది, ఏమి చేయాలి?",
        "answer": "కాయ తొలుచు పురుగు నివారణకు స్పైనోశాడ్ 45 SC 3 మి.లీ లేదా క్లోరాంట్రానిలిప్రోల్ 18.5 SC 3 మి.లీ 10 లీటర్ల నీటిలో కలిపి పిచికారీ చేయండి.",
        "crop": "tomato", "state": "andhra pradesh", "district": "kurnool", "language": "te",
        "month": "december", "intent": "pest/disease",
    },
    {
        "query": "পিঁয়াজ চাষে থ্রিপস পোকার আক্রমণ দেখা যাচ্ছে, পাতা কুঁকড়ে যাচ্ছে।",
        "answer": "থ্রিপস দমনের জন্য ফিপ্রোনিল ৫ এসসি ৩০ মিলি অথবা স্পিনোস্যাড ৪৫ এসসি ৩ মিলি ১০ লিটার পানিতে মিশিয়ে স্প্রে করুন।",
        "crop": "onion", "state": "west bengal", "district": "nadia", "language": "bn",
        "month": "january", "intent": "pest/disease",
    },
    {
        "query": "आलू की फसल में पछेती झुलसा रोग (Late Blight) लग गया है, पत्तियां काली पड़ रही हैं।",
        "answer": "पछेती झुलसा रोग के नियंत्रण के लिए मेटालैक्सिल + मैंकोजेब (रिडोमिल गोल्ड) 25 ग्राम प्रति 10 लीटर पानी में मिलाकर छिड़काव करें।",
        "crop": "potato", "state": "bihar", "district": "patna", "language": "hi",
        "month": "december", "intent": "disease",
    },
    {
        "query": "केले की फसल में सिगाटोका पत्ती धब्बा रोग (Sigatoka Leaf Spot) दिख रहा है।",
        "answer": "सिगाटोका रोग नियंत्रण के लिए प्रोपिकोनाजोल 25 EC 10 मिली प्रति 10 लीटर पानी में मिलाकर 15 दिन के अंतराल पर छिड़काव करें।",
        "crop": "banana", "state": "tamil nadu", "district": "theni", "language": "hi",
        "month": "march", "intent": "disease",
    },
    {
        "query": "সরিষা ফসলে জাব পোকার (Aphid) আক্রমণ হয়েছে, ডগা কুঁকড়ে যাচ্ছে।",
        "answer": "জাব পোকা দমনের জন্য ইমিডাক্লোপ্রিড ১৭.৮ এসএল ৫ মিলি ১০ লিটার পানিতে মিশিয়ে স্প্রে করুন।",
        "crop": "mustard", "state": "west bengal", "district": "murshidabad", "language": "bn",
        "month": "january", "intent": "pest/disease",
    },
    {
        "query": "चने की फसल में इल्ली (Pod Borer) का प्रकोप है, फलियां खराब हो रही हैं।",
        "answer": "फली छेदक इल्ली के नियंत्रण के लिए इमामेक्टिन बेंजोएट 5 SG 4 ग्राम या क्लोरएंट्रानिलिप्रोल 18.5 SC 3 मिली प्रति 10 लीटर पानी में मिलाकर छिड़काव करें।",
        "crop": "gram", "state": "madhya pradesh", "district": "bhopal", "language": "hi",
        "month": "december", "intent": "pest/disease",
    },
    {
        "query": "চা বাগানে লাল মাকড় (Red Spider Mite) দেখা যাচ্ছে, পাতা লালচে হয়ে যাচ্ছে।",
        "answer": "লাল মাকড় দমনের জন্য প্রোপারগাইট ৫৭ ইসি ১০ মিলি ১০ লিটার পানিতে মিশিয়ে স্প্রে করুন।",
        "crop": "tea", "state": "assam", "district": "jorhat", "language": "bn",
        "month": "april", "intent": "pest/disease",
    },
    {
        "query": "कपास में मिलीबग (Mealybug) का प्रकोप दिख रहा है, पौधे सूखने लगे हैं।",
        "answer": "मिलीबग के प्रभावी नियंत्रण के लिए प्रोफेनोफॉस 50 EC 20 मिली या क्लोरपायरीफॉस 20 EC 25 मिली प्रति 10 लीटर पानी में डिटर्जेंट पाउडर मिलाकर छिड़काव करें।",
        "crop": "cotton", "state": "gujarat", "district": "surat", "language": "hi",
        "month": "october", "intent": "pest/disease",
    },
    {
        "query": "सोयाबीन की फसल में तना मक्खी (Stem Fly) का असर हो रहा है।",
        "answer": "तना मक्खी नियंत्रण के लिए थायोमेथोक्साम 12.6% + लैम्ब्डा साइहेलोथ्रिन 9.5% ZC 2.5 मिली प्रति 10 लीटर पानी में मिलाकर छिड़काव करें।",
        "crop": "soybean", "state": "madhya pradesh", "district": "indore", "language": "hi",
        "month": "july", "intent": "pest/disease",
    },
    {
        "query": "कपासमां सफेद माखी माटे मोनोक्रोटोफोस वापरी शकाय?",
        "answer": "ना, મોનોક્રોટોફોસ પ્રતિબંધિત જંતુનાશક છે અને તેનો ઉપયોગ કાયદેસર રીતે માન્ય નથી. કૃપા કરીને તમારા નજીકના કૃષિ વિજ્ઞાન કેન્દ્રનો સંપર્ક કરો.",
        "crop": "cotton", "state": "gujarat", "district": "surat", "language": "gu",
        "month": "september", "intent": "pest/disease",
    },
]


def fetch_from_data_gov_in():
    """
    Pull real KCC records from data.gov.in's public API, paginating across
    all target crops. Returns a list of normalized record dicts, or raises
    if the API can't be reached / key is missing.
    """
    if not API_KEY:
        raise RuntimeError("DATA_GOV_IN_API_KEY not set")

    all_records = []
    url = f"{DATA_GOV_IN_BASE}/{KCC_RESOURCE_ID}"

    for crop in TARGET_CROPS:
        offset = 0
        while True:
            params = {
                "api-key": API_KEY,
                "format": "json",
                "limit": PAGE_LIMIT,
                "offset": offset,
                "filters[crop]": crop,
            }
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("records", [])
            if not rows:
                break

            for row in rows:
                query = (row.get("querytext") or row.get("query") or "").strip()
                answer = (row.get("kccans") or row.get("answer") or "").strip()
                if not query or not answer:
                    continue
                all_records.append({
                    "query": query,
                    "answer": answer,
                    "crop": (row.get("crop") or crop).strip().lower(),
                    "state": (row.get("statename") or row.get("state") or "").strip().lower(),
                    "district": (row.get("districtname") or row.get("district") or "").strip().lower(),
                    "language": (row.get("language") or "").strip().lower() or "hi",
                    "month": (row.get("month") or "").strip().lower(),
                    "intent": (row.get("querytype") or row.get("intent") or "general").strip().lower(),
                    "source": "data.gov.in",
                })

            offset += PAGE_LIMIT
            if len(rows) < PAGE_LIMIT:
                break
            time.sleep(0.2)  # be polite to the free-tier API

    return all_records


def main():
    os.makedirs(PROCESSED_DATA_PATH.parent, exist_ok=True)
    records = []

    try:
        print(f"Attempting to fetch live KCC data from data.gov.in "
              f"(resource: {KCC_RESOURCE_ID}) for crops: {TARGET_CROPS}...")
        records = fetch_from_data_gov_in()
        print(f"Fetched {len(records)} real KCC records from data.gov.in.")
    except Exception as e:
        print(f"Could not fetch live data.gov.in KCC data ({e}).")
        print("Falling back to curated national seed dataset "
              "(multi-state, multi-crop, multi-language) so the pipeline "
              "remains runnable. Set DATA_GOV_IN_API_KEY to use real data.")
        records = [{**r, "source": "seed"} for r in SEED_DATA]

    print(f"Total processed records: {len(records)} "
          f"across {len(set(r['crop'] for r in records))} crops, "
          f"{len(set(r.get('state', '') for r in records))} states, "
          f"{len(set(r.get('language', '') for r in records))} languages.")

    with open(PROCESSED_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=4)

    print(f"Saved processed data to {PROCESSED_DATA_PATH}")


if __name__ == "__main__":
    main()
