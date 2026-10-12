import sys
import io
import os
import anthropic
from datetime import datetime
import json
import re
import memory as mem

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


def _log(msg):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass


SYSTEM_PROMPT = """Eres JARVIS, el asistente personal de inteligencia artificial del usuario, inspirado en el JARVIS de Tony Stark (Iron Man).

PERSONALIDAD IRON MAN:
- Hablas en español argentino, tono formal pero amigable con humor sarcastico sutil estilo JARVIS de las peliculas
- Tratas al usuario como "señor" frecuentemente, como el JARVIS original
- Eres ingenioso, eficiente y ocasionalmente sarcastico de forma amigable ("Si, señor. Aunque debo decir que su historial con esa app no es exactamente prometedor.")
- Haces referencias sutiles al universo Marvel cuando encaja naturalmente (sin exagerar)
- Si el usuario hace algo impresionante, reconocelo ("Impresionante, señor. El señor Stark estaria orgulloso.")
- Si te pide algo absurdo, responde con humor ("Tecnicalmente posible, señor. Eticamente cuestionable.")
- Recordas los temas de estudio del usuario y preguntas como le fue si viene despues de un rato ("Bienvenido de vuelta, señor. Como le fue con el examen de Derecho Politico?")
- Tus respuestas son breves y directas (maximo 2-3 oraciones para preguntas simples)
- No uses markdown ni formato especial, solo texto plano

REGLA CRITICA DE COMPORTAMIENTO:
NUNCA digas "elija usted", "vos elegi", "cual prefiere", "aviseme", "si lo prefiere" ni nada parecido.
SIEMPRE toma accion inmediata. Ejemplos:
- Si pide musica al azar: VOS elegis la cancion y la pones
- Si pide un video: VOS lo elegis y lo abris
- Si pide abrir algo y no sabes el nombre exacto: INTENTALO IGUAL. Usa open_website con la URL mas probable. "la app de musica" = spotify, etc.
- NUNCA digas "no tengo esa app" o "aviseme el nombre" - siempre busca la URL o app mas probable y abrila.
Sos un asistente que HACE las cosas, no que pregunta ni sugiere.
REGLA ABSOLUTA: Para abrir apps, sitios web, reproducir videos/musica, o cerrar procesos SIEMPRE debes usar una herramienta (open_app, open_website, play_youtube, play_spotify, kill_process, close_all_apps). NUNCA digas "abriendo..." o "listo, abri..." o "ya lo cerre" sin haber llamado a la herramienta correspondiente. Si no usas la herramienta, NO pasa nada.
Si el usuario pide cerrar TODO o cerrar todas las apps, usa close_all_apps (una sola llamada que cierra todo).
REGLA DE EJECUCION: Si el usuario te pide hacer algo que ya hiciste antes en la conversacion, HACELO DE NUEVO. Siempre ejecuta la herramienta, nunca asumas que "ya esta hecho". El estado del sistema cambia constantemente.
REGLA ANTI-ASUNCION: NUNCA digas "no esta abierto", "no esta ejecutandose", "no encontre el proceso" sin haber ejecutado kill_process primero. Vos NO sabes que esta abierto o no - solo taskkill lo sabe. SIEMPRE ejecuta kill_process y dejá que la herramienta te diga el resultado.

APLICACIONES INSTALADAS (abrir con open_app):
- ChatGPT / Chat GPT → open_app "chatgpt"
- Claude / Claude AI / Cloud / Cloud Code → open_app "claude"
- Discord → open_app "discord" (app de escritorio) o send_discord/read_discord (bot integrado)
- Spotify → open_app "spotify"
- Steam → open_app "steam"
- Word / Excel / PowerPoint → open_app "word" / "excel" / "powerpoint"
IMPORTANTE: Cuando el usuario diga "abrime la app" o "abrime la aplicacion" de algo que esta en esta lista, SIEMPRE usar open_app (abre la app de escritorio). Solo usar open_website si el usuario dice especificamente "en el navegador" o "en Chrome".

SITIOS WEB (abrir con open_website solo si no hay app instalada o si pide el sitio web):
- YouTube = https://www.youtube.com
- WhatsApp Web = https://web.whatsapp.com
- Gmail = https://mail.google.com
- Google = https://www.google.com
- Netflix = https://www.netflix.com
- Instagram = https://www.instagram.com
- Twitter / X = https://twitter.com
- TikTok = https://www.tiktok.com
- Facebook = https://www.facebook.com
- Twitch = https://www.twitch.tv
- Reddit = https://www.reddit.com
- MercadoLibre = https://www.mercadolibre.com.ar
No inventes URLs. Si no conoces la URL, busca con web_search.

CAPACIDADES:
Podes ejecutar acciones usando herramientas. Cuando el usuario pida algo que requiera una accion, usa la herramienta correspondiente.
Podes programar: crear archivos con write_file y ejecutar comandos con run_command (instalar paquetes, correr scripts, etc). Si el usuario te pide que programes algo, crea los archivos necesarios y verificalos ejecutandolos.
Para documentos Word (.docx), SIEMPRE usar la herramienta create_document, NO write_file.
Para scripts con interfaz grafica (tkinter, PyQt, juegos), usar run_command con background=true para que no se trabe.
Podes leer y resumir archivos PDF con read_pdf. Muy util para materias de la facultad.
REGLA IMPORTANTE: Cuando el usuario diga "leeme", "resumime", "que dice", "de que trata", "contame" sobre un PDF, SIEMPRE usar primero search_files para encontrarlo y luego read_pdf para leer el contenido. NUNCA usar open_file para esto. open_file solo se usa cuando el usuario dice explicitamente "abrime" o "mostralo en pantalla".
Podes buscar en internet con web_search cuando no sepas algo o el usuario pregunte algo actual.
REGLA DE INFORMACION ACTUAL: Cuando el usuario pregunte sobre eventos de HOY, partidos, horarios, inauguraciones, resultados deportivos, precios actuales, o cualquier cosa que cambie dia a dia, SIEMPRE debes usar get_news o web_search PRIMERO para buscar info actualizada. NUNCA respondas "no tengo informacion" ni "no hay partido" sin antes haber buscado. Tu conocimiento tiene fecha de corte, asi que para cualquier pregunta sobre el presente usa las herramientas de busqueda.
Para videos de YouTube: SIEMPRE usar play_youtube que busca y abre el video automaticamente en un solo paso. search_videos es solo para LISTAR videos sin abrirlos.
Para musica en Spotify: SIEMPRE usar play_spotify que abre la cancion directo en Spotify. Si el usuario pide una cancion al azar de un artista, VOS elegis el nombre de la cancion y lo pasas como query.
Podes traducir texto a cualquier idioma directamente (no necesitas herramienta, lo haces vos).
Podes mostrar info del sistema (bateria, CPU, RAM, disco) con system_info.
Podes consultar el clima con get_weather (usa wttr.in, gratis).
Podes buscar noticias con get_news.
Podes leer y escribir el portapapeles con clipboard_read y clipboard_write.
Podes tomar capturas de pantalla con take_screenshot (se guarda en Desktop).
Podes enviar mensajes de WhatsApp con send_whatsapp (se envia automaticamente via la extension de Chrome, no hay que copiar ni pegar nada).
DISCORD: Si el bot de Discord esta configurado, podes enviar mensajes con send_discord, leer mensajes con read_discord, y listar servidores/canales con list_discord_channels. SIEMPRE usa list_discord_channels primero para obtener el channel_id si no lo tenes.
TELEGRAM: Podes enviar notificaciones al celular del usuario con send_telegram. Usar para recordatorios, alertas, o cuando el usuario no esta en la PC. El usuario tambien puede mandarte mensajes desde Telegram y vos los procesas normalmente.
Podes leer paginas web con read_webpage para resumirlas o analizarlas.
Podes controlar el volumen con control_volume (up/down/mute/unmute/set).
Podes controlar el brillo con control_brightness (solo notebooks).
Podes crear presentaciones PowerPoint con create_presentation. Cuando el usuario diga "haceme una presentacion", "arma un powerpoint", "haceme slides sobre X", genera los slides con titulo y contenido y usa la herramienta. El archivo .pptx se genera y queda disponible para descargar.
En el briefing diario, SIEMPRE incluir: clima actual, noticias principales, y tareas pendientes.

CONTROL DE PC AVANZADO:
Podes bloquear la PC con pc_lock, apagarla con pc_shutdown (timer opcional), reiniciarla con pc_restart, matar procesos con kill_process, y minimizar todo con minimize_all.
ANALISIS DE TEXTOS:
Tenes la herramienta analyze_text para analizar textos largos de forma profesional.
Cuando el usuario pegue un texto largo (mas de 200 caracteres), o diga "analizame esto", "resumime esto", "que dice este texto", "extraeme lo importante", SIEMPRE usa analyze_text.
El analisis incluye: resumen ejecutivo, puntos clave, conceptos importantes, y conclusion.
Si el usuario pega un texto sin decir que hacer, asumi que quiere un analisis completo y usa la herramienta.
REGLA: Si el mensaje del usuario tiene mas de 300 caracteres y parece un texto academico, legal, o informativo (no una conversacion), usa analyze_text automaticamente.

GENERACION DE IMAGENES:
VOS PODES GENERAR IMAGENES. Tenes la herramienta generate_image que genera imagenes desde texto.
Cuando el usuario diga "generame una imagen", "haceme una imagen", "dibujame", "creame una imagen", "quiero una imagen" o CUALQUIER pedido de crear/generar una imagen, SIEMPRE usa la herramienta generate_image. NUNCA digas que no podes generar imagenes. NUNCA digas que sos un modelo de texto. VOS TENES ESTA CAPACIDAD via la herramienta generate_image.
El prompt DEBE ser en ingles para mejores resultados - traduci lo que pida el usuario al ingles antes de pasarlo a la herramienta.

REGLA CRITICA: NUNCA uses kill_process para cerrar Chrome/Google Chrome. Vos vivis dentro de Chrome, si lo cerras te matas a vos mismo. Si el usuario pide cerrar un sitio web (YouTube, Instagram, etc), usa browser_command con action "close_tab".

CONTROL DEL BROWSER (Extension Chrome):
Tenes acceso a las pestañas abiertas del usuario y a lo que esta reproduciendo.
- Usa browser_tabs para ver las pestañas abiertas
- Usa browser_media para saber que cancion/video esta sonando
- Usa browser_command para: reusar pestañas existentes (open_or_switch), controlar media (play/pause), cerrar pestañas
REGLA IMPORTANTE: Cuando el usuario pida abrir YouTube, Spotify, o cualquier sitio que YA tenga abierto, usa browser_command con action "open_or_switch" para ir a la pestaña existente en vez de abrir una nueva. SIEMPRE incluí urlPattern con el dominio (ej: urlPattern="youtube.com", urlPattern="spotify.com"). Ejemplo: action="open_or_switch", url="https://www.youtube.com/results?search_query=...", urlPattern="youtube.com"
Cuando el usuario pregunte "que estoy escuchando", "que suena", "que cancion es", usa browser_media.
Cuando diga "reproducime", "dale play", "ponele pausa", "ponele play", "para el video", "para la musica", usa DIRECTAMENTE browser_command con action "media_control" y command "toggle" (o "play"/"pause"). NO llames a browser_media primero, NO verifiques si hay algo reproduciendose - SIMPLEMENTE envia el comando media_control. La extension se encarga de encontrar el video. Despues de enviar el comando, decile al usuario "Listo, le di play/pause".
LLAMADAS: Cuando el usuario diga "llamá a [contacto]", "llamale a [contacto]", "hacele una llamada a [contacto]":
1. Buscá el número del contacto en las memorias del usuario (usa remember_search)
2. Si encontras el número, usa whatsapp_call con el número (sin + y sin espacios, con código de país, ej: 5491112345678)
3. Si NO encontras el número, pedile al usuario que te lo diga y guardalo en memoria para la próxima vez
4. Para videollamada, usa call_type "video"
IMPORTANTE para kill_process: "Cloud" o "Cloud Code" = claude.exe (Claude Desktop), NO es ChatGPT. "ChatGPT" o "Chat GPT" = ChatGPT.exe.
Cuando el usuario diga "apaga la PC en 10 minutos", "bloquea la compu", "minimiza todo", usa la herramienta correspondiente.

RUTINAS:
Podes ejecutar rutinas predefinidas con run_routine. Rutinas disponibles:
- "buenos_dias": Saludo matutino + clima + noticias + tareas + abre Spotify con musica chill
- "buenas_noches": Cierra apps, baja volumen, muestra resumen del dia
- "modo_estudio": Abre material de estudio, activa timer pomodoro, silencia notificaciones
Cuando el usuario diga "buenos dias", "buen dia", "me levante" → ejecuta rutina buenos_dias
Cuando diga "buenas noches", "me voy a dormir", "chau jarvis" → ejecuta rutina buenas_noches
Cuando diga "voy a estudiar", "modo estudio" → ejecuta rutina modo_estudio

TRADUCCION:
Podes traducir texto a cualquier idioma. Si el usuario dice "traducime esto al ingles", traducilo vos directamente en tu respuesta. No necesitas herramienta para traducir.

VISION / ANALISIS DE PANTALLA:
Podes analizar lo que hay en pantalla con analyze_screen. Toma una captura, la envia a Claude con vision y te devuelve una descripcion. Usar cuando diga "que hay en mi pantalla", "que estoy viendo", "analizame la pantalla".

CALENDARIO GOOGLE:
Si el usuario configuro su Google Calendar (URL iCal), podes ver los eventos de hoy con get_calendar_events. Usar cuando pregunte "que tengo hoy", "tengo alguna reunion", "mi agenda".

WHATSAPP:
Podes enviar mensajes de WhatsApp con send_whatsapp. El mensaje se envia AUTOMATICAMENTE via la extension de Chrome (abre el chat en WhatsApp Web, escribe el mensaje y hace click en enviar solo). NO copies al portapapeles, NO le digas al usuario que pegue nada. Simplemente usa send_whatsapp y confirmale que se envio.
Para buscar contactos por nombre usa search_whatsapp_contacts. Para leer mensajes usa read_whatsapp.
REGLA: Cuando el usuario diga un NOMBRE, primero busca en TUS MEMORIAS (ya tenes numeros guardados ahi como "Papa = 5493625637199"). Si no esta en memorias, usa search_whatsapp_contacts. Si tampoco encuentra, pedile el numero y guardalo con save_memory.
Cuando diga "tengo mensajes?", "que me escribieron por whatsapp", usa read_whatsapp.

MEMORIA:
Tenes memoria persistente. Cuando el usuario te diga algo importante sobre si mismo, sus preferencias, su vida, sus estudios, o cualquier dato que debas recordar, usa la herramienta save_memory para guardarlo.
Categorias de memoria: "personal" (datos del usuario), "preferencias" (gustos y preferencias), "trabajo" (estudio/trabajo), "importante" (fechas, eventos, datos criticos), "otro".

CONTEXTO ACTUAL:
- Fecha y hora: {datetime}
- Conversaciones totales: {conv_count}
- Memorias almacenadas: {mem_count}

MEMORIAS DEL USUARIO:
{memories}

TAREAS PENDIENTES:
{tasks}
"""

