"""Baseline Audio-only Dialogue Frame Finder
Extracts dialogue timestamps from audio using Faster-Whisper and calculates approximate frame number.
Each video run is isolated in its own subfolder inside the output directory.
"""
import argparse
import json
from pathlib import Path
import cv2

from src.ingest import get_video_info, get_video_folder_name
from src.asr_search import find_audio_candidates


def seconds_to_timestamp(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def save_frame_at_index(video_path: Path, frame_number: int, out_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read frame at index {frame_number}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), frame)
    return out_path


from typing import Callable, Optional


def run_audio_baseline(
    url: str,
    target_line: str,
    outdir: str,
    folder: str | None = None,
    progress_cb: Optional[Callable[[dict], None]] = None,
):
    # Determine per-video folder name
    subfolder_name = folder or get_video_folder_name(url)
    target_outdir = Path(outdir) / subfolder_name
    target_outdir.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb({"type": "stage", "stage": "ingest_start", "message": f"Downloading video & extracting audio from {url}..."})
    print(f"\n==========================================")
    print(f"[Stage 0] Ingestion: {url}")
    print(f"Destination Folder: {target_outdir}")
    print(f"==========================================")
    info = get_video_info(url, target_outdir, progress_cb=progress_cb)
    print(f"Video Info:")
    print(f"  FPS: {info.fps:.3f}")
    print(f"  Duration: {info.duration_sec:.2f}s ({int(info.duration_sec//60)}m {int(info.duration_sec%60)}s)")
    print(f"  Resolution: {info.width}x{info.height}")
    print(f"  Embedded Subtitles Available: {info.has_subs}")

    if progress_cb:
        progress_cb({
            "type": "video_info",
            "fps": info.fps,
            "duration_sec": info.duration_sec,
            "width": info.width,
            "height": info.height,
            "has_subs": info.has_subs,
            "folder": subfolder_name,
        })

    print(f"\n==========================================")
    print(f"[Stage 1] ASR Audio Search for: '{target_line}'")
    print(f"==========================================")
    best, all_candidates, comparison = find_audio_candidates(info, target_line, progress_cb=progress_cb)

    if not best:
        print("\n[-] No matching dialogue found in audio or captions.")
        if progress_cb:
            progress_cb({"type": "error", "message": f"No dialogue match found for: '{target_line}'"})
        return None

    if progress_cb:
        progress_cb({"type": "stage", "stage": "extract_frame", "message": "Capturing target video frame image..."})

    ts_sec = best.start_sec
    timestamp_str = seconds_to_timestamp(ts_sec)
    frame_number = int(round(ts_sec * info.fps))
    frame_img_path = target_outdir / f"frame_{frame_number}.png"

    # Extract the frame image
    save_frame_at_index(info.video_path, frame_number, frame_img_path)

    # Minimum required output format
    print(f"\n==========================================")
    print(f"OUTPUT RESULT:")
    print(f"==========================================")
    print(f"Timestamp : {timestamp_str}")
    print(f"Frame     : {frame_number}")
    print(f"Text      : \"{best.text}\"")
    print(f"Image     : {frame_img_path}")

    if comparison["audio_timestamp"] and comparison["caption_timestamp"]:
        print(f"\n--- Cross-Reference Summary ---")
        print(f"  Spoken Audio Time : {comparison['audio_timestamp']}")
        print(f"  Inbuilt Caption   : {comparison['caption_timestamp']}")
        if comparison["delta_sec"]:
            print(f"  Offset / Delta    : {comparison['delta_sec']}s")
        if comparison["note"]:
            print(f"  Analysis          : {comparison['note']}")

    relative_image_path = f"/output/{subfolder_name}/frame_{frame_number}.png"

    result_data = {
        "timestamp": timestamp_str,
        "timestamp_sec": ts_sec,
        "frame_number": frame_number,
        "extracted_text": best.text,
        "source": best.source,
        "target_line": target_line,
        "similarity_score": round(best.score, 2),
        "video_fps": round(info.fps, 3),
        "video_duration_sec": round(info.duration_sec, 2),
        "frame_image": str(frame_img_path),
        "frame_image_url": relative_image_path,
        "source_url": url,
        "cross_reference": comparison,
    }

    result_json_path = target_outdir / "result.json"
    with open(result_json_path, "w") as f:
        json.dump(result_data, f, indent=2)

    print(f"\n[+] Full result saved to: {result_json_path}")
    if progress_cb:
        progress_cb({"type": "complete", "result": result_data})

    return result_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baseline Audio-only Dialogue Frame Finder")
    parser.add_argument("--url", required=True, help="Video URL (YouTube, ok.ru, Vimeo, direct link)")
    parser.add_argument("--line", required=True, help="Target dialogue to find")
    parser.add_argument("--outdir", default="./output", help="Root output directory (default: ./output)")
    parser.add_argument("--folder", default=None, help="Custom subfolder name (optional)")
    args = parser.parse_args()

    run_audio_baseline(args.url, args.line, args.outdir, args.folder)

