import os
import sys
import io
import json
import subprocess
import webbrowser
import threading
from datetime import datetime
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS


def _log(msg):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(str(msg).encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass

import memory as mem
import brain
import gmail_integration as gmail
import video_processor as vidproc
import telegram_bot

try:
    from winotify import Notification
    HAS_NOTIFY = True
except ImportError:
    HAS_NOTIFY = False

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False

UI_DIR = Path(__file__).parent / "ui"
app = Flask(__name__, static_folder=str(UI_DIR))
CORS(app)

scheduler = None
proactive_queue = []


# --- Static UI ---

@app.route("/")
def index():
    return send_from_directory(str(UI_DIR), "index.html")


@app.errorhandler(404)
def not_found(e):
    path = request.path.lstrip("/")
    if not path.startswith("api/"):
        try:
            return send_from_directory(str(UI_DIR), path)
        except Exception:
            pass
    return jsonify({"error": "not found"}), 404


# --- Chat API ---

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Mensaje vacio"}), 400

    api_key = mem.get_config("api_key")
    if not api_key:
        return jsonify({"error": "API Key no configurada. Ve a Configuracion y guarda tu API Key."}), 400

    try:
        result = brain.chat(user_message, api_key)
        _log(f"[CHAT] actions={result.get('actions', [])}")
        execute_actions(result.get("actions", []))
        return jsonify(result)
    except Exception as e:
        _log(f"[CHAT ERROR] {e}")
        err_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        return jsonify({"error": err_msg}), 500


# --- Chat History ---

@app.route("/api/history", methods=["GET"])
def api_history():
    limit = request.args.get("limit", 20, type=int)
    messages = mem.get_recent_conversations(limit=limit)
    return jsonify(messages)


# --- Text-to-Speech (Edge TTS) ---

_piper_voice = None

def _get_piper_voice():
    global _piper_voice
    if _piper_voice is None:
        try:
            from piper import PiperVoice
            model_dir = Path(__file__).parent / "tts_models"
            model_path = model_dir / "es_MX-ald-medium.onnx"
            config_path = model_dir / "es_MX-ald-medium.onnx.json"
            if model_path.exists():
                _piper_voice = PiperVoice.load(str(model_path), str(config_path))
                _log("[TTS] Piper voice loaded")
        except Exception as e:
            _log(f"[TTS] Piper load failed: {e}")
    return _piper_voice


@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Sin texto"}), 400

    audio_path = Path(__file__).parent / "ui" / "tts_output.mp3"
    wav_path = Path(__file__).parent / "ui" / "tts_output.wav"

    # 1) Piper TTS (neural, local, realistic)
    piper = _get_piper_voice()
    if piper:
        try:
            import numpy as np, wave, subprocess
            all_audio = []
            for chunk in piper.synthesize(text):
                all_audio.append(chunk.audio_float_array)
            audio = np.concatenate(all_audio)
            audio_int16 = (audio * 32767).astype(np.int16)
            with wave.open(str(wav_path), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(piper.config.sample_rate)
                wf.writeframes(audio_int16.tobytes())
            subprocess.run([
                "ffmpeg", "-y", "-i", str(wav_path),
                "-ar", "44100", "-ac", "1", "-b:a", "128k",
                str(audio_path)
            ], capture_output=True, timeout=15)
            if audio_path.exists() and audio_path.stat().st_size > 100:
                return send_from_directory(str(UI_DIR), "tts_output.mp3", mimetype="audio/mpeg")
        except Exception as e:
            _log(f"[TTS] Piper error: {e}")

    # 2) Edge TTS fallback
    try:
        import asyncio, edge_tts
        voice = data.get("voice", "es-AR-TomasNeural")
        async def generate():
            communicate = edge_tts.Communicate(text, voice, rate="+5%", pitch="-2Hz")
            await communicate.save(str(audio_path))
        asyncio.run(generate())
        return send_from_directory(str(UI_DIR), "tts_output.mp3", mimetype="audio/mpeg")
    except Exception:
        pass

    # 3) gTTS fallback
    try:
        from gtts import gTTS
        tts = gTTS(text, lang="es", tld="com.ar")
        tts.save(str(audio_path))
        return send_from_directory(str(UI_DIR), "tts_output.mp3", mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tts/voices", methods=["GET"])
def api_tts_voices():
    import asyncio, edge_tts
    async def list_voices():
        voices = await edge_tts.list_voices()
        return [v for v in voices if v["Locale"].startswith("es-")]
    try:
        voices = asyncio.run(list_voices())
        return jsonify(voices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Config ---

@app.route("/api/config", methods=["GET"])
def api_get_config():
    api_key = mem.get_config("api_key", "")
    provider = mem.get_config("ai_provider", "anthropic")
    return jsonify({
        "has_api_key": bool(api_key),
        "ai_provider": provider,
        "ai_model": mem.get_config("model", ""),
        "gmail_configured": gmail.is_configured(),
        "gmail_authenticated": gmail.is_authenticated(),
        "memory_count": len(mem.get_memories()),
        "conversation_count": mem.get_conversation_count(),
        "calendar_configured": bool(mem.get_config("google_calendar_url")),
        "whatsapp_configured": bool(mem.get_config("greenapi_instance_id")),
        "together_configured": bool(mem.get_config("together_api_key")),
    })


@app.route("/api/connections", methods=["GET"])
def api_connections():
    api_key = mem.get_config("api_key", "")
    ext_connected = browser_state.get("lastUpdate") is not None
    last_update = browser_state.get("lastUpdate")
    ext_recent = False
    if last_update:
        try:
            from datetime import timedelta
            lu = datetime.fromisoformat(last_update)
            ext_recent = (datetime.now() - lu) < timedelta(seconds=15)
        except Exception:
            pass
    return jsonify({
        "connections": [
            {
                "id": "claude",
                "name": "Claude AI",
                "description": "Cerebro IA - Procesa todos los mensajes y comandos",
                "category": "active",
                "connected": bool(api_key),
                "icon": "claude"
            },
            {
                "id": "chrome",
                "name": "Chrome",
                "description": "Extension de navegador - Control de pestañas y media",
                "category": "active",
                "connected": ext_recent,
                "icon": "chrome"
            },
            {
                "id": "windows",
                "name": "Windows",
                "description": "Control del sistema - Apps, volumen, brillo, apagado",
                "category": "active",
                "connected": True,
                "icon": "windows"
            },
            {
                "id": "whatsapp",
                "name": "WhatsApp",
                "description": "Mensajes y llamadas via WhatsApp Web",
                "category": "passive",
                "connected": ext_recent,
                "icon": "whatsapp"
            },
            {
                "id": "youtube",
                "name": "YouTube",
                "description": "Reproduccion y control de musica y videos",
                "category": "passive",
                "connected": ext_recent,
                "icon": "youtube"
            },
            {
                "id": "spotify",
                "name": "Spotify",
                "description": "Reproduccion de musica via navegador",
                "category": "passive",
                "connected": ext_recent,
                "icon": "spotify"
            },
            {
                "id": "gmail",
                "name": "Gmail",
                "description": "Leer y enviar emails",
                "category": "passive",
                "connected": gmail.is_configured() and gmail.is_authenticated(),
                "icon": "gmail"
            },
            {
                "id": "together",
                "name": "Together AI",
                "description": "Generacion de imagenes con FLUX",
                "category": "passive",
                "connected": bool(mem.get_config("together_api_key")),
                "icon": "together"
            },
            {
                "id": "calendar",
                "name": "Google Calendar",
                "description": "Ver y gestionar eventos del calendario",
                "category": "available",
                "connected": bool(mem.get_config("google_calendar_url")),
                "icon": "calendar"
            },
            {
                "id": "telegram",
                "name": "Telegram",
                "description": "Control remoto desde el celular + notificaciones",
                "category": "active" if mem.get_config("telegram_bot_token") else "available",
                "connected": bool(mem.get_config("telegram_bot_token")),
                "icon": "telegram"
            },
            {
                "id": "notion",
                "name": "Notion",
                "description": "Notas, bases de datos y documentos",
                "category": "available",
                "connected": bool(mem.get_config("notion_api_key")),
                "icon": "notion"
            },
            {
                "id": "drive",
                "name": "Google Drive",
                "description": "Archivos y documentos en la nube",
                "category": "available",
                "connected": False,
                "icon": "drive"
            },
            {
                "id": "discord",
                "name": "Discord",
                "description": "Enviar y leer mensajes via bot",
                "category": "active" if mem.get_config("discord_bot_token") else "available",
                "connected": bool(mem.get_config("discord_bot_token")),
                "icon": "discord"
            },
            {
                "id": "slack",
                "name": "Slack",
                "description": "Mensajes en canales y directos",
                "category": "available",
                "connected": bool(mem.get_config("slack_webhook_url")),
                "icon": "slack"
            },
            {
                "id": "github",
                "name": "GitHub",
                "description": "Repos, issues y pull requests",
                "category": "available",
                "connected": bool(mem.get_config("github_token")),
                "icon": "github"
            },
            {
                "id": "trello",
                "name": "Trello",
                "description": "Tableros y tarjetas de proyecto",
                "category": "available",
                "connected": bool(mem.get_config("trello_api_key")),
                "icon": "trello"
            },
            {
                "id": "todoist",
                "name": "Todoist",
                "description": "Gestion avanzada de tareas",
                "category": "available",
                "connected": bool(mem.get_config("todoist_api_token")),
                "icon": "todoist"
            },
            {
                "id": "twitter",
                "name": "X / Twitter",
                "description": "Publicar y leer tweets",
                "category": "available",
                "connected": False,
                "icon": "twitter"
            },
            {
                "id": "instagram",
                "name": "Instagram",
                "description": "Ver feed y publicar contenido",
                "category": "available",
                "connected": False,
                "icon": "instagram"
            },
            {
                "id": "twitch",
                "name": "Twitch",
                "description": "Streams en vivo y chat",
                "category": "passive",
                "connected": ext_recent,
                "icon": "twitch"
            },
            {
                "id": "netflix",
                "name": "Netflix",
                "description": "Control de reproduccion de series y peliculas",
                "category": "passive",
                "connected": ext_recent,
                "icon": "netflix"
            },
            {
                "id": "teams",
                "name": "Microsoft Teams",
                "description": "Chat, llamadas y reuniones",
                "category": "available",
                "connected": False,
                "icon": "teams"
            },
            {
                "id": "sheets",
                "name": "Google Sheets",
                "description": "Hojas de calculo en la nube",
                "category": "available",
                "connected": False,
                "icon": "sheets"
            },
            {
                "id": "obsidian",
                "name": "Obsidian",
                "description": "Notas en Markdown con enlaces",
                "category": "available",
                "connected": bool(mem.get_config("obsidian_url")),
                "icon": "obsidian"
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "DALL-E y GPT como herramientas auxiliares",
                "category": "available",
                "connected": bool(mem.get_config("openai_api_key")),
                "icon": "openai"
            },
            {
                "id": "homeassistant",
                "name": "Home Assistant",
                "description": "Control de luces y dispositivos inteligentes",
                "category": "available",
                "connected": bool(mem.get_config("homeassistant_url")),
                "icon": "homeassistant"
            },
            {
                "id": "elevenlabs",
                "name": "ElevenLabs",
                "description": "Voces ultra realistas con IA",
                "category": "available",
                "connected": bool(mem.get_config("elevenlabs_api_key")),
                "icon": "elevenlabs"
            },
            {
                "id": "dropbox",
                "name": "Dropbox",
                "description": "Almacenamiento de archivos en la nube",
                "category": "available",
                "connected": False,
                "icon": "dropbox"
            },
        ]
    })


@app.route("/api/config/calendar", methods=["POST"])
def api_set_calendar():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL vacia"}), 400
    mem.set_config("google_calendar_url", url)
    return jsonify({"success": True})


@app.route("/api/config/connection", methods=["POST"])
def api_set_connection():
    data = request.json
    key = data.get("key", "").strip()
    value = data.get("value", "").strip()
    allowed_keys = [
        "telegram_bot_token", "discord_bot_token", "slack_webhook_url",
        "github_token", "trello_api_key", "todoist_api_token",
        "openai_api_key", "elevenlabs_api_key", "homeassistant_url",
        "obsidian_url", "notion_api_key", "google_calendar_url",
    ]
    if key not in allowed_keys:
        return jsonify({"error": "Clave no permitida"}), 400
    if not value:
        return jsonify({"error": "Valor vacio"}), 400
    mem.set_config(key, value)
    if key == "telegram_bot_token":
        telegram_bot.stop_bot()
        telegram_bot.start_bot(value)
        _log("[TELEGRAM] Bot reiniciado con nuevo token")
    return jsonify({"success": True})


@app.route("/api/config/whatsapp", methods=["POST"])
def api_set_whatsapp():
    data = request.json
    instance_id = data.get("instance_id", "").strip()
    token = data.get("token", "").strip()
    api_url = data.get("api_url", "").strip()
    if not instance_id or not token:
        return jsonify({"error": "Falta instance_id o token"}), 400
    mem.set_config("greenapi_instance_id", instance_id)
    mem.set_config("greenapi_token", token)
    if api_url:
        mem.set_config("greenapi_api_url", api_url)
    return jsonify({"success": True})


@app.route("/api/config/together-key", methods=["POST"])
def api_set_together_key():
    data = request.json
    key = data.get("key", "").strip()
    if len(key) < 10:
        return jsonify({"error": "La key es muy corta"}), 400
    mem.set_config("together_api_key", key)
    return jsonify({"success": True})


@app.route("/api/config/api-key", methods=["POST"])
def api_set_key():
    data = request.json
    key = data.get("key", "").strip()
    provider = data.get("provider", "anthropic").strip()
    model = data.get("model", "").strip()
    if len(key) < 10:
        return jsonify({"error": "La key es muy corta"}), 400
    if provider not in ("anthropic", "openrouter"):
        return jsonify({"error": "Proveedor invalido"}), 400
    mem.set_config("api_key", key)
    mem.set_config("ai_provider", provider)
    mem.set_config("model", model)
    return jsonify({"success": True})


@app.route("/api/config/test-key", methods=["POST"])
def api_test_key():
    import anthropic as anth
    api_key = mem.get_config("api_key", "")
    provider = mem.get_config("ai_provider", "anthropic")
    if not api_key:
        return jsonify({"error": "No hay API key guardada"}), 400

    if provider == "openrouter":
        client = anth.Anthropic(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        saved_model = mem.get_config("model", "")
        models = [saved_model] if saved_model else [
            "anthropic/claude-sonnet-4",
            "anthropic/claude-haiku-4",
            "anthropic/claude-3.5-sonnet",
        ]
    else:
        client = anth.Anthropic(api_key=api_key)
        models = [
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-5-20250929",
            "claude-sonnet-5-5",
        ]

    results = []
    working_model = None
    for model in models:
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Di: ok"}]
            )
            results.append({"model": model, "status": "OK"})
            if not working_model:
                working_model = model
                mem.set_config("model", model)
            break
        except anth.NotFoundError:
            results.append({"model": model, "status": "404 - No encontrado"})
        except anth.AuthenticationError:
            results.append({"model": model, "status": "401 - Key invalida"})
            break
        except anth.PermissionDeniedError:
            results.append({"model": model, "status": "403 - Sin permiso"})
        except anth.BadRequestError as e:
            results.append({"model": model, "status": f"400 - {e}"})
        except Exception as e:
            results.append({"model": model, "status": str(e)})
            break

    return jsonify({
        "key_prefix": api_key[:12] + "...",
        "provider": provider,
        "results": results,
        "working_model": working_model
    })


# --- Memory ---

@app.route("/api/memories", methods=["GET"])
def api_get_memories():
    category = request.args.get("category")
    memories = mem.get_memories(category=category)
    return jsonify(memories)


@app.route("/api/memories", methods=["POST"])
def api_save_memory():
    data = request.json
    mem.save_memory(data["category"], data["content"], data.get("importance", 5))
    return jsonify({"success": True})


@app.route("/api/memories/<int:memory_id>", methods=["DELETE"])
def api_delete_memory(memory_id):
    mem.delete_memory(memory_id)
    return jsonify({"success": True})


# --- Tasks ---

@app.route("/api/tasks", methods=["GET"])
def api_get_tasks():
    status = request.args.get("status", "pending")
    tasks = mem.get_tasks(status=status)
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.json
    task_id = mem.create_task(
        title=data["title"],
        description=data.get("description", ""),
        due_date=data.get("due_date"),
        due_time=data.get("due_time")
    )
    return jsonify({"id": task_id})


@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def api_complete_task(task_id):
    mem.complete_task(task_id)
    return jsonify({"success": True})


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def api_delete_task(task_id):
    mem.delete_task(task_id)
    return jsonify({"success": True})


# --- Gmail ---

@app.route("/api/gmail/setup", methods=["POST"])
def api_gmail_setup():
    data = request.json
    address = data.get("address", "").strip()
    app_password = data.get("app_password", "").strip()
    if not address or not app_password:
        return jsonify({"error": "Falta email o app password"}), 400
    mem.set_config("gmail_address", address)
    mem.set_config("gmail_app_password", app_password)
    result = gmail.read_emails(1)
    if "error" in result:
        mem.set_config("gmail_address", "")
        mem.set_config("gmail_app_password", "")
        return jsonify({"error": result["error"]}), 400
    return jsonify({"success": True})


@app.route("/api/gmail/emails", methods=["GET"])
def api_gmail_emails():
    count = request.args.get("count", 5, type=int)
    try:
        result = gmail.read_emails(count)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Dashboard ---

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    import urllib.request
    from urllib.parse import quote
    from datetime import datetime
    data = {}

    # Tasks
    try:
        tasks = mem.get_tasks(status="pending")
        data["tasks"] = tasks[:5] if tasks else []
        data["tasks_count"] = len(tasks) if tasks else 0
    except Exception:
        data["tasks"] = []
        data["tasks_count"] = 0

    # Weather
    try:
        city = "Resistencia"
        url = f"https://wttr.in/{quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            w = json.loads(resp.read().decode("utf-8"))
        current = w.get("current_condition", [{}])[0]
        data["weather"] = {
            "city": city,
            "temp": current.get("temp_C", "?"),
            "feels": current.get("FeelsLikeC", "?"),
            "desc": current.get("lang_es", [{}])[0].get("value", current.get("weatherDesc", [{}])[0].get("value", "?")),
            "humidity": current.get("humidity", "?"),
            "wind": current.get("windspeedKmph", "?"),
        }
    except Exception as e:
        data["weather"] = {"city": "?", "temp": "?", "desc": str(e)[:50]}

    # Calendar
    try:
        ical_url = mem.get_config("google_calendar_url")
        if ical_url:
            req = urllib.request.Request(ical_url, headers={"User-Agent": "JARVIS/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                ical_data = resp.read().decode("utf-8", errors="replace")
            today = datetime.now().strftime("%Y%m%d")
            events = []
            in_event = False
            current_ev = {}
            for line in ical_data.split("\n"):
                line = line.strip()
                if line == "BEGIN:VEVENT":
                    in_event = True
                    current_ev = {}
                elif line == "END:VEVENT":
                    in_event = False
                    dtstart = current_ev.get("DTSTART", "")
                    if today in dtstart:
                        summary = current_ev.get("SUMMARY", "Sin titulo")
                        time_str = ""
                        if "T" in dtstart:
                            t = dtstart.split("T")[1][:4]
                            time_str = f"{t[:2]}:{t[2:4]}"
                        events.append({"time": time_str, "title": summary})
                elif in_event and ":" in line:
                    k, v = line.split(":", 1)
                    k = k.split(";")[0]
                    current_ev[k] = v
            data["events"] = events
        else:
            data["events"] = []
    except Exception:
        data["events"] = []

    # Emails
    try:
        if mem.get_config("gmail_address"):
            result = gmail.read_emails(3)
            if isinstance(result, dict) and "emails" in result:
                data["emails"] = [{"from": e.get("from", "?"), "subject": e.get("subject", "Sin asunto")} for e in result["emails"][:3]]
                data["emails_count"] = result.get("total", len(result["emails"]))
            else:
                data["emails"] = []
                data["emails_count"] = 0
        else:
            data["emails"] = []
            data["emails_count"] = 0
    except Exception:
        data["emails"] = []
        data["emails_count"] = 0

    # System
    data["memory_count"] = mem.get_config("memory_count") or 0
    try:
        data["memory_count"] = len(mem.search_memories("", limit=999))
    except Exception:
        pass
    data["conversation_count"] = mem.get_config("conversation_count") or 0
    data["time"] = datetime.now().strftime("%H:%M")
    data["date"] = datetime.now().strftime("%A %d de %B").capitalize()
    data["greeting"] = "Buenos dias" if datetime.now().hour < 12 else "Buenas tardes" if datetime.now().hour < 19 else "Buenas noches"

    return jsonify(data)


# --- Presentation Generator ---

@app.route("/api/presentation", methods=["POST"])
def api_presentation():
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        import os, tempfile

        data = request.json or {}
        title = data.get("title", "Presentación")
        slides_data = data.get("slides", [])

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # Title slide
        slide_layout = prs.slide_layouts[6]  # blank
        slide = prs.slides.add_slide(slide_layout)
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(0x0a, 0x0a, 0x1a)

        txBox = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(2))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(44)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0xff, 0x95, 0x00)
        p.alignment = PP_ALIGN.CENTER

        p2 = tf.add_paragraph()
        p2.text = "Generado por J.A.R.V.I.S."
        p2.font.size = Pt(18)
        p2.font.color.rgb = RGBColor(0x88, 0x88, 0x99)
        p2.alignment = PP_ALIGN.CENTER

        for sd in slides_data:
            slide = prs.slides.add_slide(slide_layout)
            bg = slide.background
            fill = bg.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor(0x0a, 0x0a, 0x1a)

            txTitle = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.5), Inches(1))
            tf = txTitle.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = sd.get("title", "")
            p.font.size = Pt(32)
            p.font.bold = True
            p.font.color.rgb = RGBColor(0xff, 0x95, 0x00)

            content = sd.get("content", "")
            if isinstance(content, list):
                lines = content
            else:
                lines = [l.strip() for l in content.split("\n") if l.strip()]

            txBody = slide.shapes.add_textbox(Inches(1), Inches(1.8), Inches(11), Inches(5))
            tf2 = txBody.text_frame
            tf2.word_wrap = True
            for i, line in enumerate(lines):
                p = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
                p.text = line
                p.font.size = Pt(20)
                p.font.color.rgb = RGBColor(0xdd, 0xdd, 0xee)
                p.space_after = Pt(8)

        out_dir = os.path.join(os.path.dirname(__file__), "ui", "downloads")
        os.makedirs(out_dir, exist_ok=True)
        fname = title.replace(" ", "_")[:30] + ".pptx"
        fpath = os.path.join(out_dir, fname)
        prs.save(fpath)

        return jsonify({"success": True, "file": f"/downloads/{fname}", "path": fpath})
    except ImportError:
        return jsonify({"error": "python-pptx no instalado. Ejecutar: pip install python-pptx"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Serve downloads
@app.route("/downloads/<path:filename>")
def serve_download(filename):
    import os
    downloads_dir = os.path.join(os.path.dirname(__file__), "ui", "downloads")
    return send_from_directory(downloads_dir, filename, as_attachment=True)


# --- Proactive notifications ---

@app.route("/api/proactive", methods=["GET"])
def api_proactive():
    global proactive_queue
    if proactive_queue:
        msgs = proactive_queue[:]
        proactive_queue = []
        return jsonify({"messages": msgs})
    return jsonify({"messages": []})


last_weather_alert = None

def check_proactive():
    global proactive_queue, last_weather_alert
    now = datetime.now()

    # Task reminders (existing logic moved here too)
    check_task_reminders()

    # Weather alert (once per hour if rain expected)
    if last_weather_alert is None or (now - last_weather_alert).seconds > 3600:
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://wttr.in/Buenos+Aires?format=%C&lang=es",
                headers={"User-Agent": "curl/7.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                weather = resp.read().decode("utf-8").strip().lower()
            if any(w in weather for w in ["lluvia", "tormenta", "rain", "thunder", "llovizna"]):
                proactive_queue.append({
                    "type": "weather_alert",
                    "text": f"Señor, alerta climatica: se esperan {weather} en Buenos Aires. Le sugiero llevar paraguas."
                })
                last_weather_alert = now
        except Exception:
            pass


# --- Actions executor ---

def find_chrome():
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

CHROME_PATH = find_chrome()

def open_in_chrome(url):
    if CHROME_PATH:
        subprocess.Popen([CHROME_PATH, url])
    else:
        webbrowser.open(url)


def find_firefox():
    paths = [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

FIREFOX_PATH = find_firefox()

def _discover_apps():
    """Descubre aplicaciones instaladas en Windows buscando en Start Menu y Program Files."""
    import glob
    apps = {}
    search_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]
    for base in search_dirs:
        if not os.path.isdir(base):
            continue
        for lnk in glob.glob(os.path.join(base, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0].lower()
            skip = ["uninstall", "desinstalar", "readme", "help", "ayuda", "manual", "license", "changelog"]
            if any(s in name for s in skip):
                continue
            apps[name] = lnk
    # Steam games
    steam_dirs = [
        r"C:\Program Files (x86)\Steam\steamapps\common",
        r"C:\Program Files\Steam\steamapps\common",
        r"D:\SteamLibrary\steamapps\common",
        r"E:\SteamLibrary\steamapps\common",
    ]
    for sd in steam_dirs:
        if os.path.isdir(sd):
            for game_dir in os.listdir(sd):
                game_lower = game_dir.lower()
                game_path = os.path.join(sd, game_dir)
                exes = glob.glob(os.path.join(game_path, "*.exe"))
                if exes:
                    apps[f"steam:{game_lower}"] = exes[0]
    # Epic Games - leer manifiestos para encontrar juegos en cualquier ubicacion
    epic_manifest_dir = r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests"
    if os.path.isdir(epic_manifest_dir):
        for mf in glob.glob(os.path.join(epic_manifest_dir, "*.item")):
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                display = data.get("DisplayName", "").strip()
                install = data.get("InstallLocation", "")
                app_name = data.get("AppName", "")
                if display and install and os.path.isdir(install):
                    clean_name = display.lower().replace("\u00ae", "").replace("\u2122", "").strip()
                    launch_exe = data.get("LaunchExecutable", "")
                    if launch_exe:
                        full_exe = os.path.join(install, launch_exe)
                        if os.path.isfile(full_exe):
                            apps[f"epic:{clean_name}"] = full_exe
                            continue
                    exes = glob.glob(os.path.join(install, "**", "*.exe"), recursive=True)
                    main_exes = [e for e in exes if "unins" not in e.lower() and "crash" not in e.lower() and "redist" not in e.lower()]
                    if main_exes:
                        apps[f"epic:{clean_name}"] = main_exes[0]
            except Exception:
                continue
    # Fallback: carpetas conocidas de Epic
    epic_dirs = [
        r"C:\Program Files\Epic Games",
        r"D:\Epic Games",
        r"E:\Epic Games",
    ]
    for ed in epic_dirs:
        if os.path.isdir(ed):
            for game_dir in os.listdir(ed):
                if game_dir.lower() in ("launcher", "directxredist", "epic online services"):
                    continue
                game_lower = game_dir.lower()
                key = f"epic:{game_lower}"
                if key in apps:
                    continue
                game_path = os.path.join(ed, game_dir)
                exes = glob.glob(os.path.join(game_path, "**", "*.exe"), recursive=True)
                main_exes = [e for e in exes if "unins" not in e.lower() and "crash" not in e.lower() and "redist" not in e.lower()]
                if main_exes:
                    apps[key] = main_exes[0]
    return apps

DISCOVERED_APPS = _discover_apps()
_log(f"[SERVER] Descubiertas {len(DISCOVERED_APPS)} aplicaciones instaladas")

APP_PATHS = {
    "chrome": CHROME_PATH or "chrome",
    "firefox": FIREFOX_PATH or "firefox",
    "mozilla firefox": FIREFOX_PATH or "firefox",
    "whatsapp": "whatsapp_web",
    "whatsapp web": "whatsapp_web",
    "word": "start winword",
    "excel": "start excel",
    "powerpoint": "start powerpnt",
    "spotify": "start spotify:",
    "calculadora": "calc",
    "notepad": "notepad",
    "bloc de notas": "notepad",
    "explorador": "explorer",
    "cmd": "cmd",
    "terminal": "wt",
    "chatgpt": "uwp:OpenAI.Codex_2p2nqsd0c76g0!App",
    "chat gpt": "uwp:OpenAI.Codex_2p2nqsd0c76g0!App",
    "claude": "uwp:Claude_pzs8sxrjxfjjc!Claude",
    "claude ai": "uwp:Claude_pzs8sxrjxfjjc!Claude",
    "cloud": "uwp:Claude_pzs8sxrjxfjjc!Claude",
    "cloud code": "uwp:Claude_pzs8sxrjxfjjc!Claude",
    "discord": "start discord:",
    "steam": "start steam:",
}

WEBSITE_SHORTCUTS = {
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "chatgpt": "https://chatgpt.com",
    "cloud chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "tiktok": "https://www.tiktok.com",
    "wikipedia": "https://es.wikipedia.org",
    "facebook": "https://www.facebook.com",
    "reddit": "https://www.reddit.com",
    "twitch": "https://www.twitch.tv",
    "discord": "https://discord.com/app",
    "mercadolibre": "https://www.mercadolibre.com.ar",
}


# --- Browser Extension Link ---

browser_state = {"tabs": [], "media": [], "activeMedia": [], "lastUpdate": None}
browser_commands = []


@app.route("/api/browser/state", methods=["POST"])
def api_browser_state():
    global browser_state
    data = request.json
    browser_state["tabs"] = data.get("tabs", [])
    browser_state["media"] = data.get("media", [])
    browser_state["activeMedia"] = data.get("activeMedia", [])
    browser_state["lastUpdate"] = datetime.now().isoformat()
    return jsonify({"ok": True})


@app.route("/api/browser/state", methods=["GET"])
def api_browser_state_get():
    return jsonify(browser_state)


@app.route("/api/browser/commands", methods=["GET"])
def api_browser_commands_get():
    global browser_commands
    cmds = browser_commands[:]
    browser_commands = []
    return jsonify({"commands": cmds})


@app.route("/api/browser/command", methods=["POST"])
def api_browser_command_post():
    global browser_commands
    data = request.json
    _log(f"[BROWSER CMD] Recibido: {data}")
    browser_commands.append(data)
    return jsonify({"ok": True, "queued": len(browser_commands)})


@app.route("/api/telegram/send", methods=["POST"])
def api_telegram_send():
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Sin texto"}), 400
    ok = telegram_bot.send_notification(text)
    return jsonify({"success": ok})

whatsapp_messages_store = []

@app.route("/api/browser/whatsapp-messages", methods=["GET"])
def api_whatsapp_messages_get():
    return jsonify({"messages": whatsapp_messages_store[:]})

@app.route("/api/browser/whatsapp-messages", methods=["POST"])
def api_whatsapp_messages_post():
    global whatsapp_messages_store
    data = request.json
    whatsapp_messages_store = data.get("messages", [])
    return jsonify({"ok": True})

@app.route("/api/apps/list", methods=["GET"])
def api_apps_list():
    query = request.args.get("q", "").lower()
    results = {}
    for name in APP_PATHS:
        if not query or query in name:
            results[name] = "builtin"
    for name in DISCOVERED_APPS:
        clean = name.replace("steam:", "")
        if not query or query in clean:
            results[name] = "discovered"
    return jsonify({"apps": results, "total": len(results)})


extension_logs = []

@app.route("/api/browser/log", methods=["POST"])
def api_browser_log():
    data = request.json
    entry = {"ts": datetime.now().isoformat(), **data}
    extension_logs.append(entry)
    if len(extension_logs) > 50:
        extension_logs.pop(0)
    _log(f"[EXT-LOG] {data}")
    return jsonify({"ok": True})

@app.route("/api/browser/logs", methods=["GET"])
def api_browser_logs_get():
    return jsonify(extension_logs)

@app.route("/api/browser/debug", methods=["GET"])
def api_browser_debug():
    return jsonify({
        "pending_commands": browser_commands[:],
        "state_lastUpdate": browser_state.get("lastUpdate"),
        "media_count": len(browser_state.get("media", [])),
        "activeMedia_count": len(browser_state.get("activeMedia", [])),
        "tabs_count": len(browser_state.get("tabs", [])),
        "media": browser_state.get("media", []),
        "extension_logs": extension_logs[-10:]
    })


# --- Document Analysis ---

@app.route("/api/analyze/upload", methods=["POST"])
def api_analyze_upload():
    print("[ANALYZE] Request recibido", flush=True)
    if "file" not in request.files:
        print("[ANALYZE] No hay archivo en el request", flush=True)
        return jsonify({"error": "No se envio ningun archivo"}), 400

    file = request.files["file"]
    filename = file.filename or "documento"
    _log(f"[ANALYZE] Archivo: {filename}")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        text = ""
        if ext == "txt" or ext == "rtf":
            text = file.read().decode("utf-8", errors="ignore")
        elif ext == "pdf":
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
            try:
                try:
                    import pdfplumber
                    with pdfplumber.open(tmp_path) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                except ImportError:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(tmp_path)
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
            finally:
                os.unlink(tmp_path)
        elif ext in ("docx", "doc"):
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
            try:
                from docx import Document
                doc = Document(tmp_path)
                text = "\n".join(p.text for p in doc.paragraphs)
            finally:
                os.unlink(tmp_path)
        else:
            return jsonify({"error": f"Formato no soportado: .{ext}. Usa PDF, DOCX o TXT."}), 400

        if not text.strip():
            return jsonify({"error": "No se pudo extraer texto del archivo. Puede estar escaneado o vacio."}), 400

        text = text[:120000]
        _log(f"[ANALYZE] Texto extraido: {len(text)} chars")

        focus = "legal" if any(w in text.lower() for w in ["articulo", "ley ", "decreto", "jurisprudencia", "demanda", "sentencia", "codigo"]) else "general"
        if any(w in text.lower() for w in ["hipotesis", "metodologia", "abstract", "investigacion"]):
            focus = "academico"

        _log(f"[ANALYZE] Enviando a brain._analyze_text con focus={focus}...")
        raw_result = brain._analyze_text(text, focus, "es")
        _log(f"[ANALYZE] Resultado recibido: {len(str(raw_result))} chars")

        try:
            parsed = json.loads(raw_result)
            analysis = parsed.get("analysis", raw_result)
            focus = parsed.get("focus", focus)
        except (json.JSONDecodeError, TypeError):
            analysis = raw_result

        return jsonify({
            "success": True,
            "filename": filename,
            "chars": len(text),
            "focus": focus,
            "analysis": analysis
        })

    except Exception as e:
        return jsonify({"error": f"Error procesando archivo: {e}"}), 500


# --- Image Generation ---

IMAGES_DIR = Path(__file__).parent / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)


@app.route("/api/images/<path:filename>")
def serve_generated_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


# --- Video Processing ---

@app.route("/api/video/upload", methods=["POST"])
def api_video_upload():
    if "video" not in request.files:
        return jsonify({"error": "No se envio ningun video"}), 400
    file = request.files["video"]
    if not file.filename:
        return jsonify({"error": "Archivo vacio"}), 400
    filename = file.filename.replace(" ", "_")
    filepath = os.path.join(vidproc.UPLOAD_DIR, filename)
    file.save(filepath)
    make_clips = request.form.get("clips", "true").lower() == "true"
    clip_format = request.form.get("format", "horizontal")
    if clip_format not in ("horizontal", "vertical", "square"):
        clip_format = "horizontal"
    api_key = mem.get_config("api_key")
    try:
        result = vidproc.process_video(filepath, api_key, make_clips=make_clips, clip_format=clip_format)
        return jsonify({
            "success": True,
            "filename": filename,
            "duration": result["transcript"]["duration"],
            "full_text": result["transcript"]["full_text"],
            "segments": result["transcript"]["segments"],
            "clips": result.get("clips", []),
            "clip_error": result.get("clip_error")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/video/clips/<path:filename>")
def api_video_clip(filename):
    return send_from_directory(vidproc.CLIPS_DIR, filename)


@app.route("/api/video/transcript", methods=["POST"])
def api_video_transcript_only():
    if "video" not in request.files:
        return jsonify({"error": "No se envio ningun video"}), 400
    file = request.files["video"]
    filename = file.filename.replace(" ", "_")
    filepath = os.path.join(vidproc.UPLOAD_DIR, filename)
    file.save(filepath)
    try:
        result = vidproc.transcribe_video(filepath)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def execute_actions(actions):
    import time
    for action in actions:
        act = action.get("action")
        try:
            if len(actions) > 1:
                time.sleep(0.5)
            if act == "open_website":
                url = action["url"]
                open_in_chrome(url)
            elif act == "open_app":
                app_name = action["app_name"].lower()
                cmd = APP_PATHS.get(app_name)
                if cmd == "whatsapp_web":
                    open_in_chrome("https://web.whatsapp.com")
                elif cmd and cmd.startswith("uwp:"):
                    app_id = cmd[4:]
                    subprocess.Popen(f'start shell:AppsFolder\\{app_id}', shell=True)
                elif cmd:
                    subprocess.Popen(cmd, shell=True)
                elif app_name in WEBSITE_SHORTCUTS:
                    open_in_chrome(WEBSITE_SHORTCUTS[app_name])
                else:
                    # Buscar en apps descubiertas dinámicamente
                    found = DISCOVERED_APPS.get(app_name) or DISCOVERED_APPS.get(f"steam:{app_name}") or DISCOVERED_APPS.get(f"epic:{app_name}")
                    if not found:
                        # Buscar match exacto de palabras, no substring
                        best = None
                        best_score = 0
                        app_words = set(app_name.split())
                        for dname, dpath in DISCOVERED_APPS.items():
                            clean = dname.replace("steam:", "")
                            dwords = set(clean.split())
                            overlap = len(app_words & dwords)
                            if overlap > best_score and overlap >= min(len(app_words), len(dwords)):
                                best = dpath
                                best_score = overlap
                        if not best:
                            for dname, dpath in DISCOVERED_APPS.items():
                                clean = dname.replace("steam:", "")
                                if app_name in clean or clean in app_name:
                                    if len(clean) >= 3:
                                        best = dpath
                                        break
                        found = best
                    if found:
                        try:
                            os.startfile(found)
                        except Exception:
                            subprocess.Popen(f'start "" "{found}"', shell=True)
                    else:
                        try:
                            subprocess.Popen(f'start "" "{app_name}"', shell=True)
                        except Exception:
                            print(f"No se pudo abrir app: {app_name}")
            elif act == "system_notify":
                send_notification(action["title"], action["message"])
            elif act == "send_email":
                gmail.send_email(action["to"], action["subject"], action["body"])
            elif act == "open_file":
                fpath = action["path"]
                _log(f"[ACTION] Abriendo archivo: {fpath}")
                import subprocess
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", f'Start-Process "{fpath}"'],
                    creationflags=0x00000008
                )
            elif act == "read_emails":
                pass
        except Exception as e:
            print(f"Error executing action {act}: {e}")


def send_notification(title, message):
    if HAS_NOTIFY:
        toast = Notification(
            app_id="J.A.R.V.I.S.",
            title=title,
            msg=message,
        )
        toast.show()


# --- Task reminder checker ---

notified_tasks = set()

def check_task_reminders():
    tasks = mem.get_tasks(status="pending")
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    for task in tasks:
        if task["due_time"] and task["id"] not in notified_tasks:
            try:
                date_str = task["due_date"] if task["due_date"] else today
                due = datetime.strptime(f"{date_str} {task['due_time']}", "%Y-%m-%d %H:%M")
                diff = (due - now).total_seconds()
                if -300 <= diff <= 60:
                    title = task["title"]
                    if title.startswith("RECORDATORIO: "):
                        send_notification("JARVIS - Recordatorio", title[14:])
                    else:
                        send_notification("JARVIS - Tarea", title)
                    notified_tasks.add(task["id"])
            except ValueError:
                pass


def start_scheduler():
    global scheduler
    if HAS_SCHEDULER:
        scheduler = BackgroundScheduler()
        scheduler.add_job(check_proactive, "interval", seconds=30)
        scheduler.start()


# --- Global Hotkey (Ctrl+Alt+J) ---

def start_hotkey_listener(port):
    try:
        from pynput.keyboard import GlobalHotKeys

        def on_activate():
            open_in_chrome(f"http://localhost:{port}")

        hotkeys = GlobalHotKeys({'<ctrl>+<alt>+j': on_activate})
        hotkeys.daemon = True
        hotkeys.start()
        print("    Hotkey: Ctrl+Alt+J para abrir JARVIS")
    except Exception as e:
        print(f"    Hotkey no disponible: {e}")


# --- Main ---

def main():
    mem.init_db()
    start_scheduler()

    port = 8080
    start_hotkey_listener(port)

    print(f"""
    ==========================================
         J.A.R.V.I.S. v4.0 ONLINE

       Abri http://localhost:{port} en Chrome
       Hotkey: Ctrl+Alt+J desde cualquier app
       Para detener: Ctrl+C
    ==========================================
    """)

    tg_token = mem.get_config("telegram_bot_token")
    if tg_token:
        telegram_bot.start_bot(tg_token)
        _log("[TELEGRAM] Bot de Telegram iniciado")
    else:
        _log("[TELEGRAM] Sin token, bot no iniciado. Configurar en Conexiones.")

    threading.Timer(1.5, lambda: open_in_chrome(f"http://localhost:{port}")).start()

    # Auto-launch floating widget
    def _launch_widget():
        import subprocess
        widget_path = os.path.join(os.path.dirname(__file__), "widget.pyw")
        if os.path.exists(widget_path):
            try:
                subprocess.Popen(["pythonw", widget_path], creationflags=0x00000008)
                _log("[WIDGET] Widget flotante iniciado")
            except Exception as e:
                _log(f"[WIDGET] No se pudo iniciar: {e}")
    threading.Timer(3, _launch_widget).start()

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