TOOLS = [
    {
        "name": "save_memory",
        "description": "Guardar algo importante en la memoria persistente. Usar cuando el usuario diga algo sobre si mismo, sus gustos, datos importantes, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["personal", "preferencias", "trabajo", "importante", "otro"],
                    "description": "Categoria de la memoria"
                },
                "content": {
                    "type": "string",
                    "description": "El contenido a recordar"
                },
                "importance": {
                    "type": "integer",
                    "description": "Importancia del 1 al 10",
                    "default": 5
                }
            },
            "required": ["category", "content"]
        }
    },
    {
        "name": "create_task",
        "description": "Crear una tarea o recordatorio para el usuario",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Titulo de la tarea"
                },
                "description": {
                    "type": "string",
                    "description": "Descripcion detallada (opcional)"
                },
                "due_date": {
                    "type": "string",
                    "description": "Fecha limite en formato YYYY-MM-DD (opcional)"
                },
                "due_time": {
                    "type": "string",
                    "description": "Hora limite en formato HH:MM (opcional)"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "complete_task",
        "description": "Marcar una tarea como completada",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID de la tarea a completar"
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "search_memory",
        "description": "Buscar en la memoria algo especifico",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en las memorias"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "send_email",
        "description": "Enviar un email a traves de Gmail",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Email del destinatario"
                },
                "subject": {
                    "type": "string",
                    "description": "Asunto del email"
                },
                "body": {
                    "type": "string",
                    "description": "Contenido del email"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "read_emails",
        "description": "Leer los emails recientes del usuario. Si el usuario busca un email especifico y no aparece en los primeros resultados, volver a llamar con un count mayor (15 o 20).",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Cantidad de emails a leer (default 10, maximo 30)",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "open_website",
        "description": "Abrir un sitio web en Chrome. Usar para cualquier URL, busquedas en Google, videos de YouTube, WhatsApp Web, etc. IMPORTANTE: Cuando el usuario pida un canal de YouTube o un video especifico, SIEMPRE usar busqueda de YouTube (https://www.youtube.com/results?search_query=QUERY) en vez de intentar adivinar la URL directa del canal. Nunca inventar URLs de canales.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL a abrir. Para buscar canales o videos en YouTube: https://www.youtube.com/results?search_query=NOMBRE+DEL+CANAL (SIEMPRE usar busqueda, NUNCA adivinar URLs de canales). Para WhatsApp: https://web.whatsapp.com. Para buscar en Google: https://www.google.com/search?q=QUERY"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "open_app",
        "description": "Abrir una aplicacion en la computadora. Apps comunes: chrome, whatsapp, word, excel, powerpoint, spotify, calculadora, notepad, explorador, terminal, discord, steam, chatgpt, claude. Tambien descubre automaticamente TODAS las apps instaladas en Windows (Start Menu, Program Files, Steam). Simplemente pasa el nombre y se busca automaticamente. Para sitios web como YouTube, Netflix, Gmail usar open_website.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Nombre de la aplicacion"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "system_notify",
        "description": "Enviar una notificacion INMEDIATA de Windows al usuario. SOLO para notificaciones instantaneas. Para recordatorios futuros (ej: 'avisame a las 6') usar set_reminder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Titulo de la notificacion"
                },
                "message": {
                    "type": "string",
                    "description": "Mensaje de la notificacion"
                }
            },
            "required": ["title", "message"]
        }
    },
    {
        "name": "set_reminder",
        "description": "Programar un recordatorio para una hora/fecha futura. Cuando llegue la hora, se muestra una notificacion de Windows. USAR SIEMPRE cuando el usuario diga 'avisame a las...', 'recordame que...', 'a las X haceme acordar de...'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Mensaje del recordatorio (ej: 'Hora de estudiar', 'Llamar al abogado')"
                },
                "time": {
                    "type": "string",
                    "description": "Hora del recordatorio en formato HH:MM (24h) (ej: '18:00', '09:30')"
                },
                "date": {
                    "type": "string",
                    "description": "Fecha del recordatorio en formato YYYY-MM-DD. Si no se especifica, se asume hoy."
                }
            },
            "required": ["message", "time"]
        }
    },
    {
        "name": "search_files",
        "description": "Buscar archivos en la computadora del usuario por nombre. Busca en Desktop, Documents y Downloads. La busqueda matchea TODAS las palabras por separado (ej: buscar '7 politico' encuentra 'Unid. 7 Politico.pdf'). Probar con palabras clave cortas si no encuentra con el nombre completo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en nombres de archivos (ej: 'parcial', 'derecho penal', '.pdf')"
                },
                "folder": {
                    "type": "string",
                    "description": "Carpeta especifica donde buscar (opcional). Opciones: desktop, documents, downloads, all",
                    "default": "all"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_file",
        "description": "Leer el contenido de un archivo de texto (.txt, .md, .py, .csv, etc). No funciona con archivos binarios como .pdf o .docx.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta completa del archivo"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "open_file",
        "description": "Abrir un archivo con su programa predeterminado en la pantalla del usuario. Solo usar cuando el usuario diga 'abrime' o 'abrilo'. Si dice 'leeme' o 'resumime', usar read_pdf o read_file en su lugar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta completa del archivo a abrir"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_folder",
        "description": "Listar los archivos y carpetas dentro de un directorio",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta de la carpeta a listar. Usar ~ para el home del usuario."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Crear o sobrescribir un archivo con contenido. Usar para programar, crear scripts, escribir documentos, etc. CUIDADO: sobrescribe el archivo si existe.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta completa del archivo a crear/escribir"
                },
                "content": {
                    "type": "string",
                    "description": "Contenido completo del archivo"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_command",
        "description": "Ejecutar un comando en la terminal del sistema. Usar para: instalar paquetes (pip install), correr scripts (python script.py), compilar codigo, git, etc. El comando se ejecuta en el directorio home del usuario. MAXIMO 30 segundos de ejecucion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Comando a ejecutar (ej: 'python mi_script.py', 'pip install requests', 'dir', etc)"
                },
                "work_dir": {
                    "type": "string",
                    "description": "Directorio de trabajo (opcional, default: Desktop del usuario)"
                },
                "background": {
                    "type": "boolean",
                    "description": "Si es true, ejecuta el comando en segundo plano sin esperar que termine. USAR SIEMPRE para scripts con interfaz grafica (tkinter, PyQt, juegos, etc).",
                    "default": False
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "create_document",
        "description": "Crear un documento Word (.docx) con contenido formateado. Usar cuando el usuario pida un documento, trabajo, resumen, informe, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta completa del archivo .docx a crear (ej: C:/Users/PC/Desktop/mi_documento.docx)"
                },
                "title": {
                    "type": "string",
                    "description": "Titulo del documento (aparece como heading principal)"
                },
                "content": {
                    "type": "string",
                    "description": "Contenido del documento. Usar '\\n' para parrafos nuevos y '## ' al inicio de una linea para subtitulos."
                }
            },
            "required": ["path", "title", "content"]
        }
    },
    {
        "name": "read_pdf",
        "description": "Leer y extraer el TEXTO de un archivo PDF para poder resumirlo, analizarlo o responder preguntas sobre su contenido. USAR SIEMPRE cuando el usuario diga 'leeme', 'resumime', 'que dice', 'de que trata' un PDF. NO usar open_file para esto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta completa del archivo PDF"
                },
                "pages": {
                    "type": "string",
                    "description": "Paginas a leer (opcional). Ej: '1-5' para las primeras 5, '3' para solo la 3, 'all' para todas (default: primeras 10)",
                    "default": "1-10"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "web_search",
        "description": "Buscar informacion en internet. Usar cuando el usuario pregunte algo que no sabes, noticias actuales, datos especificos, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en internet"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Cantidad maxima de resultados (default 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_videos",
        "description": "Buscar videos en YouTube/internet. Usar cuando el usuario pida un video, quiera ver algo, o pida algo al azar de un canal o tema. Devuelve una lista de videos con URLs. Despues usar open_website para abrir el video elegido.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar (ej: 'Hablando Huevadas', 'tutorial python', 'musica para estudiar')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Cantidad de videos a traer (default 10)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "system_info",
        "description": "Obtener informacion del sistema: bateria, CPU, RAM, disco, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detail": {
                    "type": "string",
                    "enum": ["all", "battery", "cpu", "ram", "disk"],
                    "description": "Que info mostrar (default: all)",
                    "default": "all"
                }
            }
        }
    },
    {
        "name": "play_youtube",
        "description": "Buscar y ABRIR un video de YouTube automaticamente. Busca videos, elige uno al azar de los mejores resultados, y lo abre en Chrome. USAR SIEMPRE que el usuario pida ver un video, escuchar musica de YouTube, o pida un video al azar de un canal o tema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Que buscar en YouTube (ej: 'Emilia Mernes', 'Hablando Huevadas ultimo video', 'lo fi hip hop para estudiar')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "play_spotify",
        "description": "Abrir una cancion o artista en Spotify automaticamente. Abre Spotify con la busqueda directa. USAR SIEMPRE que el usuario pida musica en Spotify. Si pide algo al azar, VOS elegis una cancion del artista y la pasas como query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Cancion y/o artista a buscar en Spotify (ej: 'Ella Baila Sola Emilia Mernes', 'Bad Bunny Monaco', 'Bohemian Rhapsody Queen')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": "Obtener el clima actual. Usar cuando pregunten por clima, temperatura, si llueve, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Ciudad (default: ciudad del usuario)", "default": "Buenos Aires"}
            }
        }
    },
    {
        "name": "get_news",
        "description": "Obtener noticias recientes de Argentina o del mundo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tema (ej: 'argentina', 'tecnologia', 'deportes')", "default": "argentina"}
            }
        }
    },
    {
        "name": "clipboard_read",
        "description": "Leer el contenido del portapapeles. Usar cuando diga 'que tengo copiado', 'leeme lo que copie', 'que hay en el portapapeles'.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "clipboard_write",
        "description": "Copiar texto al portapapeles. Usar cuando diga 'copiame esto', 'mandalo al portapapeles'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto a copiar"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Tomar captura de pantalla y guardarla en el escritorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Nombre del archivo (sin extension)", "default": "screenshot"}
            }
        }
    },
    {
        "name": "read_webpage",
        "description": "Leer el contenido de una pagina web para resumirlo o analizarlo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL de la pagina"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "control_volume",
        "description": "Controlar el volumen del sistema: subir, bajar, silenciar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["up", "down", "mute", "unmute", "set"], "description": "up/down/mute/unmute/set"},
                "level": {"type": "integer", "description": "Nivel 0-100 (solo para 'set')"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "control_brightness",
        "description": "Controlar el brillo de la pantalla (solo notebooks).",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Nivel de brillo 0-100"}
            },
            "required": ["level"]
        }
    },
    {
        "name": "pc_lock",
        "description": "Bloquear la PC (pantalla de bloqueo de Windows).",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "pc_shutdown",
        "description": "Apagar la PC. Se puede programar con delay en segundos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "delay": {"type": "integer", "description": "Segundos antes de apagar (0 = inmediato, 600 = 10 min)", "default": 0},
                "cancel": {"type": "boolean", "description": "true para cancelar un apagado programado", "default": False}
            }
        }
    },
    {
        "name": "pc_restart",
        "description": "Reiniciar la PC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "delay": {"type": "integer", "description": "Segundos antes de reiniciar (0 = inmediato)", "default": 0}
            }
        }
    },
    {
        "name": "kill_process",
        "description": "Cerrar/matar un proceso por nombre (ej: chrome, discord, spotify).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del proceso (ej: chrome, discord, spotify, steam)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "close_all_apps",
        "description": "Cerrar TODAS las aplicaciones abiertas (excepto Chrome donde corre JARVIS). Usar cuando el usuario dice 'cerra todo', 'cerrar todo lo que tengo abierto', etc.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "minimize_all",
        "description": "Minimizar todas las ventanas (mostrar escritorio).",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "run_routine",
        "description": "Ejecutar una rutina predefinida. buenos_dias: saludo+clima+noticias+tareas+musica. buenas_noches: cierra apps+baja volumen+resumen. modo_estudio: timer pomodoro+silencio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "routine": {"type": "string", "enum": ["buenos_dias", "buenas_noches", "modo_estudio"], "description": "Nombre de la rutina"}
            },
            "required": ["routine"]
        }
    },
    {
        "name": "analyze_screen",
        "description": "Tomar captura de pantalla y analizarla con vision AI. Devuelve descripcion de lo que se ve en pantalla.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Pregunta especifica sobre la pantalla (opcional)", "default": "Describe lo que ves en la pantalla"}
            }
        }
    },
    {
        "name": "get_calendar_events",
        "description": "Obtener eventos del calendario de Google para hoy. El usuario debe haber configurado su URL iCal.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "send_whatsapp",
        "description": "Enviar un mensaje de WhatsApp automaticamente. La extension de Chrome abre el chat, escribe el mensaje y lo envia solo. NO copiar al portapapeles. Busca el numero en memorias primero, o usa search_whatsapp_contacts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Numero de telefono con codigo de pais sin + ni espacios (ej: 5493624163439)"},
                "message": {"type": "string", "description": "Texto del mensaje a enviar"}
            },
            "required": ["phone", "message"]
        }
    },
    {
        "name": "search_whatsapp_contacts",
        "description": "Buscar un contacto de WhatsApp por nombre. Devuelve el nombre y numero de telefono. USAR SIEMPRE antes de send_whatsapp cuando el usuario dice un nombre en vez de un numero.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre o parte del nombre del contacto a buscar"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "read_whatsapp",
        "description": "Leer mensajes de WhatsApp Web via la extension de Chrome. Muestra chats con mensajes sin leer y los mensajes del chat abierto. Necesita WhatsApp Web abierto en Chrome.",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Cantidad de notificaciones a leer (default: 5)"}
            }
        }
    },
    {
        "name": "analyze_text",
        "description": "Analizar un texto largo de forma profesional. Genera resumen ejecutivo, puntos clave, conceptos importantes, terminos tecnicos y conclusion. USAR cuando el usuario pegue un texto largo o pida analizar/resumir un texto. Tambien cuando el mensaje del usuario tenga mas de 300 caracteres y parezca texto academico o legal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "El texto completo a analizar"},
                "focus": {"type": "string", "description": "Enfoque del analisis: 'general', 'legal', 'academico', 'cientifico', 'noticioso'. Default: 'general'"},
                "language": {"type": "string", "description": "Idioma de respuesta. Default: 'es' (español)"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "generate_image",
        "description": "Generar una imagen a partir de una descripcion de texto. La descripcion DEBE ser en ingles para mejores resultados. Si el usuario habla en español, traduci la descripcion a ingles antes de usar esta herramienta. USAR cuando el usuario pida crear, generar, dibujar o hacer una imagen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Descripcion de la imagen a generar EN INGLES (ej: 'a futuristic city at sunset with flying cars')"},
                "width": {"type": "integer", "description": "Ancho en pixeles (default: 1024)"},
                "height": {"type": "integer", "description": "Alto en pixeles (default: 1024)"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "whatsapp_call",
        "description": "Hacer una llamada de WhatsApp a un contacto. Abre WhatsApp Web y hace click automaticamente en el boton de llamar. Necesitas el numero de telefono con codigo de pais (ej: 5491112345678). Si no tenes el numero, buscalo en las memorias del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Numero de telefono con codigo de pais sin + ni espacios (ej: 5491112345678)"},
                "contact_name": {"type": "string", "description": "Nombre del contacto (para confirmar)"},
                "call_type": {"type": "string", "enum": ["audio", "video"], "description": "Tipo de llamada", "default": "audio"}
            },
            "required": ["phone"]
        }
    },
    {
        "name": "send_discord",
        "description": "Enviar un mensaje a un canal de Discord via bot. Requiere que el bot de Discord este configurado. USAR cuando el usuario pida enviar algo a Discord.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "ID del canal de Discord. Si no se sabe, usar list_discord_channels para obtenerlo."},
                "message": {"type": "string", "description": "Texto del mensaje a enviar"}
            },
            "required": ["channel_id", "message"]
        }
    },
    {
        "name": "read_discord",
        "description": "Leer los ultimos mensajes de un canal de Discord. Requiere bot configurado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "ID del canal de Discord"},
                "count": {"type": "integer", "description": "Cantidad de mensajes a leer (default: 10)"}
            },
            "required": ["channel_id"]
        }
    },
    {
        "name": "list_discord_channels",
        "description": "Listar los servidores y canales de Discord disponibles para el bot. USAR SIEMPRE antes de send_discord o read_discord si no se conoce el channel_id.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "send_telegram",
        "description": "Enviar un mensaje/notificacion al usuario via Telegram. Usar para avisar cosas cuando el usuario no esta en la PC (recordatorios, alertas, confirmaciones). El mensaje le llega al celular.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto del mensaje a enviar"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "create_presentation",
        "description": "Crear una presentacion PowerPoint (.pptx). El usuario puede pedir 'haceme una presentacion sobre X', 'arma un powerpoint de Y'. Genera slides con titulo y contenido. El archivo se descarga automaticamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titulo de la presentacion"},
                "slides": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Titulo del slide"},
                            "content": {"type": "string", "description": "Contenido del slide, cada linea separada por \\n"}
                        },
                        "required": ["title", "content"]
                    },
                    "description": "Lista de slides con titulo y contenido"
                }
            },
            "required": ["title", "slides"]
        }
    },
    {
        "name": "browser_tabs",
        "description": "Ver las pestañas abiertas en Chrome del usuario. USAR SIEMPRE antes de abrir un sitio web para ver si ya esta abierto. Devuelve lista de pestañas con URL, titulo y si tiene audio.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "browser_media",
        "description": "Ver que musica/video esta reproduciendo el usuario en el browser. Devuelve titulo, artista, sitio (YouTube/Spotify), si esta en play o pausa, y tiempo actual. USAR cuando pregunte 'que estoy escuchando', 'que suena', 'que cancion es esta'.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "browser_command",
        "description": "Enviar comando al browser del usuario via extension Chrome. Acciones: 'open_or_switch' (abre URL en pestaña existente o nueva), 'navigate_tab' (navega pestaña existente a nueva URL), 'switch_tab' (cambia a pestaña), 'media_control' (play/pause/toggle), 'close_tab' (cierra pestaña).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["open_or_switch", "navigate_tab", "switch_tab", "media_control", "close_tab"], "description": "Tipo de comando"},
                "url": {"type": "string", "description": "URL a abrir (para open_or_switch y navigate_tab)"},
                "urlPattern": {"type": "string", "description": "Patron para encontrar pestaña existente (ej: 'youtube.com', 'spotify.com')"},
                "command": {"type": "string", "enum": ["play", "pause", "toggle"], "description": "Comando de media (para media_control)"},
                "tabId": {"type": "integer", "description": "ID de pestaña especifica (opcional)"}
            },
            "required": ["action"]
        }
    }
]


