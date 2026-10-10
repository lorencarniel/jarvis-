import os
import sys
import io
import json
import subprocess
import webbrowser
import threading
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import memory as mem
import brain
import gmail_integration as gmail
import video_processor as vidproc

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
        print(f"[CHAT] actions={result.get('actions', [])}", flush=True)
        execute_actions(result.get("actions", []))
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[CHAT ERROR] {e}", flush=True)
        return jsonify({"error": str(e)}), 500


# --- Chat History ---

@app.route("/api/history", methods=["GET"])
def api_history():
    limit = request.args.get("limit", 20, type=int)
    messages = mem.get_recent_conversations(limit=limit)
    return jsonify(messages)


# --- Text-to-Speech (Edge TTS) ---

@app.route("/api/tts", methods=["POST"])
def api_tts():
    import asyncio
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Sin texto"}), 400

    voice = data.get("voice", "es-AR-TomasNeural")
    audio_path = Path(__file__).parent / "ui" / "tts_output.mp3"

    try:
        import edge_tts
        async def generate():
            communicate = edge_tts.Communicate(text, voice, rate="+5%", pitch="-2Hz")
            await communicate.save(str(audio_path))

        asyncio.run(generate())
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
    return jsonify({
        "has_api_key": bool(api_key),
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
                "description": "Mensajes y notificaciones via bot",
                "category": "available",
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
                "description": "Mensajes y notificaciones via bot",
                "category": "available",
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
    if len(key) < 10:
        return jsonify({"error": "La key es muy corta"}), 400
    mem.set_config("api_key", key)
    mem.set_config("model", "")
    return jsonify({"success": True})


@app.route("/api/config/test-key", methods=["POST"])
def api_test_key():
    import anthropic as anth
    api_key = mem.get_config("api_key", "")
    if not api_key:
        return jsonify({"error": "No hay API key guardada"}), 400

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
        except anth.NotFoundError as e:
            results.append({"model": model, "status": f"404 - No encontrado"})
        except anth.AuthenticationError as e:
            results.append({"model": model, "status": f"401 - Key invalida"})
            break
        except anth.PermissionDeniedError as e:
            results.append({"model": model, "status": f"403 - Sin permiso"})
        except anth.BadRequestError as e:
            results.append({"model": model, "status": f"400 - {e}"})
        except Exception as e:
            results.append({"model": model, "status": str(e)})
            break

    return jsonify({
        "key_prefix": api_key[:12] + "...",
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
print(f"[SERVER] Descubiertas {len(DISCOVERED_APPS)} aplicaciones instaladas", flush=True)

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
    print(f"[BROWSER CMD] Recibido: {data}")
    browser_commands.append(data)
    return jsonify({"ok": True, "queued": len(browser_commands)})


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
    print(f"[EXT-LOG] {data}", flush=True)
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
    print(f"[ANALYZE] Archivo: {filename}", flush=True)
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
        print(f"[ANALYZE] Texto extraido: {len(text)} chars", flush=True)

        focus = "legal" if any(w in text.lower() for w in ["articulo", "ley ", "decreto", "jurisprudencia", "demanda", "sentencia", "codigo"]) else "general"
        if any(w in text.lower() for w in ["hipotesis", "metodologia", "abstract", "investigacion"]):
            focus = "academico"

        print(f"[ANALYZE] Enviando a brain._analyze_text con focus={focus}...", flush=True)
        raw_result = brain._analyze_text(text, focus, "es")
        print(f"[ANALYZE] Resultado recibido: {len(str(raw_result))} chars", flush=True)

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
                os.startfile(action["path"])
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

    threading.Timer(1.5, lambda: open_in_chrome(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
