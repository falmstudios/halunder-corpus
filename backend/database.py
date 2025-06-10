import os
from supabase import create_client, Client
from typing import List, Dict, Optional
import json
import csv
from datetime import datetime

# Replace these with your Supabase credentials
SUPABASE_URL = "https://dhdshkzloxdmkvjpqwbt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRoZHNoa3psb3hkbWt2anBxd2J0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkyMjI5OTUsImV4cCI6MjA2NDc5ODk5NX0.88-c7RiZTkx9L5pFGapYK2E4FY6nWHHtoGb7PNzr7TI"

class Database:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    def get_users(self) -> List[str]:
        """Get list of users for dropdown"""
        response = self.client.table('users').select('name').execute()
        return [user['name'] for user in response.data]
    
    def add_text(self, data: dict) -> dict:
        """Add new text to database"""
        response = self.client.table('texts').insert(data).execute()
        return response.data[0]
    
    def find_matching_texts(self, language: str) -> List[dict]:
        """Find texts that might match a translation"""
        response = self.client.table('texts')\
            .select('*')\
            .neq('language', language)\
            .execute()
        return response.data
    
    def update_translation_link(self, text_id: str, translation_of: str, confidence: float):
        """Link a text as translation of another"""
        self.client.table('texts').update({
            'translation_of': translation_of,
            'match_confidence': confidence
        }).eq('id', text_id).execute()
    
    def add_sentences(self, sentences: List[dict]):
        """Add extracted sentences mit korrektem Schema"""
        if not sentences:
            print("⚠️ Keine Sätze zum Speichern")
            return
        
        print(f"💾 Speichere {len(sentences)} Sätze in Supabase...")
        
        # Bereinige und validiere Daten für Supabase
        clean_sentences = []
        for sentence in sentences:
            # Reasoning aus linguistic_notes extrahieren falls vorhanden
            reasoning = ""
            if isinstance(sentence.get('linguistic_notes'), dict):
                reasoning = sentence['linguistic_notes'].get('reasoning', '')
            elif 'reasoning' in sentence:
                reasoning = sentence['reasoning']
            
            clean_sentence = {
                "text_id": sentence.get("text_id"),
                "position": int(sentence.get("position", 0)),
                "halunder_text": sentence.get("halunder_text"),
                "german_text": sentence.get("german_text"),
                "match_confidence": float(sentence.get("match_confidence")) if sentence.get("match_confidence") is not None else None,
                "is_idiom": bool(sentence.get("is_idiom", False)),
                "linguistic_notes": {"reasoning": reasoning} if reasoning else {}
            }
            
            clean_sentences.append(clean_sentence)
        
        try:
            response = self.client.table('sentences').insert(clean_sentences).execute()
            print(f"✅ {len(clean_sentences)} Sätze erfolgreich in Supabase gespeichert")
            return response.data
        except Exception as e:
            print(f"❌ Supabase Fehler beim Speichern der Sätze:")
            print(f"   Fehler: {e}")
            print(f"   Beispiel-Datenstruktur: {clean_sentences[0] if clean_sentences else 'LEER'}")
            raise e
            
    def add_translation_aids(self, aids: List[dict]):
        """Add translation aid entries"""
        self.client.table('translation_aids').insert(aids).execute()
    
    def export_parallel_sentences(self) -> List[dict]:
        """Export all parallel sentences as list"""
        response = self.client.table('sentences')\
            .select('*')\
            .not_.is_('german_text', 'null')\
            .not_.is_('halunder_text', 'null')\
            .execute()
        
        return response.data
    
    def save_csv_export(self, data: List[dict], filename: str):
        """Save data to CSV file"""
        if not data:
            return
        
        # Create exports directory if it doesn't exist
        os.makedirs('exports', exist_ok=True)
        
        filepath = os.path.join('exports', filename)
        
        # Get all keys for CSV headers
        headers = list(data[0].keys())
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)
    
    def get_all_texts(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """Get all texts with metadata"""
        response = self.client.table('texts')\
            .select('*')\
            .order('created_at', desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        return response.data
    
    def get_sentence_count(self, text_id: str) -> int:
        """Get sentence count for a text"""
        response = self.client.table('sentences')\
            .select('id', count='exact')\
            .eq('text_id', text_id)\
            .execute()
        return response.count or 0
    
    def get_sentences_by_text(self, text_id: str) -> List[dict]:
        """Get all sentences for a specific text"""
        response = self.client.table('sentences')\
            .select('*')\
            .eq('text_id', text_id)\
            .order('position')\
            .execute()
        return response.data
    
    def update_sentence(self, sentence_id: str, update_data: dict) -> dict:
        """Update a sentence"""
        # Add reasoning to linguistic_notes if provided
        if 'reasoning' in update_data:
            linguistic_notes = update_data.get('linguistic_notes', {})
            if not isinstance(linguistic_notes, dict):
                linguistic_notes = {}
            linguistic_notes['reasoning'] = update_data.pop('reasoning')
            update_data['linguistic_notes'] = linguistic_notes
        
        response = self.client.table('sentences')\
            .update(update_data)\
            .eq('id', sentence_id)\
            .execute()
        return response.data[0] if response.data else None
    
    def delete_sentence(self, sentence_id: str):
        """Delete a sentence"""
        self.client.table('sentences')\
            .delete()\
            .eq('id', sentence_id)\
            .execute()
    
    def update_text(self, text_id: str, update_data: dict) -> dict:
        """Update text metadata"""
        response = self.client.table('texts')\
            .update(update_data)\
            .eq('id', text_id)\
            .execute()
        return response.data[0] if response.data else None
    
    def get_all_sentences_with_metadata(self) -> List[dict]:
        """Get all sentences with text metadata joined"""
        # First try with a join
        response = self.client.table('sentences')\
            .select('*, texts!inner(source_title, source_author, source_page, added_by)')\
            .order('created_at', desc=False)\
            .execute()
        
        # Flatten the response
        sentences = []
        for item in response.data:
            sentence = {**item}
            # Extract reasoning from linguistic_notes if exists
            if sentence.get('linguistic_notes') and isinstance(sentence['linguistic_notes'], dict):
                sentence['reasoning'] = sentence['linguistic_notes'].get('reasoning', '')
            else:
                sentence['reasoning'] = ''
            
            # Flatten texts data
            if 'texts' in sentence:
                sentence['source_title'] = sentence['texts']['source_title']
                sentence['source_author'] = sentence['texts']['source_author'] 
                sentence['source_page'] = sentence['texts']['source_page']
                sentence['added_by'] = sentence['texts']['added_by']
                del sentence['texts']
            
            sentences.append(sentence)
        
        return sentences