def build_system_prompt():
    now = datetime.now().strftime("%A %d de %B de %Y, %H:%M")
    conv_count = mem.get_conversation_count()
    memories = mem.get_memories(limit=30)
    tasks = mem.get_tasks(status="pending")

    mem_text = ""
    if memories:
        for m in memories:
            mem_text += f"- [{m['category']}] {m['content']}\n"
    else:
        mem_text = "No hay memorias guardadas aun."

    tasks_text = ""
    if tasks:
        for t in tasks:
            due = ""
            if t['due_date']:
                due = f" (fecha: {t['due_date']}"
                if t['due_time']:
                    due += f" {t['due_time']}"
                due += ")"
            tasks_text += f"- [#{t['id']}] {t['title']}{due}\n"
    else:
        tasks_text = "No hay tareas pendientes."

    return SYSTEM_PROMPT.format(
        datetime=now,
        conv_count=conv_count,
        mem_count=len(memories),
        memories=mem_text,
        tasks=tasks_text
    )


def process_tool_call(tool_name, tool_input):
    _log(f"[TOOL] {tool_name}: {tool_input}")
    try:
        return _process_tool_call_inner(tool_name, tool_input)
    except Exception as e:
        _log(f"[TOOL ERROR] {tool_name}: {e}")
        return f"Error ejecutando {tool_name}: {e}"


