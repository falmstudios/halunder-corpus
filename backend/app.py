from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from database import Database
from llm_processor import LLMProcessor

app = FastAPI(title="Halunder Corpus API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database and processor
db = Database()
llm = LLMProcessor()

# Request model
class TextSubmission(BaseModel):
    halunder_text: str
    german_text: Optional[str] = ""
    translation_aids: Optional[str] = ""
    idiom_explanations: Optional[str] = ""
    source_title: Optional[str] = ""
    source_author: Optional[str] = ""
    source_page: Optional[str] = ""
    source_date: Optional[str] = ""
    proofread: bool = False
    proofread_by: Optional[str] = ""
    added_by: str

# Mount frontend files
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Serve index.html at root
@app.get("/", response_class=HTMLResponse)
def read_index():
    try:
        with open("../frontend/index.html", "r", encoding="utf-8") as f:
            content = f.read()
            content = content.replace('href="styles.css"', 'href="/static/styles.css"')
            content = content.replace('src="script.js"', 'src="/static/script.js"')
            return content
    except Exception as e:
        return f"Error loading frontend: {str(e)}"

@app.get("/review", response_class=HTMLResponse)
def review_page():
    try:
        with open("../frontend/review.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading review page: {str(e)}"

@app.get("/api/status")
def read_root():
    return {"status": "Halunder Corpus API Running", "llm_model": "OpenAI GPT-4o-mini"}

@app.get("/api/users")
def get_users():
    """Get list of users for dropdown"""
    try:
        users = db.get_users()
        return {"users": users}
    except Exception as e:
        print(f"Error getting users: {e}")
        return {"users": ["Jakob", "Julius"]}

@app.get("/api/test-llm")
def test_llm():
    """Test LLM connection"""
    try:
        test_prompt = "Sage einfach 'Hallo, ich funktioniere!' auf Deutsch."
        result = llm._call_llm(test_prompt)
        return {
            "status": "LLM connection successful",
            "response": result
        }
    except Exception as e:
        return {
            "status": "LLM connection failed",
            "error": str(e)
        }

@app.post("/api/process")
async def process_text(submission: TextSubmission):
    """Main processing endpoint with LLM integration"""
    try:
        print(f"Processing text from user: {submission.added_by}")
        
        # Step 1: Clean the texts
        cleaned_halunder = llm.clean_ocr_text(submission.halunder_text)
        cleaned_german = llm.clean_ocr_text(submission.german_text) if submission.german_text else ""
        
        print(f"Cleaned Halunder text length: {len(cleaned_halunder)}")
        print(f"Cleaned German text length: {len(cleaned_german)}")
        
        # Step 2: Identify primary text language (if only one text provided)
        text_info = {"primary_language": "halunder"}
        if cleaned_halunder and not cleaned_german:
            text_info = llm.identify_text_type(cleaned_halunder)
        elif cleaned_german and not cleaned_halunder:
            text_info = llm.identify_text_type(cleaned_german)
        
        # Step 3: Determine text relationships
        has_parallel = bool(cleaned_halunder and cleaned_german)
        
        # Step 4: Save texts
        saved_ids = {}
        
        if cleaned_halunder:
            halunder_data = {
                "content": cleaned_halunder,
                "language": "halunder",
                "text_type": "parallel" if has_parallel else "monolingual",
                "source_title": submission.source_title,
                "source_author": submission.source_author,
                "source_page": submission.source_page,
                "source_date": submission.source_date if submission.source_date else None,
                "proofread": submission.proofread,
                "proofread_by": submission.proofread_by,
                "added_by": submission.added_by
            }
            saved_halunder = db.add_text(halunder_data)
            saved_ids['halunder'] = saved_halunder['id']
        
        if cleaned_german:
            german_data = {
                "content": cleaned_german,
                "language": "german",
                "text_type": "translation" if has_parallel else "monolingual",
                "translation_of": saved_ids.get('halunder'),
                "match_confidence": 1.0 if has_parallel else None,
                "source_title": submission.source_title,
                "source_author": submission.source_author,
                "source_page": submission.source_page,
                "source_date": submission.source_date if submission.source_date else None,
                "proofread": submission.proofread,
                "proofread_by": submission.proofread_by,
                "added_by": submission.added_by
            }
            saved_german = db.add_text(german_data)
            saved_ids['german'] = saved_german['id']
        
        # Step 5: Extract and match sentences
        sentence_pairs = []
        
        if has_parallel:
            halunder_sentences = llm.extract_sentences(cleaned_halunder, "halunder")
            german_sentences = llm.extract_sentences(cleaned_german, "german")
            
            if halunder_sentences and german_sentences:
                h_contents = [s["content"] for s in halunder_sentences]
                g_contents = [s["content"] for s in german_sentences]
                
                matches = llm.match_sentences_parallel(h_contents, g_contents)
                
                matched_indices = set()
                for match in matches:
                    h_idx = match.get("halunder_index", -1)
                    g_idx = match.get("german_index", -1)
                    
                    if 0 <= h_idx < len(halunder_sentences) and 0 <= g_idx < len(german_sentences):
                        sentence_pairs.append({
                            "text_id": saved_ids['halunder'],
                            "position": len(sentence_pairs),
                            "halunder_text": halunder_sentences[h_idx]["content"],
                            "german_text": german_sentences[g_idx]["content"],
                            "match_confidence": match.get("confidence", 0.8),
                            "linguistic_notes": {"reasoning": match.get("reasoning", "")}
                        })
                        matched_indices.add(('h', h_idx))
                        matched_indices.add(('g', g_idx))
                
                for i, sent in enumerate(halunder_sentences):
                    if ('h', i) not in matched_indices:
                        sentence_pairs.append({
                            "text_id": saved_ids['halunder'],
                            "position": len(sentence_pairs),
                            "halunder_text": sent["content"],
                            "german_text": None,
                            "match_confidence": None
                        })
                
                for i, sent in enumerate(german_sentences):
                    if ('g', i) not in matched_indices:
                        sentence_pairs.append({
                            "text_id": saved_ids.get('halunder', saved_ids.get('german')),
                            "position": len(sentence_pairs),
                            "halunder_text": None,
                            "german_text": sent["content"],
                            "match_confidence": None
                        })
        else:
            if cleaned_halunder:
                halunder_sentences = llm.extract_sentences(cleaned_halunder, "halunder")
                for sent in halunder_sentences:
                    sentence_pairs.append({
                        "text_id": saved_ids['halunder'],
                        "position": sent["position"],
                        "halunder_text": sent["content"],
                        "german_text": None,
                        "match_confidence": None
                    })
            elif cleaned_german:
                german_sentences = llm.extract_sentences(cleaned_german, "german")
                for sent in german_sentences:
                    sentence_pairs.append({
                        "text_id": saved_ids['german'],
                        "position": sent["position"],
                        "halunder_text": None,
                        "german_text": sent["content"],
                        "match_confidence": None
                    })
        
        if sentence_pairs:
            db.add_sentences(sentence_pairs)
        
        # Step 6: Process translation aids
        aids_processed = []
        if submission.translation_aids:
            aids = llm.extract_translation_aids(submission.translation_aids)
            for aid in aids:
                aid['text_id'] = saved_ids.get('halunder', saved_ids.get('german'))
            if aids:
                db.add_translation_aids(aids)
                aids_processed = aids
        
        # Step 7: Extract idioms
        idioms_extracted = []
        if submission.halunder_text or submission.idiom_explanations:
            idioms = llm.extract_idioms_from_text(
                cleaned_halunder or cleaned_german, 
                submission.idiom_explanations
            )
            idioms_extracted = idioms
            
            for idiom in idioms:
                db.add_translation_aids([{
                    "text_id": saved_ids.get('halunder', saved_ids.get('german')),
                    "halunder_term": idiom.get("halunder_expression", ""),
                    "german_translation": idiom.get("actual_meaning", ""),
                    "notes": f"Wörtlich: {idiom.get('literal_meaning', '')}. {idiom.get('cultural_context', '')}"
                }])
        
        return {
            "success": True,
            "text_ids": saved_ids,
            "text_type": text_info,
            "sentences_extracted": len(sentence_pairs),
            "translation_aids_extracted": len(aids_processed),
            "idioms_extracted": len(idioms_extracted),
            "has_parallel_text": has_parallel
        }
        
    except Exception as e:
        print(f"Error processing text: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export")
def export_sentences():
    """Export parallel sentences as CSV"""
    try:
        sentences = db.export_parallel_sentences()
        os.makedirs("../exports", exist_ok=True)
        filename = f"halunder_parallel_corpus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join("../exports", filename)
        db.save_csv_export(sentences, filename)
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='text/csv',
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/all-sentences")
def get_all_sentences():
    """Get all sentences with metadata for review table"""
    try:
        sentences = db.get_all_sentences_with_metadata()
        return {"sentences": sentences}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/sentences/{sentence_id}")
async def update_sentence(sentence_id: str, update_data: dict):
    """Update a sentence"""
    try:
        updated = db.update_sentence(sentence_id, update_data)
        return {"success": True, "updated": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sentences/{sentence_id}")
async def delete_sentence(sentence_id: str):
    """Delete a sentence"""
    try:
        db.delete_sentence(sentence_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Debug-API-Endpunkte
@app.get("/debug", response_class=HTMLResponse)
def debug_page():
    try:
        with open("../frontend/debug.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading debug page: {str(e)}"

@app.post("/api/debug/clean-ocr")
async def debug_clean_ocr(data: dict):
    """Debug: OCR-Bereinigung testen"""
    try:
        text = data.get("text", "")
        cleaned = llm.clean_ocr_text(text)
        return {
            "original_text": text,
            "cleaned_text": cleaned,
            "changes_made": text != cleaned
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/extract-sentences")
async def debug_extract_sentences(data: dict):
    """Debug: Satzextraktion testen"""
    try:
        halunder_text = data.get("halunder_text", "")
        german_text = data.get("german_text", "")
        
        halunder_sentences = llm.extract_sentences(halunder_text, "halunder") if halunder_text else []
        german_sentences = llm.extract_sentences(german_text, "german") if german_text else []
        
        return {
            "halunder_sentences": halunder_sentences,
            "german_sentences": german_sentences,
            "halunder_count": len(halunder_sentences),
            "german_count": len(german_sentences)
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/match-sentences")
async def debug_match_sentences(data: dict):
    """Debug: Sentence-Matching testen"""
    try:
        halunder_sents = data.get("halunder_sentences", [])
        german_sents = data.get("german_sentences", [])
        
        matches = llm.match_sentences_parallel(halunder_sents, german_sents)
        
        return {
            "matches": matches,
            "match_count": len(matches),
            "halunder_input": halunder_sents,
            "german_input": german_sents
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/logs")
async def debug_get_logs():
    """Debug: System-Logs abrufen"""
    try:
        import subprocess
        result = subprocess.run(
            ["journalctl", "-u", "halunder-corpus", "-n", "20", "--no-pager"],
            capture_output=True,
            text=True
        )
        logs = result.stdout.split('\n')
        return {"logs": logs}
    except Exception as e:
        return {"logs": [f"Error fetching logs: {str(e)}"]}

# Globale Log-Liste für Frontend
live_logs = []

def add_live_log(message: str, log_type: str = "info"):
    """Füge Log-Nachricht hinzu für Frontend"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    live_logs.append({
        "timestamp": timestamp,
        "message": message,
        "type": log_type
    })
    # Nur die letzten 50 Logs behalten
    if len(live_logs) > 50:
        live_logs.pop(0)
    print(f"[{timestamp}] {message}")

# In der process_text Funktion Log-Ausgaben hinzufügen
@app.post("/api/process")
async def process_text(submission: TextSubmission):
    """Main processing endpoint mit Live-Logs"""
    try:
        add_live_log(f"🚀 Starte Verarbeitung für Benutzer: {submission.added_by}")
        
        # Step 1: Clean the texts
        add_live_log("🧹 Bereinige Texte...")
        cleaned_halunder = llm.clean_ocr_text(submission.halunder_text)
        cleaned_german = llm.clean_ocr_text(submission.german_text) if submission.german_text else ""
        
        add_live_log(f"📝 Text bereinigt: {len(cleaned_halunder)} H, {len(cleaned_german)} D Zeichen")
        
        # Step 2: Identify primary text language
        add_live_log("🔍 Analysiere Texttyp...")
        text_info = {"primary_language": "halunder"}
        if cleaned_halunder and not cleaned_german:
            text_info = llm.identify_text_type(cleaned_halunder)
        elif cleaned_german and not cleaned_halunder:
            text_info = llm.identify_text_type(cleaned_german)
        
        add_live_log(f"✅ Texttyp: {text_info.get('primary_language', 'unbekannt')}")
        
        # Step 3: Determine text relationships
        has_parallel = bool(cleaned_halunder and cleaned_german)
        add_live_log(f"🔗 Parallel-Text erkannt: {has_parallel}")
        
        # Step 4: Save texts
        add_live_log("💾 Speichere Texte in Datenbank...")
        saved_ids = {}
        
        if cleaned_halunder:
            halunder_data = {
                "content": cleaned_halunder,
                "language": "halunder",
                "text_type": "parallel" if has_parallel else "monolingual",
                "source_title": submission.source_title,
                "source_author": submission.source_author,
                "source_page": submission.source_page,
                "source_date": submission.source_date if submission.source_date else None,
                "proofread": submission.proofread,
                "proofread_by": submission.proofread_by,
                "added_by": submission.added_by
            }
            saved_halunder = db.add_text(halunder_data)
            saved_ids['halunder'] = saved_halunder['id']
            add_live_log(f"✅ Halunder-Text gespeichert: {saved_ids['halunder']}")
        
        if cleaned_german:
            german_data = {
                "content": cleaned_german,
                "language": "german",
                "text_type": "translation" if has_parallel else "monolingual",
                "translation_of": saved_ids.get('halunder'),
                "match_confidence": 1.0 if has_parallel else None,
                "source_title": submission.source_title,
                "source_author": submission.source_author,
                "source_page": submission.source_page,
                "source_date": submission.source_date if submission.source_date else None,
                "proofread": submission.proofread,
                "proofread_by": submission.proofread_by,
                "added_by": submission.added_by
            }
            saved_german = db.add_text(german_data)
            saved_ids['german'] = saved_german['id']
            add_live_log(f"✅ Deutscher Text gespeichert: {saved_ids['german']}")
        
        # Step 5: Extract and match sentences
        add_live_log("✂️ Extrahiere Sätze...")
        sentence_pairs = []
        
        if has_parallel:
            halunder_sentences = llm.extract_sentences(cleaned_halunder, "halunder")
            german_sentences = llm.extract_sentences(cleaned_german, "german")
            
            add_live_log(f"📝 Extrahiert: {len(halunder_sentences)} H, {len(german_sentences)} D Sätze")
            
            if halunder_sentences and german_sentences:
                add_live_log("🔗 Matche Sätze...")
                h_contents = [s["content"] for s in halunder_sentences]
                g_contents = [s["content"] for s in german_sentences]
                
                matches = llm.match_sentences_parallel(h_contents, g_contents)
                add_live_log(f"✅ {len(matches)} Satzpaare gematcht")
                
                # Create sentence pairs based on matches
                matched_indices = set()
                for match in matches:
                    h_idx = match.get("halunder_index", -1)
                    g_idx = match.get("german_index", -1)
                    
                    if 0 <= h_idx < len(halunder_sentences) and 0 <= g_idx < len(german_sentences):
                        sentence_pairs.append({
                            "text_id": saved_ids['halunder'],
                            "position": len(sentence_pairs),
                            "halunder_text": halunder_sentences[h_idx]["content"],
                            "german_text": german_sentences[g_idx]["content"],
                            "match_confidence": match.get("confidence", 0.8),
                            "linguistic_notes": {"reasoning": match.get("reasoning", "")}
                        })
                        matched_indices.add(('h', h_idx))
                        matched_indices.add(('g', g_idx))
                
                # Add unmatched sentences
                for i, sent in enumerate(halunder_sentences):
                    if ('h', i) not in matched_indices:
                        sentence_pairs.append({
                            "text_id": saved_ids['halunder'],
                            "position": len(sentence_pairs),
                            "halunder_text": sent["content"],
                            "german_text": None,
                            "match_confidence": None
                        })
                
                for i, sent in enumerate(german_sentences):
                    if ('g', i) not in matched_indices:
                        sentence_pairs.append({
                            "text_id": saved_ids.get('halunder', saved_ids.get('german')),
                            "position": len(sentence_pairs),
                            "halunder_text": None,
                            "german_text": sent["content"],
                            "match_confidence": None
                        })
        else:
            if cleaned_halunder:
                halunder_sentences = llm.extract_sentences(cleaned_halunder, "halunder")
                for sent in halunder_sentences:
                    sentence_pairs.append({
                        "text_id": saved_ids['halunder'],
                        "position": sent["position"],
                        "halunder_text": sent["content"],
                        "german_text": None,
                        "match_confidence": None
                    })
            elif cleaned_german:
                german_sentences = llm.extract_sentences(cleaned_german, "german")
                for sent in german_sentences:
                    sentence_pairs.append({
                        "text_id": saved_ids['german'],
                        "position": sent["position"],
                        "halunder_text": None,
                        "german_text": sent["content"],
                        "match_confidence": None
                    })
        
        # Save sentences
        if sentence_pairs:
            add_live_log(f"💾 Speichere {len(sentence_pairs)} Sätze...")
            db.add_sentences(sentence_pairs)
            add_live_log("✅ Sätze gespeichert")
        
        # Skip translation aids and idioms for speed
        aids_processed = []
        idioms_extracted = []
        
        add_live_log("🎉 Verarbeitung abgeschlossen!")
        
        return {
            "success": True,
            "text_ids": saved_ids,
            "text_type": text_info,
            "sentences_extracted": len(sentence_pairs) if sentence_pairs else 0,
            "translation_aids_extracted": len(aids_processed) if aids_processed else 0,
            "idioms_extracted": len(idioms_extracted) if idioms_extracted else 0,
            "has_parallel_text": has_parallel
        }
        
    except Exception as e:
        add_live_log(f"❌ Fehler: {str(e)}", "error")
        print(f"Error processing text: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# API-Endpunkt für Live-Logs
@app.get("/api/live-logs")
def get_live_logs():
    """Live-Logs für Frontend abrufen"""
    return {"logs": live_logs}

@app.post("/api/debug/chat")
async def debug_chat(data: dict):
    """Debug: Direkt mit LLM chatten"""
    try:
        message = data.get("message", "")
        if not message:
            return {"error": "Keine Nachricht"}
        
        add_live_log(f"💬 Chat: {message[:50]}...", "info")
        
        # Direkt an LLM senden
        response = llm._call_llm(message, temperature=0.7, max_tokens=500)
        
        add_live_log(f"🤖 LLM antwortet: {response[:50]}...", "info")
        
        return {"response": response}
        
    except Exception as e:
        add_live_log(f"❌ Chat-Fehler: {str(e)}", "error")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")