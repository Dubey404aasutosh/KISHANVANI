import os
import sys
import io
import base64
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# On Windows, the console's default stdout/stderr encoding is cp1252, which
# cannot encode Devanagari/Gujarati/Tamil/etc. characters. Every pipeline
# stage prints the farmer's (transcribed/generated) text for debugging, so
# without this, any non-Latin query crashes the request with
# UnicodeEncodeError the moment it tries to print. Force UTF-8 so the server
# never crashes just because a farmer asked a question in an Indian language.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from orchestrator import orchestrator_instance

app = FastAPI(title="KISANVANI Webhook")

FALLBACK_UI_DIR = os.path.join(os.path.dirname(__file__), "fallback_ui")

# Serve static assets (demo video, images, etc.) alongside the landing page
# from /assets, so index.html can reference them with relative paths.
app.mount("/assets", StaticFiles(directory=FALLBACK_UI_DIR), name="assets")

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serves the fallback recording UI."""
    index_path = os.path.join(FALLBACK_UI_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/process_audio")
async def process_audio(
    audio_file: UploadFile = File(...),
    crop: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
):
    """
    Endpoint for the fallback UI to submit recorded audio.
    crop/state/language are optional hints from the caller (e.g. an IVR menu
    or the fallback UI's dropdowns) - language is auto-detected from the
    audio itself when not supplied, so the pipeline works for any Indian
    language/crop/state without requiring these.
    """
    temp_file_path = f"temp_{audio_file.filename}"
    with open(temp_file_path, "wb") as f:
        f.write(await audio_file.read())

    detected_language = language or "hi"
    if orchestrator_instance:
        text_response, audio_path, detected_language = orchestrator_instance.handle_call(
            temp_file_path, caller_id="fallback_ui_user",
            language=language, crop=crop, state=state,
        )
    else:
        text_response = "Sorry, the system is still starting up. Please try again shortly."
        audio_path = None
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    audio_b64 = None
    if audio_path and os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
        os.remove(audio_path)  # Cleanup the generated TTS file

    return JSONResponse({
        "text": text_response,
        "audio_base64": audio_b64,
        "detected_language": detected_language,
    })

@app.post("/twilio_webhook")
async def twilio_webhook():
    """
    Placeholder for Twilio inbound call webhook.
    Would respond with TwiML to record audio or play response.
    """
    # For a real telephony webhook, you'd return an XML response (TwiML).
    return HTMLResponse(content="<Response><Say>Welcome to Kisanvani.</Say></Response>", media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server for KISANVANI Telephony Fallback UI...")
    uvicorn.run("webhook:app", host="0.0.0.0", port=8000, reload=True)
