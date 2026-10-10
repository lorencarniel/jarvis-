# J.A.R.V.I.S. - Asistente Personal con IA

> Just A Rather Very Intelligent System

Asistente personal de escritorio con inteligencia artificial, inspirado en el JARVIS de Iron Man. Usa **Claude (Anthropic)** como cerebro, control por voz, memoria persistente, y se integra con Chrome para controlar pestañas, media, WhatsApp y más.

![JARVIS UI](https://img.shields.io/badge/version-9.0-blue) ![Python](https://img.shields.io/badge/python-3.10+-green) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## Funcionalidades

- **Chat por voz y texto** - Habla con JARVIS usando el micrófono o escribiendo
- **Wake word "Hey Jarvis"** - Se activa con la voz, sin tocar nada
- **Memoria persistente** - Recuerda todo lo que le digas (SQLite local)
- **Control de media** - Play/pausa de YouTube, Spotify, Twitch, Netflix desde la voz
- **Abrir aplicaciones** - Detecta automáticamente todas las apps instaladas en Windows
- **WhatsApp** - Enviar mensajes y hacer llamadas por WhatsApp Web
- **Gmail** - Leer y enviar emails
- **Tareas y recordatorios** - Crear tareas con fecha/hora y recibir notificaciones
- **Transcripción de video** - Subir videos y obtener transcripción + clips automáticos
- **Análisis de documentos** - Subir PDF/DOCX y hacer preguntas sobre el contenido
- **Generación de imágenes** - Genera imágenes con IA (Together AI / Pollinations)
- **Control del sistema** - Volumen, brillo, apagar PC, bloquear, minimizar todo
- **Búsqueda web** - Busca en internet y te resume los resultados
- **Rutinas automáticas** - "Buenos días" / "Buenas noches" / "Modo estudio"

## Requisitos

- **Windows 10/11**
- **Python 3.10+** ([python.org](https://www.python.org/downloads/))
- **Google Chrome** (para la extensión de control de pestañas)
- **API Key de Anthropic** ([console.anthropic.com](https://console.anthropic.com))
- **FFmpeg** (opcional, para transcripción de video) - `winget install ffmpeg`

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/jarvis.git
cd jarvis
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

O ejecutar `instalar.bat` que hace lo mismo.

### 3. Instalar la extensión de Chrome

1. Abrir `chrome://extensions/` en Chrome
2. Activar **Modo desarrollador** (arriba a la derecha)
3. Click en **Cargar descomprimida**
4. Seleccionar la carpeta `chrome-extension/`

### 4. Iniciar JARVIS

**Opción A** - Sin ventana visible (recomendado):
```
Doble click en iniciar_jarvis.vbs
```

**Opción B** - Con ventana (para ver logs):
```
Doble click en iniciar.bat
```

### 5. Abrir en Chrome

Ir a **http://localhost:8080** en Chrome.

### 6. Configurar API Key

1. Ir a la pestaña **Config** en la UI
2. Pegar tu API Key de Anthropic
3. Click en **Guardar y verificar**

## Configuración opcional

### Gmail
Para leer/enviar emails:
1. Ir a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Crear un App Password con nombre "JARVIS"
3. Configurar en la pestaña Config de la UI

### Generación de imágenes
Para mejor calidad de imágenes:
1. Crear cuenta en [together.ai](https://api.together.xyz)
2. Copiar tu API Key
3. Configurar en la pestaña Config de la UI

Sin esta key, JARVIS usa Pollinations (gratis pero menor calidad).

### Transcripción de video
Requiere FFmpeg instalado:
```bash
winget install ffmpeg
```
El modelo de Whisper se descarga automáticamente la primera vez.

## Estructura del proyecto

```
jarvis/
├── server.py              # Servidor Flask (backend principal)
├── brain.py               # Cerebro IA (Claude API + 49 herramientas)
├── memory.py              # Sistema de memoria persistente (SQLite)
├── gmail_integration.py   # Integración con Gmail
├── video_processor.py     # Transcripción de video con Whisper
├── requirements.txt       # Dependencias Python
├── ui/                    # Frontend
│   ├── index.html         # Página principal con reactor arc
│   ├── jarvis.js          # Lógica del cliente (voz, wake word, chat)
│   └── styles.css         # Estilos Iron Man / HUD
├── chrome-extension/      # Extensión de Chrome
│   ├── manifest.json      # Manifest V3
│   ├── background.js      # Service worker (polling, media, WhatsApp)
│   └── content.js         # Content script (detección de media)
├── iniciar_jarvis.vbs     # Iniciar sin ventana visible
├── cerrar_jarvis.vbs      # Cerrar servidor
├── iniciar.bat            # Iniciar con ventana (ver logs)
└── instalar.bat           # Instalar dependencias
```

## Comandos de voz (ejemplos)

| Comando | Qué hace |
|---------|----------|
| "Jarvis, reproducime algo de Emilia Mernes" | Busca y reproduce en YouTube |
| "Jarvis, pará la canción" | Pausa la música/video |
| "Jarvis, dale play" | Reanuda la reproducción |
| "Jarvis, abrime Discord" | Abre la app de Discord |
| "Jarvis, llamá a mamá" | Llama por WhatsApp Web |
| "Jarvis, recordá que mañana tengo examen" | Guarda en memoria |
| "Jarvis, mis tareas pendientes" | Lista tareas |
| "Jarvis, leé mis emails" | Lee los últimos emails |
| "Jarvis, buscá qué es la ley 26.994" | Busca en internet |
| "Jarvis, apagá la PC en 30 minutos" | Programa apagado |
| "Jarvis, buenos días" | Ejecuta rutina matutina |

## Tecnologías

- **Backend**: Python + Flask
- **IA**: Claude (Anthropic) - modelos Haiku/Sonnet
- **Voz**: Web Speech API (reconocimiento) + Edge TTS (síntesis)
- **Memoria**: SQLite
- **Media**: Chrome Extension (Manifest V3)
- **Transcripción**: faster-whisper

## Notas

- La API Key de Anthropic se guarda localmente en SQLite, nunca se envía a ningún servidor externo
- Todo corre en tu máquina, no hay servidor en la nube
- La extensión de Chrome solo se comunica con `localhost:8080`
- Para cerrar JARVIS: ejecutar `cerrar_jarvis.vbs` o cerrar la ventana del bat

## Licencia

MIT License - Usalo como quieras.