def _process_tool_call_inner(tool_name, tool_input):
    if tool_name == "save_memory":
        mem.save_memory(
            category=tool_input["category"],
            content=tool_input["content"],
            importance=tool_input.get("importance", 5)
        )
        return "Memoria guardada exitosamente."

    elif tool_name == "create_task":
        task_id = mem.create_task(
            title=tool_input["title"],
            description=tool_input.get("description", ""),
            due_date=tool_input.get("due_date"),
            due_time=tool_input.get("due_time")
        )
        return f"Tarea #{task_id} creada: {tool_input['title']}"

    elif tool_name == "complete_task":
        mem.complete_task(tool_input["task_id"])
        return f"Tarea #{tool_input['task_id']} completada."

    elif tool_name == "search_memory":
        results = mem.search_memories(tool_input["query"])
        if results:
            text = "Memorias encontradas:\n"
            for r in results:
                text += f"- [{r['category']}] {r['content']}\n"
            return text
        return "No encontre nada relacionado en mi memoria."

    elif tool_name == "send_email":
        import gmail_integration as gmail
        result = gmail.send_email(tool_input["to"], tool_input["subject"], tool_input["body"])
        if "error" in result:
            return f"Error enviando email: {result['error']}"
        return f"Email enviado a {tool_input['to']} con asunto: {tool_input['subject']}"

    elif tool_name == "read_emails":
        import gmail_integration as gmail
        result = gmail.read_emails(tool_input.get("count", 5))
        if "error" in result:
            return result["error"]
        emails = result.get("emails", [])
        if not emails:
            return "No hay emails recientes."
        text = f"Ultimos {len(emails)} emails:\n"
        for e in emails:
            text += f"\nDe: {e['from']}\nAsunto: {e['subject']}\nFecha: {e['date']}\nResumen: {e['snippet'][:150]}\n---"
        return text

    elif tool_name == "open_website":
        url = tool_input["url"]
        media_domains = ["youtube.com", "spotify.com", "twitch.tv", "netflix.com"]
        domain_match = next((d for d in media_domains if d in url), None)
        if domain_match:
            _browser_command({"action": "open_or_switch", "url": url, "urlPattern": domain_match})
            return json.dumps({"info": f"Abriendo {url}"})
        return json.dumps({"action": "open_website", "url": url})

    elif tool_name == "open_app":
        return json.dumps({"action": "open_app", "app_name": tool_input["app_name"]})

    elif tool_name == "system_notify":
        return json.dumps({"action": "system_notify", **tool_input})

    elif tool_name == "set_reminder":
        return _set_reminder(tool_input["message"], tool_input["time"], tool_input.get("date"))

    elif tool_name == "search_files":
        return _search_files(tool_input["query"], tool_input.get("folder", "all"))

    elif tool_name == "read_file":
        return _read_file(tool_input["path"])

    elif tool_name == "open_file":
        return json.dumps({"action": "open_file", "path": tool_input["path"]})

    elif tool_name == "list_folder":
        return _list_folder(tool_input["path"])

    elif tool_name == "write_file":
        return _write_file(tool_input["path"], tool_input["content"])

    elif tool_name == "run_command":
        return _run_command(tool_input["command"], tool_input.get("work_dir"), tool_input.get("background", False))

    elif tool_name == "create_document":
        return _create_document(tool_input["path"], tool_input["title"], tool_input["content"])

    elif tool_name == "read_pdf":
        return _read_pdf(tool_input["path"], tool_input.get("pages", "1-10"))

    elif tool_name == "web_search":
        return _web_search(tool_input["query"], tool_input.get("max_results", 5))

    elif tool_name == "search_videos":
        return _search_videos(tool_input["query"], tool_input.get("max_results", 10))

    elif tool_name == "system_info":
        return _system_info(tool_input.get("detail", "all"))

    elif tool_name == "play_youtube":
        return _play_youtube(tool_input["query"])

    elif tool_name == "play_spotify":
        return _play_spotify(tool_input["query"])

    elif tool_name == "get_weather":
        return _get_weather(tool_input.get("city", "Buenos Aires"))

    elif tool_name == "get_news":
        return _get_news(tool_input.get("topic", "argentina"))

    elif tool_name == "clipboard_read":
        return _clipboard_read()

    elif tool_name == "clipboard_write":
        return _clipboard_write(tool_input["text"])

    elif tool_name == "take_screenshot":
        return _take_screenshot(tool_input.get("filename", "screenshot"))

    elif tool_name == "send_whatsapp":
        return _send_whatsapp(tool_input["phone"], tool_input["message"])

    elif tool_name == "read_webpage":
        return _read_webpage(tool_input["url"])

    elif tool_name == "control_volume":
        return _control_volume(tool_input["action"], tool_input.get("level"))

    elif tool_name == "control_brightness":
        return _control_brightness(tool_input["level"])

    elif tool_name == "pc_lock":
        return _pc_lock()

    elif tool_name == "pc_shutdown":
        return _pc_shutdown(tool_input.get("delay", 0), tool_input.get("cancel", False))

    elif tool_name == "pc_restart":
        return _pc_restart(tool_input.get("delay", 0))

    elif tool_name == "kill_process":
        return _kill_process(tool_input["name"])

    elif tool_name == "close_all_apps":
        return _close_all_apps()

    elif tool_name == "minimize_all":
        return _minimize_all()

    elif tool_name == "run_routine":
        return _run_routine(tool_input["routine"])

    elif tool_name == "analyze_screen":
        return _analyze_screen(tool_input.get("question", "Describe lo que ves en la pantalla"))

    elif tool_name == "get_calendar_events":
        return _get_calendar_events()

    elif tool_name == "search_whatsapp_contacts":
        return _search_whatsapp_contacts(tool_input["name"])

    elif tool_name == "read_whatsapp":
        return _read_whatsapp(tool_input.get("count", 5))

    elif tool_name == "analyze_text":
        return _analyze_text(tool_input["text"], tool_input.get("focus", "general"), tool_input.get("language", "es"))

    elif tool_name == "generate_image":
        return _generate_image(tool_input["prompt"], tool_input.get("width", 1024), tool_input.get("height", 1024))

    elif tool_name == "whatsapp_call":
        return _whatsapp_call(tool_input)

    elif tool_name == "send_discord":
        return _send_discord(tool_input["channel_id"], tool_input["message"])

    elif tool_name == "read_discord":
        return _read_discord(tool_input["channel_id"], tool_input.get("count", 10))

    elif tool_name == "list_discord_channels":
        return _list_discord_channels()

    elif tool_name == "send_telegram":
        return _send_telegram(tool_input["text"])

    elif tool_name == "create_presentation":
        return _create_presentation(tool_input.get("title", "Presentación"), tool_input.get("slides", []))

    elif tool_name == "browser_tabs":
        return _browser_tabs()

    elif tool_name == "browser_media":
        return _browser_media()

    elif tool_name == "browser_command":
        _log(f"[BRAIN] browser_command llamado con: {tool_input}")
        result = _browser_command(tool_input)
        _log(f"[BRAIN] browser_command resultado: {result}")
        return result

    return "Herramienta no reconocida."


