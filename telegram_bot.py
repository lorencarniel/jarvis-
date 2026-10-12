import os
import sys
import io
import json
import threading
import logging
import urllib.request

os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="[TELEGRAM] %(message)s")
log = logging.getLogger("telegram_bot")

JARVIS_API = "http://localhost:8080/api"

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    log.warning("python-telegram-bot no instalado. Ejecutar: pip install python-telegram-bot")


def _safe_log(msg):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass


def _call_jarvis(message):
    try:
        payload = json.dumps({"message": message}).encode("utf-8")
        req = urllib.request.Request(
            f"{JARVIS_API}/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("text", "No hubo respuesta.")
    except Exception as e:
        return f"Error comunicando con JARVIS: {e}"


def _get_system_status():
    try:
        req = urllib.request.Request(f"{JARVIS_API}/config")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = "JARVIS esta ONLINE\n"
        status += f"Conversaciones: {data.get('conversation_count', '?')}\n"
        status += f"Memorias: {data.get('memory_count', '?')}\n"
        status += f"Gmail: {'conectado' if data.get('gmail_configured') else 'no'}\n"
        status += f"IA: {'configurada' if data.get('has_api_key') else 'sin key'}"
        return status
    except Exception:
        return "JARVIS esta OFFLINE. La PC puede estar apagada."


def _wake_pc():
    try:
        from wakeonlan import send_magic_packet
        mac = "2C:F0:5D:70:76:B0"
        send_magic_packet(mac)
        return "Enviado paquete Wake-on-LAN. La PC deberia encenderse en unos segundos si tiene WOL activado en la BIOS."
    except ImportError:
        return "wakeonlan no instalado. Ejecutar: pip install wakeonlan"
    except Exception as e:
        return f"Error enviando WOL: {e}"


_authorized_user_id = None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _authorized_user_id
    user = update.effective_user
    _authorized_user_id = user.id
    _safe_log(f"[TELEGRAM] Usuario autorizado: {user.first_name} (ID: {user.id})")

    try:
        import memory as mem
        mem.set_config("telegram_chat_id", str(user.id))
    except Exception:
        pass

    await update.message.reply_text(
        f"Hola {user.first_name}! Soy JARVIS, tu asistente personal.\n\n"
        "Comandos disponibles:\n"
        "/status - Ver si la PC esta encendida\n"
        "/prender - Encender la PC (Wake-on-LAN)\n"
        "/tareas - Ver tareas pendientes\n"
        "/emails - Leer emails recientes\n\n"
        "O simplemente escribime lo que necesites y se lo paso a JARVIS."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    status = _get_system_status()
    await update.message.reply_text(status)


async def cmd_prender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    await update.message.reply_text("Intentando encender la PC...")
    result = _wake_pc()
    await update.message.reply_text(result)


async def cmd_tareas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    response = _call_jarvis("cuales son mis tareas pendientes")
    await update.message.reply_text(response[:4000])


async def cmd_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    response = _call_jarvis("leeme mis ultimos emails")
    await update.message.reply_text(response[:4000])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    text = update.message.text
    if not text:
        return

    _safe_log(f"[TELEGRAM] Mensaje: {text}")
    await update.message.reply_text("Procesando...")

    response = _call_jarvis(text)

    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
    else:
        await update.message.reply_text(response)


def _is_authorized(update: Update):
    global _authorized_user_id
    if _authorized_user_id is None:
        return True
    if update.effective_user.id != _authorized_user_id:
        return False
    return True


_bot_app = None
_bot_thread = None


def send_notification(text):
    if not _bot_app or not _authorized_user_id:
        return False
    try:
        import asyncio
        loop = _bot_app._loop if hasattr(_bot_app, '_loop') else None
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _bot_app.bot.send_message(chat_id=_authorized_user_id, text=text),
                loop
            )
        else:
            asyncio.run(_bot_app.bot.send_message(chat_id=_authorized_user_id, text=text))
        return True
    except Exception as e:
        _safe_log(f"[TELEGRAM] Error enviando notificacion: {e}")
        return False


def start_bot(token):
    global _bot_app, _bot_thread, _authorized_user_id

    if not HAS_TELEGRAM:
        _safe_log("[TELEGRAM] No se puede iniciar: python-telegram-bot no instalado")
        return False

    if not token:
        _safe_log("[TELEGRAM] No hay token configurado")
        return False

    try:
        import memory as mem
        saved_chat_id = mem.get_config("telegram_chat_id")
        if saved_chat_id:
            _authorized_user_id = int(saved_chat_id)
            _safe_log(f"[TELEGRAM] Chat ID recuperado: {_authorized_user_id}")
    except Exception:
        pass

    def _run():
        global _bot_app
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            _bot_app = Application.builder().token(token).build()
            _bot_app._loop = loop

            _bot_app.add_handler(CommandHandler("start", cmd_start))
            _bot_app.add_handler(CommandHandler("status", cmd_status))
            _bot_app.add_handler(CommandHandler("prender", cmd_prender))
            _bot_app.add_handler(CommandHandler("tareas", cmd_tareas))
            _bot_app.add_handler(CommandHandler("emails", cmd_emails))
            _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

            _safe_log(f"[TELEGRAM] Bot iniciado correctamente")
            loop.run_until_complete(_bot_app.run_polling(drop_pending_updates=True))
        except Exception as e:
            _safe_log(f"[TELEGRAM] Error: {e}")

    _bot_thread = threading.Thread(target=_run, daemon=True)
    _bot_thread.start()
    return True


def stop_bot():
    global _bot_app
    if _bot_app:
        try:
            _bot_app.stop()
        except Exception:
            pass
        _bot_app = None
