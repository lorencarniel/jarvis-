import os
import json
import subprocess
import tempfile
from pathlib import Path

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
CLIPS_DIR = os.path.join(os.path.dirname(__file__), "clips")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

def _find_ffmpeg():
    import shutil
    import glob
    found = shutil.which("ffmpeg")
    if found:
        return found
    patterns = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages", "**", "ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for pat in patterns:
        matches = glob.glob(pat, recursive=True)
        if matches:
            return matches[0]
    return "ffmpeg"

FFMPEG_PATH = _find_ffmpeg()

_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


def transcribe_video(video_path):
    model = get_whisper_model()
    segments, info = model.transcribe(video_path, language="es", beam_size=5)
    result = []
    full_text = []
    for seg in segments:
        entry = {
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip()
        }
        result.append(entry)
        full_text.append(seg.text.strip())
    return {
        "language": info.language,
        "duration": round(info.duration, 2),
        "segments": result,
        "full_text": " ".join(full_text)
    }


def find_interesting_clips(transcript, api_key, min_clip_seconds=10, max_clip_seconds=60):
    import urllib.request
    segments_text = ""
    for s in transcript["segments"]:
        segments_text += f"[{_fmt_time(s['start'])} - {_fmt_time(s['end'])}] {s['text']}\n"

    prompt = f"""Analiza esta transcripcion de video y encontra los momentos mas interesantes, graciosos, impactantes o virales para hacer clips cortos.

TRANSCRIPCION:
{segments_text}

Devolveme SOLO un JSON array con los clips. Cada clip debe tener:
- "start": timestamp de inicio en segundos (numero)
- "end": timestamp de fin en segundos (numero)
- "title": titulo corto y descriptivo del clip
- "reason": por que es interesante

Reglas:
- Cada clip debe durar entre {min_clip_seconds} y {max_clip_seconds} segundos
- Maximo 5 clips
- Ordenalos del mas interesante al menos
- Devolvé SOLO el JSON, sin texto extra"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    text = data["content"][0]["text"]
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return []


def cut_clip(video_path, start, end, output_name, clip_format="horizontal"):
    output_path = os.path.join(CLIPS_DIR, output_name)
    vf = None
    if clip_format == "vertical":
        vf = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    elif clip_format == "square":
        vf = "crop='min(iw,ih)':'min(iw,ih)',scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", video_path,
        "-ss", str(start),
        "-to", str(end),
    ]
    if vf:
        cmd += ["-vf", vf]
    else:
        cmd += ["-pix_fmt", "yuv420p"]
    cmd += [
        "-c:v", "libx264",
        "-profile:v", "main",
        "-c:a", "aac",
        "-preset", "fast",
        "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, timeout=120)
    if os.path.exists(output_path):
        return output_path
    return None


def process_video(video_path, api_key, make_clips=True, clip_format="horizontal"):
    transcript = transcribe_video(video_path)

    result = {
        "transcript": transcript,
        "clips": [],
        "clip_format": clip_format
    }

    if make_clips and api_key and len(transcript["segments"]) > 2:
        try:
            interesting = find_interesting_clips(transcript, api_key)
            for i, clip in enumerate(interesting):
                filename = f"clip_{i+1}_{clip.get('title', 'clip').replace(' ', '_')[:30]}.mp4"
                filename = "".join(c for c in filename if c.isalnum() or c in "_-.")
                path = cut_clip(video_path, clip["start"], clip["end"], filename, clip_format)
                if path:
                    clip["file"] = path
                    clip["filename"] = filename
                    result["clips"].append(clip)
        except Exception as e:
            result["clip_error"] = str(e)

    return result


def _fmt_time(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"