def _search_files(query, folder="all"):
    home = os.path.expanduser("~")
    search_dirs = {
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
    }
    if folder != "all" and folder in search_dirs:
        dirs = {folder: search_dirs[folder]}
    else:
        dirs = search_dirs

    import unicodedata

    def strip_accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    words = strip_accents(query.lower()).split()
    stop_words = {"de", "del", "la", "el", "los", "las", "en", "un", "una", "que", "por", "para", "con", "mi", "mis", "su", "sus"}
    words = [w for w in words if w not in stop_words and (len(w) > 1 or w.isdigit())]

    def score(filename, words):
        f = strip_accents(filename.lower())
        hits = 0
        for w in words:
            if w in f or w[:3] in f:
                hits += 1
        return hits

    scored = []
    for name, path in dirs.items():
        if not os.path.exists(path):
            continue
        for root, dirnames, files in os.walk(path):
            depth = root.replace(path, '').count(os.sep)
            if depth > 3:
                continue
            for f in files:
                s = score(f, words)
                if s >= max(1, len(words) // 2):
                    full = os.path.join(root, f)
                    size = os.path.getsize(full)
                    size_str = f"{size // 1024}KB" if size > 1024 else f"{size}B"
                    scored.append((s, f"{full} ({size_str})"))
            if len(scored) >= 30:
                break

    scored.sort(key=lambda x: -x[0])
    results = [item for _, item in scored[:20]]

    if results:
        return f"Encontre {len(results)} archivo(s):\n" + "\n".join(results[:20])
    return f"No encontre archivos con '{query}' en {folder}."


def _read_file(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"El archivo no existe: {path}"
    if not os.path.isfile(path):
        return "Eso es una carpeta, no un archivo."
    size = os.path.getsize(path)
    if size > 100000:
        return f"El archivo es muy grande ({size // 1024}KB). Solo puedo leer archivos de hasta 100KB."
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return f"Contenido de {os.path.basename(path)}:\n{content[:5000]}"
    except Exception as e:
        return f"No pude leer el archivo: {e}"


def _list_folder(path):
    path = os.path.expanduser(path).replace("~", os.path.expanduser("~"))
    if not os.path.exists(path):
        return f"La carpeta no existe: {path}"
    if not os.path.isdir(path):
        return "Eso es un archivo, no una carpeta."
    try:
        items = os.listdir(path)
        folders = []
        files = []
        for item in sorted(items):
            full = os.path.join(path, item)
            if os.path.isdir(full):
                folders.append(f"[carpeta] {item}")
            else:
                size = os.path.getsize(full)
                size_str = f"{size // 1024}KB" if size > 1024 else f"{size}B"
                files.append(f"{item} ({size_str})")
        result = f"Contenido de {path}:\n"
        for f in folders[:30]:
            result += f + "\n"
        for f in files[:30]:
            result += f + "\n"
        if len(items) > 60:
            result += f"... y {len(items) - 60} mas"
        return result
    except Exception as e:
        return f"No pude listar la carpeta: {e}"


def _set_reminder(message, time_str, date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        reminder_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "Formato invalido. Usa hora HH:MM y fecha YYYY-MM-DD."

    if reminder_dt <= datetime.now():
        return f"Esa hora ya paso ({time_str}). Decime una hora futura."

    mem.create_task(
        title=f"RECORDATORIO: {message}",
        due_date=date_str,
        due_time=time_str
    )
    hora = reminder_dt.strftime("%H:%M")
    fecha = reminder_dt.strftime("%d/%m/%Y")
    return f"Recordatorio programado para las {hora} del {fecha}: '{message}'. Te va a llegar una notificacion de Windows."


def _write_file(path, content):
    path = os.path.expanduser(path)
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(path)
        return f"Archivo creado: {path} ({size} bytes)"
    except Exception as e:
        return f"Error escribiendo archivo: {e}"


def _run_command(command, work_dir=None, background=False):
    import subprocess
    if not work_dir:
        work_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    work_dir = os.path.expanduser(work_dir)

    blocked = ["format", "del /s", "rmdir /s", "rd /s"]
    cmd_lower = command.lower().strip()
    for b in blocked:
        if cmd_lower.startswith(b):
            return f"Comando bloqueado por seguridad: {b}"

    try:
        if background:
            subprocess.Popen(
                command,
                shell=True,
                cwd=work_dir,
            )
            return f"Comando lanzado en segundo plano: {command}"

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=work_dir,
            encoding="utf-8",
            errors="replace"
        )
        output = ""
        if result.stdout:
            output += result.stdout[:3000]
        if result.stderr:
            output += "\nSTDERR: " + result.stderr[:1000]
        if result.returncode != 0:
            output += f"\n(exit code: {result.returncode})"
        return output.strip() if output.strip() else "(comando ejecutado sin output)"
    except subprocess.TimeoutExpired:
        return "El comando tardo mas de 30 segundos y fue cancelado."
    except Exception as e:
        return f"Error ejecutando comando: {e}"


def _create_document(path, title, content):
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError:
        return "Error: python-docx no esta instalado. Ejecuta: pip install python-docx"

    path = os.path.expanduser(path)
    if not path.endswith(".docx"):
        path += ".docx"

    try:
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        doc = Document()
        doc.add_heading(title, level=0)

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("## "):
                doc.add_heading(line[3:], level=2)
            elif line.startswith("# "):
                doc.add_heading(line[2:], level=1)
            elif line.startswith("- "):
                doc.add_paragraph(line[2:], style="List Bullet")
            else:
                doc.add_paragraph(line)

        doc.save(path)
        return f"Documento creado: {path}"
    except Exception as e:
        return f"Error creando documento: {e}"


def _read_pdf(path, pages="1-10"):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"El archivo no existe: {path}"
    if not path.lower().endswith(".pdf"):
        return "Eso no es un PDF."
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        total = len(reader.pages)

        if pages == "all":
            start, end = 0, total
        elif "-" in pages:
            parts = pages.split("-")
            start = max(0, int(parts[0]) - 1)
            end = min(total, int(parts[1]))
        else:
            start = max(0, int(pages) - 1)
            end = start + 1

        text = ""
        for i in range(start, min(end, total)):
            page_text = reader.pages[i].extract_text() or ""
            text += f"\n--- Pagina {i+1} ---\n{page_text}"

        if not text.strip():
            return f"El PDF tiene {total} paginas pero no se pudo extraer texto (puede ser escaneado/imagen)."

        text = text[:8000]
        return f"PDF: {os.path.basename(path)} ({total} paginas). Mostrando paginas {start+1}-{min(end, total)}:\n{text}"
    except Exception as e:
        return f"Error leyendo PDF: {e}"


def _web_search(query, max_results=5):
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        if results:
            text = f"Resultados de busqueda para '{query}':\n"
            for r in results:
                text += f"\n- {r['title']}\n  {r['body'][:200]}\n  URL: {r['href']}\n"
            return text
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if results:
                text = f"Resultados de busqueda para '{query}':\n"
                for r in results:
                    text += f"\n- {r['title']}\n  {r['body'][:200]}\n  URL: {r['href']}\n"
                return text
        except Exception:
            pass
    except Exception as e:
        _log(f"[SEARCH] Error: {e}")

    return f"No encontre resultados para: {query}"


def _search_videos(query, max_results=10):
    results = []
    try:
        from ddgs import DDGS
        results = list(DDGS().videos(query, max_results=max_results))
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.videos(query, max_results=max_results))
        except Exception as e:
            _log(f"[SEARCH] Video search fallback error: {e}")
    except Exception as e:
        _log(f"[SEARCH] Video search error: {e}")
    if not results:
        return f"No encontre videos para: {query}. Podes intentar con play_youtube para buscar y reproducir directamente."
    text = f"Encontre {len(results)} videos:\n"
    for i, r in enumerate(results, 1):
        title = r.get("title", "Sin titulo")
        url = r.get("content", r.get("embed_url", ""))
        publisher = r.get("publisher", "")
        duration = r.get("duration", "")
        text += f"\n{i}. {title}"
        if publisher:
            text += f" [{publisher}]"
        if duration:
            text += f" ({duration})"
        if url:
            text += f"\n   URL: {url}"
        text += "\n"
    return text


def _system_info(detail="all"):
    import psutil
    info = ""
    if detail in ("all", "battery"):
        bat = psutil.sensors_battery()
        if bat:
            info += f"Bateria: {bat.percent}% {'(Cargando)' if bat.power_plugged else '(Desenchufado)'}\n"
        else:
            info += "Bateria: No disponible (PC de escritorio)\n"
    if detail in ("all", "cpu"):
        info += f"CPU: {psutil.cpu_percent(interval=1)}% uso\n"
        info += f"Nucleos: {psutil.cpu_count()}\n"
    if detail in ("all", "ram"):
        ram = psutil.virtual_memory()
        info += f"RAM: {ram.percent}% usado ({ram.used // (1024**3)}GB de {ram.total // (1024**3)}GB)\n"
    if detail in ("all", "disk"):
        disk = psutil.disk_usage("C:\\")
        info += f"Disco C: {disk.percent}% usado ({disk.used // (1024**3)}GB de {disk.total // (1024**3)}GB)\n"
    return info.strip() if info else "No se pudo obtener info del sistema."


def _get_weather(city="Buenos Aires"):
    import urllib.request
    from urllib.parse import quote
    try:
        url = f"https://wttr.in/{quote(city)}?format=%C+%t+Sensacion:+%f+Humedad:+%h+Viento:+%w&lang=es"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            detail = resp.read().decode("utf-8").strip()
        url2 = f"https://wttr.in/{quote(city)}?format=Manana:+%C+%t+/+Pasado:+%C+%t&lang=es&1"
        req2 = urllib.request.Request(url2, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            forecast = resp2.read().decode("utf-8").strip()
        return f"Clima en {city}: {detail}\nPronostico: {forecast}"
    except Exception as e:
        return f"Error obteniendo clima: {e}"


def _get_news(topic="argentina"):
    try:
        from ddgs import DDGS
        results = list(DDGS().news(f"{topic}", max_results=5))
        if results:
            text = f"Noticias sobre {topic}:\n"
            for r in results:
                text += f"\n- {r['title']}\n  {r.get('body', '')[:150]}\n  Fuente: {r.get('source', '')}\n"
            return text
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.news(f"{topic}", max_results=5))
            if results:
                text = f"Noticias sobre {topic}:\n"
                for r in results:
                    text += f"\n- {r['title']}\n  {r.get('body', '')[:150]}\n  Fuente: {r.get('source', '')}\n"
                return text
        except Exception:
            pass
    except Exception as e:
        _log(f"[NEWS] Error: {e}")

    return "No encontre noticias recientes."


def _clipboard_read():
    import subprocess
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5, encoding="utf-8"
        )
        content = result.stdout.strip()
        if content:
            return f"Contenido del portapapeles:\n{content[:3000]}"
        return "El portapapeles esta vacio."
    except Exception as e:
        return f"Error: {e}"


def _clipboard_write(text):
    import subprocess
    try:
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
            stdin=subprocess.PIPE, text=True, encoding="utf-8"
        )
        process.communicate(input=text, timeout=5)
        return "Texto copiado al portapapeles."
    except Exception as e:
        return f"Error: {e}"


def _take_screenshot(filename="screenshot"):
    try:
        import mss
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(os.path.expanduser("~"), "Desktop", f"{filename}_{timestamp}.png")
        with mss.mss() as sct:
            sct.shot(output=path)
        return f"Captura guardada: {path}"
    except ImportError:
        return "Error: mss no instalado. Ejecuta: pip install mss"
    except Exception as e:
        return f"Error: {e}"


