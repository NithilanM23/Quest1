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



def download(url: str, outdir: Path) -> Path:
    """Download best video+audio via yt-dlp. Works across hosts (YouTube,
    ok.ru, Vimeo, etc.) through one consistent interface."""
    outdir.mkdir(parents=True, exist_ok=True)
    video_exts = {".mp4", ".mkv", ".avi", ".mov"}
    existing = [p for p in outdir.glob("source.*") if p.suffix.lower() in video_exts and ".f" not in p.name and p.stat().st_size > 500*1024]
    if existing:
        print(f"      [Cache hit] Using existing video at {existing[0]}")
        return existing[0]

    # Find directory containing ffmpeg.exe
    ffmpeg_dir = None
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        import shutil
        which_ff = shutil.which("ffmpeg")
        if which_ff:
            ffmpeg_dir = str(Path(which_ff).parent)
    except Exception:
        pass

    out_template = str(outdir / "source.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-N", "4",
        "--retries", "10",
        "--fragment-retries", "10",
        "--extractor-args", "youtube:player_client=android,web,ios",
        "--no-check-certificates",
    ]
    if ffmpeg_dir:
        cmd.extend(["--ffmpeg-location", ffmpeg_dir])

    cmd.extend([
        "-f", "bestvideo*[height<=720]+bestaudio/best[height<=720]/bestvideo*+bestaudio/best/b",
        "--merge-output-format", "mp4",
        "--write-subs", "--write-auto-subs", "--sub-langs", "en.*",
        "-o", out_template,
        url,
    ])
    subprocess.run(cmd, check=True)
    
    # Identify video file (excluding partial or separate audio files)
    matches = [p for p in outdir.glob("source.*") if p.suffix.lower() in video_exts and ".f" not in p.name]
    if not matches:
        # Fallback to any mp4 in outdir
        matches = list(outdir.glob("*.mp4"))
    if not matches:
        raise RuntimeError("yt-dlp did not produce a merged output video file")
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


def get_video_info(url: str, outdir: Path) -> VideoInfo:
    video_path = download(url, outdir)
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

