"""Stage 0: download the source video/audio and read ground-truth metadata."""
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure ffmpeg & ffprobe are on PATH in all environments
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass


@dataclass
class VideoInfo:
    video_path: Path
    audio_path: Path
    fps: float
    duration_sec: float
    width: int
    height: int
    has_subs: bool
    subs_path: Path | None


def get_video_folder_name(url: str) -> str:
    """Generate a clean, sanitized directory name for any video URL."""
    import re
    from urllib.parse import urlparse

    clean_url = url.strip()
    # YouTube URL
    yt_match = re.search(r'(?:v=|\/)([a-zA-Z0-9_-]{11})(?:[&?]|$)', clean_url)
    if "youtu" in clean_url and yt_match:
        return f"youtube_{yt_match.group(1)}"

    # ok.ru URL
    ok_match = re.search(r'ok\.ru/video/(\d+)', clean_url)
    if ok_match:
        return f"ok_ru_{ok_match.group(1)}"

    # Generic URLs (Vimeo, direct mp4, etc.)
    try:
        parsed = urlparse(clean_url)
        host = parsed.netloc.replace("www.", "").split(".")[0]
        path_part = parsed.path.strip("/").split("/")[-1]
        slug = re.sub(r"[^\w\-_\.]", "_", f"{host}_{path_part}").strip("_")
        return slug[:50] or "video_output"
    except Exception:
        import hashlib
        return f"video_{hashlib.md5(clean_url.encode()).hexdigest()[:8]}"



from typing import Callable, Optional


def download(url: str, outdir: Path, progress_cb: Optional[Callable[[dict], None]] = None) -> Path:
    """Download best video+audio via yt-dlp. Works across hosts (YouTube,
    ok.ru, Vimeo, etc.) through one consistent interface."""
    import yt_dlp
    import shutil

    outdir.mkdir(parents=True, exist_ok=True)
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".ts", ".m4v"}
    existing = [p for p in outdir.glob("source.*") if p.suffix.lower() in video_exts and ".f" not in p.name and p.stat().st_size > 500*1024]
    if existing:
        print(f"      [Cache hit] Using existing video at {existing[0]}")
        if progress_cb:
            progress_cb({"type": "download_progress", "pct": 100.0, "message": "Using cached video file", "is_cache": True})
        return existing[0]

    # Find directory containing ffmpeg.exe
    ffmpeg_dir = None
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        which_ff = shutil.which("ffmpeg")
        if which_ff:
            ffmpeg_dir = str(Path(which_ff).parent)
    except Exception:
        pass

    def ydl_progress_hook(d):
        if not progress_cb:
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0
            if total > 0:
                pct = min(100.0, (downloaded / total) * 100.0)
            elif d.get("fragment_count") and d["fragment_count"] > 0:
                pct = min(100.0, (d.get("fragment_index", 0) / d["fragment_count"]) * 100.0)
            else:
                pct = 0.0

            progress_cb({
                "type": "download_progress",
                "pct": round(pct, 1),
                "downloaded_bytes": downloaded,
                "total_bytes": total,
                "speed_bytes": round(speed, 1),
                "eta_sec": round(eta, 1),
                "filename": Path(d.get("filename", "video")).name,
            })
        elif status == "finished":
            progress_cb({
                "type": "download_progress",
                "pct": 100.0,
                "downloaded_bytes": d.get("total_bytes") or 0,
                "total_bytes": d.get("total_bytes") or 0,
                "speed_bytes": 0,
                "eta_sec": 0,
                "message": "Download finished, processing stream...",
            })

    out_template = str(outdir / "source.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en.*", "en", "en-US", "en-orig"],
        "nocheckcertificate": True,
        "no_check_certificates": True,
        "prefer_insecure": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "progress_hooks": [ydl_progress_hook],
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "ios"]
            }
        },
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": False,
    }
    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    print(f"      [yt-dlp] Downloading media from: {url}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"      [yt-dlp] Primary download attempt warning: {e}. Retrying with basic format...")
        fallback_opts = {
            "outtmpl": out_template,
            "format": "best",
            "nocheckcertificate": True,
            "no_check_certificates": True,
            "prefer_insecure": True,
            "retries": 5,
            "socket_timeout": 30,
            "progress_hooks": [ydl_progress_hook],
            "quiet": False,
            "no_warnings": True,
            "ignoreerrors": False,
        }
        if ffmpeg_dir:
            fallback_opts["ffmpeg_location"] = ffmpeg_dir
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            ydl.download([url])

    # Identify video file (excluding partial or separate audio files)
    matches = [p for p in outdir.glob("source.*") if p.suffix.lower() in video_exts and ".f" not in p.name and not p.name.endswith(".part")]
    if not matches:
        matches = [p for p in outdir.glob("*.*") if p.suffix.lower() in video_exts and not p.name.endswith(".part")]
    if not matches:
        raise RuntimeError(f"Could not download or locate video file from {url}. Please check URL accessibility or internet connection.")
    return matches[0]


def extract_audio(video_path: Path, outdir: Path) -> Path:
    audio_path = outdir / "audio.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-ac", "1", "-ar", "16000", "-vn",
        str(audio_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return audio_path


def probe(video_path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path),
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def get_video_info(url: str, outdir: Path, progress_cb: Optional[Callable[[dict], None]] = None) -> VideoInfo:
    video_path = download(url, outdir, progress_cb=progress_cb)
    if progress_cb:
        progress_cb({"type": "stage", "stage": "audio_extract", "message": "Extracting audio track (16kHz mono WAV)..."})
    audio_path = extract_audio(video_path, outdir)
    meta = probe(video_path)

    v_stream = next(s for s in meta["streams"] if s["codec_type"] == "video")
    
    # Handle FPS calculation robustly
    r_fps = v_stream.get("r_frame_rate", "30/1")
    if "/" in r_fps:
        num, den = r_fps.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(r_fps)

    duration = float(meta.get("format", {}).get("duration", 0.0))
    if duration == 0.0 and "duration" in v_stream:
        duration = float(v_stream["duration"])

    subs_candidates = list(outdir.glob("source.en*.vtt")) + list(outdir.glob("source.en*.srt"))
    subs_path = subs_candidates[0] if subs_candidates else None

    return VideoInfo(
        video_path=video_path,
        audio_path=audio_path,
        fps=fps,
        duration_sec=duration,
        width=int(v_stream.get("width", 0)),
        height=int(v_stream.get("height", 0)),
        has_subs=subs_path is not None,
        subs_path=subs_path,
    )