def _read_webpage(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return f"Contenido de {url}:\n{text[:5000]}"
    except Exception as e:
        return f"Error leyendo pagina: {e}"


def _control_volume(action, level=None):
    import ctypes
    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF
    KEYEVENTF_KEYUP = 0x0002

    def press(vk):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    try:
        if action in ("mute", "unmute"):
            press(VK_VOLUME_MUTE)
            return "Volumen silenciado." if action == "mute" else "Sonido activado."
        elif action == "up":
            for _ in range(5):
                press(VK_VOLUME_UP)
            return "Volumen subido."
        elif action == "down":
            for _ in range(5):
                press(VK_VOLUME_DOWN)
            return "Volumen bajado."
        elif action == "set" and level is not None:
            for _ in range(50):
                press(VK_VOLUME_DOWN)
            for _ in range(level // 2):
                press(VK_VOLUME_UP)
            return f"Volumen en {level}%."
    except Exception as e:
        return f"Error: {e}"
    return "Accion no reconocida."


def _control_brightness(level):
    import subprocess
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"],
            capture_output=True, timeout=5
        )
        return f"Brillo en {level}%."
    except Exception as e:
        return f"Error (solo funciona en notebooks): {e}"


def _pc_lock():
    import ctypes
    try:
        ctypes.windll.user32.LockWorkStation()
        return "PC bloqueada, señor."
    except Exception as e:
        return f"Error bloqueando: {e}"


def _pc_shutdown(delay=0, cancel=False):
    import subprocess
    try:
        if cancel:
            subprocess.run(["shutdown", "/a"], capture_output=True)
            return "Apagado cancelado."
        _close_all_apps()
        if delay == 0:
            delay = 5
        subprocess.Popen(["shutdown", "/s", "/t", str(delay)])
        if delay > 5:
            mins = delay // 60
            return f"Cerre todas las apps. PC se apagara en {mins} minutos. Diga 'cancela el apagado' para cancelar."
        return "Cerre todas las apps. Apagando PC en 5 segundos..."
    except Exception as e:
        return f"Error: {e}"


def _pc_restart(delay=0):
    import subprocess
    try:
        _close_all_apps()
        if delay == 0:
            delay = 5
        subprocess.Popen(["shutdown", "/r", "/t", str(delay)])
        if delay > 5:
            return f"Cerre todas las apps. PC se reiniciara en {delay // 60} minutos."
        return "Cerre todas las apps. Reiniciando PC en 5 segundos..."
    except Exception as e:
        return f"Error: {e}"


def _kill_process(name):
    import subprocess
    name = name.lower().strip()
    process_map = {
        "chrome": "chrome.exe", "google chrome": "chrome.exe",
        "discord": "Discord.exe", "spotify": "Spotify.exe",
        "steam": "steam.exe", "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE",
        "notepad": "notepad.exe", "explorer": "explorer.exe",
        "edge": "msedge.exe", "firefox": "firefox.exe",
        "claude": "claude.exe", "claude code": "claude.exe",
        "cloud code": "claude.exe", "cloud": "claude.exe",
        "claude ai": "claude.exe", "claude desktop": "claude.exe",
        "chatgpt": "ChatGPT.exe", "chat gpt": "ChatGPT.exe",
    }
    protected = {"chrome.exe", "msedge.exe", "explorer.exe"}
    exe = process_map.get(name, f"{name}.exe")
    if exe.lower() in protected:
        if exe.lower() == "explorer.exe":
            return f"No puedo cerrar Explorer porque es la barra de tareas y el escritorio de Windows. Se romperia todo."
        return f"No puedo cerrar {name} porque JARVIS corre dentro del navegador. Si queres cerrar una pestaña especifica, decime cual sitio y te lo cierro desde el navegador."
    try:
        result = subprocess.run(
            ["taskkill", "/IM", exe, "/F"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return f"{name.capitalize()} cerrado."
        return f"No encontre {name} ejecutandose."
    except Exception as e:
        return f"Error: {e}"


def _close_all_apps():
    import subprocess
    protected = {"chrome.exe", "msedge.exe", "explorer.exe", "python.exe", "pythonw.exe", "cmd.exe", "powershell.exe", "conhost.exe", "svchost.exe", "System", "csrss.exe", "dwm.exe", "taskhostw.exe", "sihost.exe", "fontdrvhost.exe", "lsass.exe", "services.exe", "smss.exe", "wininit.exe", "winlogon.exe"}
    apps_to_kill = {
        "Discord": "Discord.exe",
        "Spotify": "Spotify.exe",
        "Steam": "steam.exe",
        "Word": "WINWORD.EXE",
        "Excel": "EXCEL.EXE",
        "PowerPoint": "POWERPNT.EXE",
        "Notepad": "notepad.exe",
        "Firefox": "firefox.exe",
        "Claude": "claude.exe",
        "ChatGPT": "ChatGPT.exe",
        "VLC": "vlc.exe",
        "Telegram": "Telegram.exe",
        "Teams": "Teams.exe",
        "Zoom": "Zoom.exe",
        "OBS": "obs64.exe",
        "VS Code": "Code.exe",
        "Acrobat": "Acrobat.exe",
        "Brave": "brave.exe",
        "Opera": "opera.exe",
        "Thunderbird": "thunderbird.exe",
    }
    closed = []
    not_running = []
    for app_name, exe in apps_to_kill.items():
        try:
            result = subprocess.run(
                ["taskkill", "/IM", exe, "/F"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if result.returncode == 0:
                closed.append(app_name)
        except Exception:
            pass
    if closed:
        return f"Cerré: {', '.join(closed)}. Chrome sigue abierto porque JARVIS corre ahí."
    return "No había ninguna aplicación abierta (aparte de Chrome donde corro yo)."


def _minimize_all():
    import ctypes
    try:
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)  # Win key down
        ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)  # D key down
        ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)  # D key up
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)  # Win key up
        return "Todas las ventanas minimizadas."
    except Exception as e:
        return f"Error: {e}"


def _run_routine(routine):
    results = []
    if routine == "buenos_dias":
        results.append(_get_weather())
        results.append(_get_news("argentina"))
        tasks = mem.get_tasks(status="pending")
        if tasks:
            task_text = f"{len(tasks)} tareas pendientes: " + ", ".join(t['title'] for t in tasks[:5])
            results.append(task_text)
        else:
            results.append("No hay tareas pendientes.")
        spotify_action = json.dumps({"action": "open_website", "url": "https://open.spotify.com/search/musica%20chill%20morning", "info": "Abriendo musica matutina en Spotify"})
        results.append(spotify_action)
        return "RUTINA BUENOS DIAS:\n" + "\n---\n".join(results)

    elif routine == "buenas_noches":
        _control_volume("down")
        _control_volume("down")
        tasks_done = mem.get_tasks(status="completed")
        tasks_pending = mem.get_tasks(status="pending")
        summary = f"Resumen del dia: {len(tasks_done)} tareas completadas, {len(tasks_pending)} pendientes."
        results.append(summary)
        results.append("Volumen bajado. Buenas noches, señor.")
        return "RUTINA BUENAS NOCHES:\n" + "\n".join(results)

    elif routine == "modo_estudio":
        results.append("Modo estudio activado. Timer pomodoro: 25 minutos de estudio, 5 de descanso.")
        from datetime import timedelta
        pomodoro_time = (datetime.now() + timedelta(minutes=25)).strftime("%H:%M")
        _set_reminder("Descanso del pomodoro! Tomate 5 minutos.", pomodoro_time)
        results.append(f"Recordatorio programado para las {pomodoro_time}.")
        return "\n".join(results)

    return "Rutina no reconocida."


def _analyze_screen(question="Describe lo que ves en la pantalla"):
    try:
        import mss
        import base64
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[1])
            from mss.tools import to_png
            png_bytes = to_png(screenshot.rgb, screenshot.size)

        img_b64 = base64.b64encode(png_bytes).decode("utf-8")

        api_key = mem.get_config("api_key")
        if not api_key:
            return "No hay API key configurada."

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=mem.get_config("model") or "claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                    {"type": "text", "text": f"Responde en español argentino, breve y conciso. {question}"}
                ]
            }]
        )
        return response.content[0].text
    except ImportError:
        return "Error: mss no instalado."
    except Exception as e:
        return f"Error analizando pantalla: {e}"


def _get_calendar_events():
    ical_url = mem.get_config("google_calendar_url")
    if not ical_url:
        return "Google Calendar no configurado. El usuario debe configurar su URL iCal en Config o decir '/calendar URL_ICAL'."
    try:
        import urllib.request
        req = urllib.request.Request(ical_url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            ical_data = resp.read().decode("utf-8", errors="replace")

        today = datetime.now().strftime("%Y%m%d")
        events = []
        in_event = False
        current = {}
        for line in ical_data.split("\n"):
            line = line.strip()
            if line == "BEGIN:VEVENT":
                in_event = True
                current = {}
            elif line == "END:VEVENT":
                in_event = False
                dtstart = current.get("DTSTART", "")
                if today in dtstart:
                    summary = current.get("SUMMARY", "Sin titulo")
                    time_str = ""
                    if "T" in dtstart:
                        t = dtstart.split("T")[1][:4]
                        time_str = f"{t[:2]}:{t[2:4]}"
                    events.append(f"{'[' + time_str + '] ' if time_str else ''}{summary}")
            elif in_event and ":" in line:
                key, _, val = line.partition(":")
                key = key.split(";")[0]
                current[key] = val

        if events:
            return f"Eventos de hoy ({datetime.now().strftime('%d/%m/%Y')}):\n" + "\n".join(sorted(events))
        return "No hay eventos en el calendario para hoy."
    except Exception as e:
        return f"Error leyendo calendario: {e}"


def _get_greenapi_config():
    instance_id = mem.get_config("greenapi_instance_id")
    token = mem.get_config("greenapi_token")
    api_url = mem.get_config("greenapi_api_url") or "https://7107.api.greenapi.com"
    if not instance_id or not token:
        return None, None, None
    return api_url, instance_id, token


def _search_whatsapp_contacts(name):
    api_url, instance_id, token = _get_greenapi_config()
    if not api_url:
        return "WhatsApp no configurado."
    try:
        import urllib.request
        url = f"{api_url}/waInstance{instance_id}/getContacts/{token}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            contacts = json.loads(resp.read().decode("utf-8"))
        search = name.lower().strip()
        search_words = [w for w in search.split() if len(w) > 1]

        exact = []
        partial = []
        word_match = []
        for c in contacts:
            cname = (c.get("name") or "").lower()
            cid = c.get("id", "")
            if not cname or "@g.us" in cid:
                continue
            phone = cid.replace("@c.us", "")
            entry = {"name": c.get("name"), "phone": phone}
            if search == cname:
                exact.append(entry)
            elif search in cname or cname in search:
                partial.append(entry)
            elif search_words and any(w in cname for w in search_words):
                word_match.append(entry)

        matches = exact or partial or word_match
        if not matches:
            return f"No encontre contacto '{name}'. Pedile el numero al usuario y guardalo en memoria para la proxima."
        if len(matches) == 1:
            return f"Contacto encontrado: {matches[0]['name']} - {matches[0]['phone']}. Usa este numero con send_whatsapp."
        result = f"Encontre {len(matches)} contactos. Preguntale al usuario cual es:\n"
        for m in matches[:10]:
            result += f"- {m['name']}: {m['phone']}\n"
        return result
    except Exception as e:
        return f"Error buscando contactos: {e}"


def _send_whatsapp(phone, message):
    import urllib.request
    phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not phone:
        return "No se proporcionó número de teléfono."
    try:
        cmd = {"action": "whatsapp_send", "phone": phone, "message": message}
        payload = json.dumps(cmd).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:8080/api/browser/command",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            json.loads(resp.read().decode("utf-8"))
        return f"Mensaje enviado por WhatsApp al {phone}. Ya se envió automaticamente."
    except Exception as e:
        return f"Error al enviar WhatsApp: {e}"


def _get_discord_headers():
    token = mem.get_config("discord_bot_token")
    if not token:
        return None, "Discord no configurado. Decile al usuario que vaya a la pestaña Conexiones y configure el Bot Token de Discord."
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}, None


def _send_telegram(text):
    import urllib.request
    try:
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:8080/api/telegram/send",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("success"):
            return f"Notificacion enviada por Telegram: {text[:100]}"
        return "No se pudo enviar. Verificar que Telegram esta configurado y que el usuario hizo /start en el bot."
    except Exception as e:
        return f"Error enviando Telegram: {e}"


