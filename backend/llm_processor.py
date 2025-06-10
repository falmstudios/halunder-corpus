import json
import os
import re
import time
from typing import List, Dict
from openai import OpenAI

class LLMProcessor:
    def __init__(self):
        """Production LLM Processor mit OpenAI API"""
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key or api_key.startswith("sk-your-key"):
            print("⚠️ WARNUNG: Kein gültiger OpenAI API Key!")
            print("   System läuft im Fallback-Modus ohne LLM-Features")
            self.client = None
            self.model = "fallback-mode"
        else:
            try:
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-4o-mini"
                print(f"✅ OpenAI Client initialisiert mit {self.model}")
                
                # Schneller API-Test
                test_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=5,
                    timeout=10
                )
                print("✅ OpenAI API Test erfolgreich")
                
            except Exception as e:
                print(f"❌ OpenAI Initialisierung fehlgeschlagen: {e}")
                print("   System läuft im Fallback-Modus")
                self.client = None
                self.model = "fallback-mode"
    
    def _call_llm(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """Optimierter LLM-Aufruf mit kürzeren Timeouts"""
        if not self.client:
            raise Exception("OpenAI nicht verfügbar - läuft im Fallback-Modus")
        
        try:
            print(f"🤖 LLM-Anfrage startet... ({len(prompt)} Zeichen → max {max_tokens} tokens)")
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30
            )
            
            duration = time.time() - start_time
            result = response.choices[0].message.content
            print(f"✅ LLM-Antwort in {duration:.1f}s ({len(result)} Zeichen)")
            return result
            
        except Exception as e:
            duration = time.time() - start_time if 'start_time' in locals() else 0
            print(f"❌ LLM Fehler nach {duration:.1f}s: {e}")
            raise Exception(f"LLM-Aufruf fehlgeschlagen nach {duration:.1f}s: {e}")
    
    def clean_ocr_text(self, text: str) -> str:
        """OCR-Bereinigung mit LLM oder Fallback"""
        if not text or len(text.strip()) < 10:
            return text
        
        # Mit LLM versuchen
        if self.client:
            try:
                prompt = f"""Korrigiere OCR-Fehler in diesem Text. Behalte Halunder-Dialekt bei.

Text: {text}

Antworte NUR mit dem korrigierten Text:"""
                
                result = self._call_llm(prompt, temperature=0.1, max_tokens=len(text) + 100)
                print(f"✅ OCR mit LLM bereinigt")
                return result.strip()
                
            except Exception as e:
                print(f"⚠️ LLM-OCR fehlgeschlagen, verwende Fallback: {e}")
        
        # Fallback-Bereinigung
        print("🔧 OCR-Fallback-Bereinigung")
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r',,', '"', text)
        text = re.sub(r"''", '"', text)
        return text.strip()
    
    def identify_text_type(self, text: str) -> Dict:
        """Schnelle Texttyp-Identifikation"""
        
        # Mit LLM versuchen (kürzerer Prompt)
        if self.client:
            try:
                prompt = f"""Analysiere schnell: Ist das Halunder oder Deutsch?
Halunder-Kennzeichen: deät, dja, uun, fan, med, wat, Djül, küm

Text: {text[:300]}

JSON-Antwort:
{{"primary_language": "halunder", "confidence": 0.9}}"""
                
                result = self._call_llm(prompt, temperature=0.1, max_tokens=50)
                parsed = json.loads(result)
                print(f"✅ Texttyp mit LLM: {parsed['primary_language']}")
                return {
                    "primary_language": parsed.get("primary_language", "halunder"),
                    "has_parallel_text": False,
                    "has_translation_aids": False,
                    "confidence": parsed.get("confidence", 0.8)
                }
                    
            except Exception as e:
                print(f"⚠️ LLM-Texttyp fehlgeschlagen: {e}")
        
        # Fallback-Identifikation
        print("🔧 Texttyp-Fallback")
        halunder_words = ['deät', 'dja', 'uun', 'fan', 'med', 'wat', 'soo', 'oaber', 'Djül', 'küm', 'dear', 'hid']
        text_lower = text.lower()
        halunder_count = sum(1 for word in halunder_words if word in text_lower)
        
        return {
            "primary_language": "halunder" if halunder_count > 0 else "german",
            "has_parallel_text": False,
            "has_translation_aids": False,
            "confidence": 0.9 if halunder_count > 2 else 0.7
        }
    
    def extract_sentences(self, text: str, language: str) -> List[Dict]:
        """Satzextraktion mit LLM oder Fallback"""
        if not text:
            return []
        
        # Mit LLM versuchen
        if self.client:
            try:
                prompt = f"""Extrahiere Sätze aus diesem {language}-Text.

Text: {text}

JSON-Array:
[
    {{"position": 0, "content": "Erster Satz."}},
    {{"position": 1, "content": "Zweiter Satz."}}
]"""
                
                result = self._call_llm(prompt, temperature=0.3, max_tokens=800)
                sentences = json.loads(result)
                print(f"✅ {len(sentences)} Sätze mit LLM extrahiert")
                return sentences
                
            except Exception as e:
                print(f"⚠️ LLM-Extraktion fehlgeschlagen: {e}")
        
        # Fallback-Extraktion
        print("🔧 Satzextraktion-Fallback")
        sentences = []
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        
        for i, part in enumerate(parts):
            part = part.strip()
            if part and len(part) > 2:
                sentences.append({
                    "position": i,
                    "content": part
                })
        
        print(f"📝 {len(sentences)} Sätze mit Fallback extrahiert")
        return sentences
    
    def match_sentences_parallel(self, halunder_sents: List[str], german_sents: List[str]) -> List[Dict]:
        """Sentence-Matching mit LLM oder Fallback"""
        
        # Mit LLM versuchen
        if self.client:
            try:
                prompt = f"""Matche Halunder-Sätze mit deutschen Übersetzungen.

Halunder: {json.dumps(halunder_sents[:5], ensure_ascii=False)}
Deutsch: {json.dumps(german_sents[:5], ensure_ascii=False)}

JSON-Array:
[
    {{
        "halunder_index": 0,
        "german_index": 0,
        "confidence": 0.95,
        "reasoning": "Begründung"
    }}
]"""
                
                result = self._call_llm(prompt, temperature=0.3, max_tokens=600)
                matches = json.loads(result)
                print(f"✅ {len(matches)} Paare mit LLM gematcht")
                return matches
                
            except Exception as e:
                print(f"⚠️ LLM-Matching fehlgeschlagen: {e}")
        
        # Fallback-Matching (1:1)
        print("🔧 Sentence-Matching-Fallback")
        matches = []
        for i in range(min(len(halunder_sents), len(german_sents))):
            matches.append({
                "halunder_index": i,
                "german_index": i,
                "confidence": 0.8,
                "reasoning": f"Automatisches 1:1 Matching Position {i+1}"
            })
        
        print(f"📝 {len(matches)} Paare mit Fallback gematcht")
        return matches
    
    def extract_translation_aids(self, text: str) -> List[Dict]:
        """Übersetzungshilfen-Fallback (für Geschwindigkeit)"""
        if not text:
            return []
        
        print("🔧 Übersetzungshilfen-Fallback")
        aids = []
        for line in text.split('\n'):
            line = line.strip()
            if '-' in line or ':' in line:
                parts = re.split(r'\s*[-:–]\s*', line, 1)
                if len(parts) == 2:
                    aids.append({
                        "halunder_term": parts[0].strip(),
                        "german_translation": parts[1].strip(),
                        "notes": "Automatisch extrahiert"
                    })
        
        print(f"📖 {len(aids)} Übersetzungshilfen mit Fallback extrahiert")
        return aids
    
    def extract_idioms_from_text(self, text: str, explanations: str = "") -> List[Dict]:
        """Idiom-Fallback (für Geschwindigkeit)"""
        print("🔧 Idiom-Fallback (leer für Performance)")
        return []