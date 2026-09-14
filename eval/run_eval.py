import json
import os
import sys

# Ensure parent dirs are reachable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from asr.transcribe import ASRTranscriber
from retrieval.retrieve import HybridRetriever

def calculate_wer(reference, hypothesis):
    """
    Very basic Word Error Rate calculation (simplified for prototype)
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    
    matches = sum([1 for w in hyp_words if w in ref_words])
    return max(0.0, 1.0 - (matches / max(len(ref_words), 1)))

def run_eval():
    print("Loading Eval Dataset...")
    try:
        with open("eval/gold_set.json", 'r', encoding='utf-8') as f:
            gold_set = json.load(f)
    except Exception:
        print("Gold set not found.")
        return
        
    print("Initializing components...")
    transcriber = ASRTranscriber(model_id="openai/whisper-small")
    retriever = HybridRetriever()
    
    total_wer = 0
    recall_at_3 = 0
    
    for item in gold_set:
        print(f"\nEvaluating: {item['true_transcript'][:40]}...")
        
        # 1. ASR WER (language auto-detected, same as production path)
        if os.path.exists(item['audio_path']):
            hyp_transcript, detected_language = transcriber.transcribe(item['audio_path'])
            print(f"  Detected language: {detected_language} (expected: {item.get('language', 'n/a')})")
        else:
            print(f"  [Warning] Audio {item['audio_path']} not found. Skipping ASR (simulating perfect ASR).")
            hyp_transcript = item['true_transcript']

        wer = calculate_wer(item['true_transcript'], hyp_transcript)
        total_wer += wer
        print(f"  WER: {wer:.2f}")

        # 2. Recall@3 (optionally narrowed by crop/state, same as production path)
        results = retriever.retrieve(hyp_transcript, k=3, crop=item.get('crop'), state=item.get('state'))
        found = False
        for res in results:
            ans = res.get('answer', '').lower()
            if any(kw.lower() in ans for kw in item['relevant_passage_keywords']):
                found = True
                break
        
        if found:
            recall_at_3 += 1
            print("  Recall@3: HIT")
        else:
            print("  Recall@3: MISS")
            
    avg_wer = total_wer / len(gold_set)
    acc_recall = recall_at_3 / len(gold_set)
    
    print("\n--- Final Eval Results ---")
    print(f"Average WER: {avg_wer:.2f}")
    print(f"Retrieval Recall@3: {acc_recall*100:.1f}%")
    print("\nManual scoring template for LLM generated answers is ready. Run orchestrator manually to score TTS and LLM.")

if __name__ == "__main__":
    run_eval()