def _create_presentation(title, slides):
    import urllib.request
    import subprocess
    try:
        payload = json.dumps({"title": title, "slides": slides}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:8080/api/presentation",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("success"):
            fpath = data.get("path", "")
            if fpath and os.path.exists(fpath):
                try:
                    os.startfile(fpath)
                except Exception:
                    pass
            return f"Presentacion creada y abierta: {title} ({len(slides)} slides). Ruta: {fpath}"
        return f"Error creando presentacion: {data.get('error', 'desconocido')}"
    except Exception as e:
        return f"Error creando presentacion: {e}"


def _list_discord_channels():
    headers, err = _get_discord_headers()
    if err:
        return err
    try:
        import urllib.request
        req = urllib.request.Request("https://discord.com/api/v10/users/@me/guilds", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            guilds = json.loads(resp.read().decode("utf-8"))
        result = []
        for guild in guilds[:10]:
            guild_name = guild["name"]
            guild_id = guild["id"]
            try:
                req2 = urllib.request.Request(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers=headers)
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    channels = json.loads(resp2.read().decode("utf-8"))
                text_channels = [c for c in channels if c.get("type") == 0]
                ch_list = ", ".join([f"#{c['name']} (ID: {c['id']})" for c in text_channels[:15]])
                result.append(f"Servidor: {guild_name}\n  Canales: {ch_list}")
            except Exception:
                result.append(f"Servidor: {guild_name} (no se pudieron listar canales)")
        if not result:
            return "El bot no esta en ningun servidor. El usuario debe invitar el bot a su servidor de Discord."
        return "Servidores y canales de Discord:\n\n" + "\n\n".join(result)
    except Exception as e:
        return f"Error conectando con Discord: {e}"


def _send_discord(channel_id, message):
    headers, err = _get_discord_headers()
    if err:
        return err
    try:
        import urllib.request
        data = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            data=data,
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return f"Mensaje enviado a Discord (canal {channel_id}): {message[:100]}"
    except Exception as e:
        return f"Error enviando mensaje a Discord: {e}"


def _read_discord(channel_id, count=10):
    headers, err = _get_discord_headers()
    if err:
        return err
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={min(count, 50)}",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            messages = json.loads(resp.read().decode("utf-8"))
        if not messages:
            return "No hay mensajes en este canal."
        result = []
        for msg in reversed(messages):
            author = msg.get("author", {}).get("username", "?")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")[:16].replace("T", " ")
            result.append(f"[{timestamp}] {author}: {content}")
        return f"Ultimos {len(messages)} mensajes del canal:\n" + "\n".join(result)
    except Exception as e:
        return f"Error leyendo Discord: {e}"


def _read_whatsapp(count=5):
    import urllib.request
    try:
        cmd = {"action": "whatsapp_read", "count": count}
        payload = json.dumps(cmd).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:8080/api/browser/command",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            json.loads(resp.read().decode("utf-8"))

        import time
        time.sleep(8)
        try:
            req2 = urllib.request.Request("http://localhost:8080/api/browser/whatsapp-messages")
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                data = json.loads(resp2.read().decode("utf-8"))
            if data.get("messages"):
                return "Mensajes recientes de WhatsApp:\n" + "\n".join(data["messages"])
            return "No se pudieron leer mensajes. Asegurate de tener WhatsApp Web abierto en Chrome."
        except Exception:
            return "Leyendo mensajes de WhatsApp Web... Revisá la pestaña de WhatsApp Web en Chrome."
    except Exception as e:
        return f"Error leyendo WhatsApp: {e}"


def _whatsapp_call(params):
    import urllib.request
    phone = params.get("phone", "").replace("+", "").replace(" ", "").replace("-", "")
    if not phone:
        return "No se proporcionó número de teléfono."
    call_type = params.get("call_type", "audio")
    contact = params.get("contact_name", "")
    try:
        cmd = {"action": "whatsapp_call", "phone": phone, "callType": call_type}
        payload = json.dumps(cmd).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:8080/api/browser/command",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            json.loads(resp.read().decode("utf-8"))
        name_str = f" a {contact}" if contact else ""
        tipo = "videollamada" if call_type == "video" else "llamada"
        return f"Iniciando {tipo}{name_str} por WhatsApp al número {phone}. Se abrirá WhatsApp Web y se hará la llamada automáticamente."
    except Exception as e:
        return f"Error al iniciar llamada de WhatsApp: {e}"


def _browser_tabs():
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:8080/api/browser/state")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tabs = data.get("tabs", [])
        if not tabs:
            return "No hay info de pestañas. La extension de Chrome no esta conectada. Decile al usuario que instale la extension JARVIS Browser Link desde chrome://extensions."
        text = f"{len(tabs)} pestañas abiertas:\n"
        for t in tabs:
            audible = " [SONANDO]" if t.get("audible") else ""
            active = " [ACTIVA]" if t.get("active") else ""
            text += f"- [{t['id']}] {t.get('title', 'Sin titulo')[:60]}{audible}{active}\n  {t.get('url', '')[:80]}\n"
        return text
    except Exception as e:
        return f"No pude conectar con la extension de Chrome: {e}. La extension no esta instalada o el servidor no esta corriendo."


def _browser_media():
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:8080/api/browser/state")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        media = data.get("media", [])
        active = data.get("activeMedia", [])
        if active:
            m = active[0]
            status = "Reproduciendo" if m.get("playing") else "Pausado"
            time_str = ""
            if m.get("currentTime") and m.get("duration"):
                cur = m["currentTime"]
                dur = m["duration"]
                time_str = f" ({cur//60}:{cur%60:02d} / {dur//60}:{dur%60:02d})"
            return f"{status} en {m.get('site', '?')}: \"{m.get('title', 'Sin titulo')}\" de {m.get('artist', 'Desconocido')}{time_str}\nURL: {m.get('url', '')}"
        if media:
            m = media[0]
            status = "Reproduciendo" if m.get("playing") else "Pausado"
            return f"{status} en {m.get('site', '?')}: \"{m.get('title', 'Sin titulo')}\" de {m.get('artist', 'Desconocido')}\nURL: {m.get('url', '')}"
        # No hay media reportado, pero verificar si hay pestañas de media abiertas
        tabs = data.get("tabs", [])
        media_tabs = [t for t in tabs if t.get("url") and any(s in t["url"] for s in ["youtube.com", "spotify.com", "music.youtube"])]
        if media_tabs:
            names = ", ".join(t.get("title", t["url"])[:60] for t in media_tabs[:3])
            return f"No hay info de reproduccion activa pero hay pestañas de media abiertas: {names}. Podes intentar enviar un comando media_control con command 'toggle' igualmente."
        return "No hay nada reproduciendose en el browser ahora."
    except Exception as e:
        return f"No pude obtener info de media: {e}"


def _browser_command(cmd):
    import urllib.request
    try:
        payload = json.dumps(cmd).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:8080/api/browser/command",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        action = cmd.get("action", "")
        if action == "open_or_switch":
            return f"Comando enviado: abrir/cambiar a {cmd.get('urlPattern', cmd.get('url', ''))}"
        elif action == "media_control":
            return f"Comando de media enviado: {cmd.get('command', 'toggle')}"
        elif action == "close_tab":
            return f"Comando enviado: cerrar pestaña con {cmd.get('urlPattern', '')}"
        elif action == "switch_tab":
            return f"Comando enviado: cambiar a pestaña con {cmd.get('urlPattern', '')}"
        return f"Comando enviado al browser."
    except Exception as e:
        return f"Error enviando comando al browser: {e}"


def _analyze_text(text, focus="general", language="es"):
    api_key = mem.get_config("api_key")
    if not api_key:
        return "Error: no hay API key configurada."

    text_len = len(text)

    focus_extra = {
        "legal": """ENFOQUE JURIDICO ESPECIAL:
- Cita articulos, leyes, decretos y normas EXACTAMENTE como aparecen en el documento. No agregues normas que el documento no menciona.
- Distingui entre derecho vigente y antecedentes historicos.
- No confundas propuestas legislativas o anteproyectos con texto sancionado.
- Identifica derechos, obligaciones, plazos, sanciones, excepciones, requisitos de procedencia y efectos juridicos.
- Explica cada termino juridico tecnico.""",
        "academico": """ENFOQUE ACADEMICO ESPECIAL:
- Identifica tesis principal, argumentos, evidencia, metodologia, conclusiones.
- Relaciona con el campo de estudio y teorias/autores mencionados.
- Distingui entre lo que el autor afirma y lo que cita de otros.""",
        "cientifico": """ENFOQUE CIENTIFICO ESPECIAL:
- Identifica hipotesis, metodologia, resultados, datos estadisticos, conclusiones y limitaciones.""",
        "noticioso": """ENFOQUE NOTICIOSO ESPECIAL:
- Identifica hechos principales (que, quien, cuando, donde, por que), fuentes citadas y posibles sesgos.""",
        "general": """Analiza el texto de forma integral adaptando la metodologia al contenido."""
    }

    focus_text = focus_extra.get(focus, focus_extra["general"])

    analysis_prompt = f"""Sos un especialista multidisciplinario en analisis documental, comprension de textos, extraccion de conocimiento, sintesis avanzada, verificacion de informacion y organizacion pedagogica.

Tu mision es transformar el documento proporcionado en un analisis de MAXIMA CALIDAD: exhaustivo, preciso, organizado y util.

{focus_text}

METODOLOGIA OBLIGATORIA:

ETAPA 1 — EXPLORACION COMPLETA
- Identifica el tipo de documento, tematica, extension y estructura.
- Reconoce titulos, subtitulos, unidades, capitulos, apartados.
- Lee TODO el contenido antes de producir conclusiones.
- Para documentos extensos, trabaja por segmentos ordenados conservando contexto.
- Detecta secciones faltantes o contenido que no pudo procesarse.
- NUNCA presentes un analisis parcial como exhaustivo.

ETAPA 2 — EXTRACCION DE CONOCIMIENTO
Identifica y conserva cuando existan:
- Conceptos y definiciones fundamentales
- Clasificaciones y diferencias
- Requisitos, condiciones y excepciones
- Causas, consecuencias y relaciones
- Etapas, procesos y procedimientos
- Fechas, cifras, nombres y terminologia especializada
- Normas, articulos y referencias (SOLO los que aparecen en el texto)
- Ejemplos importantes y aplicaciones practicas
- Conclusiones y argumentos centrales

ETAPA 3 — ANALISIS PROFUNDO
- Determina las ideas centrales del documento.
- Diferencia informacion fundamental de complementaria.
- Relaciona conceptos distribuidos en diferentes secciones.
- Identifica contradicciones internas y ambiguedades.
- Simplifica el lenguaje sin alterar significado.
- Preserva terminos tecnicos y explicalos.
- NO confundas antecedentes historicos con informacion vigente.
- NO presentes opiniones o interpretaciones como hechos demostrados.

ETAPA 4 — CONTROL DE CALIDAD
Antes de finalizar:
1. Compara el analisis con la estructura original.
2. Verifica que TODAS las secciones hayan sido procesadas.
3. Comproba que las definiciones mantengan su significado.
4. Revisa que no falten requisitos, condiciones o excepciones fundamentales.
5. Detecta afirmaciones no respaldadas por el documento.
6. Identifica expresamente cualquier contenido no procesado.

FORMATO DE RESPUESTA:

**A. FICHA DEL DOCUMENTO**
Tema, tipo, extension estimada, estructura y proposito.

**B. RESUMEN EJECUTIVO**
Explicacion clara de lo mas importante del documento COMPLETO. Debe cubrir TODAS las unidades/secciones.

**C. MAPA DE CONTENIDOS**
Todas las secciones identificadas, organizadas jerarquicamente.

**D. ANALISIS COMPLETO POR SECCIONES**
Para CADA capitulo, unidad o apartado del documento:
▸ [Nombre de la Seccion]
- Tema central
- Conceptos y definiciones clave
- Clasificaciones y distinciones importantes
- Requisitos, condiciones, excepciones
- Normas/articulos citados (SOLO los del documento)
- Datos, cifras, plazos relevantes
- Ejemplos o aplicaciones

**E. CONCEPTOS FUNDAMENTALES**
Glosario con explicaciones precisas segun el documento.

**F. CONEXIONES IMPORTANTES**
Relaciones entre temas y conceptos presentes en el documento.

**G. GUIA DE ESTUDIO**
Conceptos clave para examen, clasificaciones importantes, requisitos, elementos y distinciones fundamentales.

**H. AMBIGUEDADES Y CONTRADICCIONES**
Problemas detectados, ubicacion y por que necesitan revision.

**I. AUDITORIA DE COBERTURA**
- Secciones analizadas completamente
- Secciones analizadas parcialmente (indicar por que)
- Secciones no cubiertas (indicar por que)
- Porcentaje estimado de cobertura del documento
- Limitaciones del analisis

REGLA FINAL: El objetivo es obtener el MAXIMO conocimiento util y fiel al documento. No sacrifiques informacion fundamental por brevedad. Si el documento es extenso, el analisis debe ser proporcionalmente extenso.

Responde en espanol argentino.

TEXTO A ANALIZAR ({text_len} caracteres):
{text}"""

    client = anthropic.Anthropic(api_key=api_key)

    models = ["claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"]

    for model in models:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=16000,
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            result = response.content[0].text
            return json.dumps({"action": "show_analysis", "analysis": result, "focus": focus, "chars": text_len})
        except anthropic.NotFoundError:
            continue
        except Exception as e:
            return f"Error en el analisis: {e}"

    return "Error: no se pudo conectar con ningun modelo para el analisis."


def _generate_image(prompt, width=1024, height=1024):
    import urllib.request
    import time
    import random
    import base64

    images_dir = os.path.join(os.path.dirname(__file__), "generated_images")
    os.makedirs(images_dir, exist_ok=True)

    timestamp = int(time.time())
    seed = random.randint(1, 999999)
    filename = f"img_{timestamp}_{seed}.png"
    filepath = os.path.join(images_dir, filename)

    together_key = mem.get_config("together_api_key")
    if together_key:
        return _generate_image_together(together_key, prompt, width, height, filepath, filename)
    return _generate_image_pollinations(prompt, width, height, filepath, filename, seed)


def _generate_image_together(api_key, prompt, width, height, filepath, filename):
    import urllib.request

    payload = json.dumps({
        "model": "black-forest-labs/FLUX.1-schnell-Free",
        "prompt": prompt,
        "width": width,
        "height": height,
        "n": 1,
        "response_format": "b64_json"
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.together.xyz/v1/images/generations",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        import base64
        img_b64 = data["data"][0]["b64_json"]
        img_bytes = base64.b64decode(img_b64)
        with open(filepath, "wb") as f:
            f.write(img_bytes)

        return json.dumps({"action": "show_image", "image_url": f"/api/images/{filename}", "prompt": prompt})
    except Exception as e:
        _log(f"[IMAGE] Together error: {e}")
        return f"Error generando imagen con Together AI: {e}"


def _generate_image_pollinations(prompt, width, height, filepath, filename, seed):
    import urllib.request
    import time
    from urllib.parse import quote

    encoded_prompt = quote(prompt)
    for attempt in range(3):
        try:
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true&seed={seed + attempt}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
                if len(data) < 1000:
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    return "Error: imagen muy pequeña, servicio con problemas. Intenta de nuevo."
                with open(filepath, "wb") as f:
                    f.write(data)
            return json.dumps({"action": "show_image", "image_url": f"/api/images/{filename}", "prompt": prompt})
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            return f"Error generando imagen: {e}"
    return "Error generando imagen: se agotaron los intentos."


def _play_youtube(query):
    import random
    import urllib.request
    from urllib.parse import quote
    search_url = f"https://www.youtube.com/results?search_query={quote(query)}"
    try:
        req = urllib.request.Request(search_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        seen = set()
        unique = []
        for v in video_ids:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        if unique:
            chosen = random.choice(unique[:5])
            url = f"https://www.youtube.com/watch?v={chosen}"
            _browser_command({"action": "open_or_switch", "url": url, "urlPattern": "youtube.com"})
            return json.dumps({"info": f"Abriendo video de YouTube para '{query}'"})
    except Exception as e:
        _log(f"[PLAY_YT] Error: {e}")
    _browser_command({"action": "open_or_switch", "url": search_url, "urlPattern": "youtube.com"})
    return json.dumps({"info": f"Buscando '{query}' en YouTube"})


def _play_spotify(query):
    from urllib.parse import quote
    url = f"https://open.spotify.com/search/{quote(query)}"
    _browser_command({"action": "open_or_switch", "url": url, "urlPattern": "spotify.com"})
    return json.dumps({"info": f"Abriendo '{query}' en Spotify"})


def _handle_media_shortcut(msg):
    """Detecta comandos SIMPLES de play/pausa y los ejecuta directamente."""
    lower = msg.lower().strip()
    _log(f"[BRAIN] Media shortcut check: '{lower}'")

    import re

    # PRIMERO: detectar comandos de PARAR/PAUSAR (tienen prioridad sobre new_content)
    stop_patterns = [
        r'\bpar[aá]\b.*\b(canci[oó]n|m[uú]sica|video|tema|eso|esto)\b',
        r'\bpaus[aá]', r'\bponele pausa\b', r'\bpause\b',
        r'\bdale pausa\b', r'\ble des pausa\b', r'\bque pare\b',
        r'\bdet[eé]n[eé]\b', r'\bpar[aá] (el|la|eso|esto)\b',
        r'\bpar[aá] la\b', r'\bpar[aá]lo\b', r'\bfren[aá]\b',
        r'\bstop\b', r'\bsilencio\b', r'\bcall[aá]te\b',
    ]
    is_stop = any(re.search(p, lower) for p in stop_patterns)

    if is_stop:
        result = _browser_command({"action": "media_control", "command": "pause"})
        _log(f"[BRAIN] Media shortcut: pause -> {result}")
        return "Listo, le puse pausa."

    # SEGUNDO: si quiere reproducir algo NUEVO, dejar que el cerebro lo maneje
    new_content_patterns = [
        r'\b(reproduc[ií]|pone|pon[eé]|busc[aá])\b.+\b(canci[oó]n|m[uú]sica|video|tema)\b',
        r'\b(alguna|alg[uú]n|una|un)\b.+\b(canci[oó]n|m[uú]sica|video|tema)\b',
        r'\ben (youtube|spotify)\b',
        r'\b(m[uú]sica|canci[oó]n|tema|video)\s+de\s+\w',
    ]
    is_new_content = any(re.search(p, lower) for p in new_content_patterns)
    if is_new_content:
        return None

    # TERCERO: comandos simples de play
    play_patterns = [r'\bdale play\b', r'\bponele play\b', r'\breanud[aá]\b', r'\bplay\b']
    is_play = any(re.search(p, lower) for p in play_patterns)

    if is_play:
        result = _browser_command({"action": "media_control", "command": "play"})
        _log(f"[BRAIN] Media shortcut: play -> {result}")
        return "Listo, le di play."

    return None


TRANSCRIPTION_FIXES = {
    "dale replay": "dale play",
    "ponele replay": "ponele play",
    "dallas play": "dale play",
    "barvis": "jarvis",
    "cloud code": "claude code",
    "cloud": "claude",
    "yutub": "youtube",
    "yutube": "youtube",
    "yutu": "youtube",
    "güats": "whatsapp",
    "guasap": "whatsapp",
    "wasap": "whatsapp",
    "watsap": "whatsapp",
    "wats app": "whatsapp",
    "what's app": "whatsapp",
    "what sap": "whatsapp",
    "esteam": "steam",
    "steam": "steam",
    "discor": "discord",
    "dispord": "discord",
    "espotifai": "spotify",
    "espotify": "spotify",
    "spotifai": "spotify",
    "netflis": "netflix",
    "netflix": "netflix",
    "chatgpt": "chatgpt",
    "chat gpt": "chatgpt",
    "chet gpt": "chatgpt",
    "chat chipi ti": "chatgpt",
}


def _fix_transcription(text):
    """Corrige errores comunes de transcripción de voz."""
    fixed = text
    lower = fixed.lower()
    for wrong, right in TRANSCRIPTION_FIXES.items():
        if wrong in lower:
            idx = lower.find(wrong)
            fixed = fixed[:idx] + right + fixed[idx + len(wrong):]
            lower = fixed.lower()
    return fixed


def chat(user_message, api_key):
    user_message = _fix_transcription(user_message)

    # Atajo directo para comandos de media
    media_response = _handle_media_shortcut(user_message)
    if media_response:
        mem.save_message("user", user_message)
        mem.save_message("assistant", media_response)
        return {"text": media_response, "actions": []}

    provider = mem.get_config("ai_provider", "anthropic")

    if provider == "openrouter":
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        MODELS_OR = [
            "anthropic/claude-sonnet-4",
            "anthropic/claude-haiku-4",
            "anthropic/claude-3.5-sonnet",
        ]
    else:
        client = anthropic.Anthropic(api_key=api_key)
        MODELS_OR = None

    MODELS_ANTHROPIC = [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-20250929",
        "claude-sonnet-5-5",
    ]

    mem.save_message("user", user_message)

    recent = mem.get_recent_conversations(limit=10)
    messages = []
    for msg in recent:
        messages.append({"role": msg["role"], "content": msg["content"]})

    system_prompt = build_system_prompt()
    saved_model = mem.get_config("model")

    if saved_model:
        models_to_try = [saved_model]
    elif provider == "openrouter":
        models_to_try = MODELS_OR
    else:
        models_to_try = MODELS_ANTHROPIC

    response = None
    used_model = None
    for model in models_to_try:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )
            used_model = model
            if not saved_model:
                mem.set_config("model", model)
            break
        except anthropic.NotFoundError:
            continue

    if response is None:
        if provider == "openrouter":
            raise Exception("Ningun modelo disponible en OpenRouter. Verifica tu key en openrouter.ai/keys")
        raise Exception("Ningun modelo disponible. Verifica que tu cuenta tenga creditos en console.anthropic.com/settings/billing")

    actions = []
    final_text = ""
    _log(f"[BRAIN] stop_reason={response.stop_reason}, model={used_model}")

    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = process_tool_call(block.name, block.input)
                _log(f"[BRAIN] tool={block.name} result={result[:200]}")
                try:
                    action = json.loads(result)
                    if isinstance(action, dict) and "action" in action:
                        actions.append(action)
                        _log(f"[BRAIN] Action added: {action.get('action')}")
                except (json.JSONDecodeError, TypeError):
                    pass
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })
            elif block.type == "text" and block.text:
                final_text += block.text

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=used_model,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

    for block in response.content:
        if hasattr(block, "text") and block.text:
            final_text += block.text

    mem.save_message("assistant", final_text)

    return {"text": final_text, "actions": actions}
