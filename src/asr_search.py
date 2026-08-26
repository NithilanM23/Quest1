"""Stage 1: Speech-to-Text & Dialogue Search

Performs automated speech recognition (ASR) on extracted audio using Faster-Whisper,
checks for embedded platform captions, and finds dialogue matches via fuzzy text matching.
"""
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional
from rapidfuzz import fuzz

from .types import Candidate

MATCH_THRESHOLD = 80.0


def _parse_vtt_or_srt(subs_path: Path) -> list[dict]:
    """Parse VTT/SRT subtitle files into structured cues: [{start, end, text}]."""
    text = subs_path.read_text(errors="ignore")
    blocks = re.split(r"\n\s*\n", text)
    cues = []
    time_re = re.compile(r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})")

    def to_sec(t: str) -> float:
        t = t.replace(",", ".")
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    for block in blocks:
        m = time_re.search(block)
        if not m:
            continue
        start, end = to_sec(m.group(1)), to_sec(m.group(2))
        lines = block.strip().splitlines()
        text_lines = [l for l in lines if "-->" not in l and not l.strip().isdigit()]
        cues.append({"start": start, "end": end, "text": " ".join(text_lines).strip()})
    return cues


def search_existing_subs(subs_path: Path, target_line: str) -> list[Candidate]:
    """Search pre-existing subtitle cues using fuzzy matching."""
    cues = _parse_vtt_or_srt(subs_path)
    candidates = []
    for cue in cues:
        score = fuzz.partial_ratio(target_line.lower(), cue["text"].lower())
        if score >= MATCH_THRESHOLD:
            candidates.append(Candidate(
                start_sec=cue["start"],
                end_sec=cue["end"],
                text=cue["text"],
                source="platform_caption",
                score=score,
            ))
    return sorted(candidates, key=lambda c: c.start_sec)


def transcribe_and_search(
    audio_path: Path,
    target_line: str,
    model_size: str = "small",
    total_duration: float = 0.0,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> list[Candidate]:
    """Transcribe audio with Faster-Whisper (INT8 quantized) and search for target dialogue.

    Optimizations:
    - INT8 quantization for fast CPU execution.
    - Voice Activity Detection (VAD) to skip silence/music.
    - Streaming sliding-window token matching.
    - Early-exit when a confident match (>=95%) is encountered.
    """
    from faster_whisper import WhisperModel

    start_time = time.time()
    threads = os.cpu_count() or 4

    if progress_cb:
        progress_cb({
            "type": "stage",
            "stage": "asr_init",
            "message": f"Initializing Faster-Whisper ({model_size}) on CPU with {threads} threads...",
        })
    print(f"      [ASR] Initializing Faster-Whisper ({model_size}) on CPU with {threads} threads...")

    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=threads)

    if progress_cb:
        progress_cb({
            "type": "stage",
            "stage": "asr_transcribe",
            "message": "Transcribing audio with Voice Activity Detection (VAD)...",
        })
    print("      [ASR] Transcribing audio with Voice Activity Detection (VAD)...")

    segments, info = model.transcribe(
        str(audio_path),
        language="en",
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    duration = total_duration or getattr(info, "duration", 0.0)
    words = []
    candidates = []
    target_word_count = len(target_line.split())
    window = max(target_word_count, 3)

    last_logged_pct = -1

    for seg in segments:
        seg_pct = min(100.0, (seg.end / duration * 100.0)) if duration > 0 else 0.0
        elapsed = time.time() - start_time
        eta_sec = (elapsed / (seg_pct / 100.0) - elapsed) if seg_pct > 2.0 else 0.0

        m_curr, s_curr = int(seg.end // 60), int(seg.end % 60)
        m_start, s_start = int(seg.start // 60), int(seg.start % 60)
        m_tot, s_tot = int(duration // 60), int(duration % 60) if duration > 0 else (0, 0)
        minute_str = f"{m_curr:02d}:{s_curr:02d}"
        total_time_str = f"{m_tot:02d}:{s_tot:02d}"
        time_range_str = f"{m_start:02d}:{s_start:02d} - {m_curr:02d}:{s_curr:02d}"

        if progress_cb:
            progress_cb({
                "type": "asr_progress",
                "pct": round(seg_pct, 1),
                "current_sec": round(seg.end, 2),
                "duration_sec": round(duration, 2),
                "minute_str": minute_str,
                "total_time_str": total_time_str,
                "time_range_str": time_range_str,
                "elapsed_sec": round(elapsed, 1),
                "eta_sec": round(max(0.0, eta_sec), 1),
                "current_text": seg.text.strip(),
            })

        if int(seg_pct) != last_logged_pct and int(seg_pct) % 5 == 0:
            last_logged_pct = int(seg_pct)
            print(f"      [ASR Progress] {seg_pct:.1f}% ({minute_str} / {total_time_str}) — \"{seg.text.strip()[:40]}\"", flush=True)

        if seg.words:
            for w in seg.words:
                words.append(w)
                # Streaming sliding window match
                if len(words) >= window:
                    span = words[-window:]
                    span_text = " ".join(w.word.strip() for w in span)
                    score = fuzz.partial_ratio(target_line.lower(), span_text.lower())
                    if score >= MATCH_THRESHOLD:
                        cand = Candidate(
                            start_sec=span[0].start,
                            end_sec=span[-1].end,
                            text=span_text,
                            source="audio_speech",
                            score=score,
                        )
                        candidates.append(cand)
                        ts_m, ts_s = int(cand.start_sec // 60), int(cand.start_sec % 60)
                        print(f"      [ASR Match Found @ {ts_m:02d}:{ts_s:02d} | Score: {score:.1f}%] \"{span_text}\"", flush=True)
                        if progress_cb:
                            progress_cb({
                                "type": "asr_match",
                                "start_sec": cand.start_sec,
                                "score": score,
                                "text": span_text,
                                "timestamp": f"{ts_m:02d}:{ts_s:02d}",
                            })

        # Early exit optimization: stop if a highly confident match (>=95%) is found
        if candidates and any(c.score >= 95.0 for c in candidates):
            print("      [ASR] High confidence match found (>=95%). Stopping early scan.", flush=True)
            if progress_cb:
                progress_cb({
                    "type": "stage",
                    "stage": "asr_early_exit",
                    "message": "High confidence match found (>=95%). Finalizing ASR...",
                })
            break

    # Collapse overlapping candidates within 2 seconds, keeping the highest score
    candidates.sort(key=lambda c: c.start_sec)
    merged: list[Candidate] = []
    for c in candidates:
        if merged and c.start_sec - merged[-1].end_sec < 2.0:
            if c.score > merged[-1].score:
                merged[-1] = c
        else:
            merged.append(c)
    return merged


def find_audio_candidates(
    video_info,
    target_line: str,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> tuple[Candidate | None, list[Candidate], dict]:
    """Finds candidates across audio Whisper transcription and optional embedded platform subtitles."""
    if progress_cb:
        progress_cb({"type": "stage", "stage": "asr_start", "message": "Running Faster-Whisper ASR on audio track..."})
    print("      [1/2] Running Faster-Whisper ASR on audio track...")
    audio_candidates = transcribe_and_search(
        video_info.audio_path,
        target_line,
        total_duration=video_info.duration_sec,
        progress_cb=progress_cb,
    )

    caption_candidates = []
    if video_info.has_subs and video_info.subs_path:
        if progress_cb:
            progress_cb({"type": "stage", "stage": "captions_check", "message": "Checking inbuilt platform transcription/captions..."})
        print("      [2/2] Checking inbuilt platform transcription/captions...")
        caption_candidates = search_existing_subs(video_info.subs_path, target_line)
    else:
        if progress_cb:
            progress_cb({"type": "stage", "stage": "captions_none", "message": "No inbuilt platform transcription found. Relying on audio Whisper."})
        print("      [2/2] No inbuilt platform transcription found. Relying on audio Whisper.")

    comparison = {
        "audio_speech_found": len(audio_candidates) > 0,
        "platform_captions_found": len(caption_candidates) > 0,
        "audio_timestamp": None,
        "caption_timestamp": None,
        "delta_sec": None,
        "note": "",
    }

    if audio_candidates:
        best_audio = max(audio_candidates, key=lambda c: c.score)
        m_a, s_a = int(best_audio.start_sec // 60), best_audio.start_sec % 60
        comparison["audio_timestamp"] = f"{m_a:02d}:{s_a:06.3f}"
        print(f"      -> Audio Speech: \"{best_audio.text}\" @ {comparison['audio_timestamp']} (Score: {best_audio.score:.1f}%)")

    if caption_candidates:
        best_caption = max(caption_candidates, key=lambda c: c.score)
        m_c, s_c = int(best_caption.start_sec // 60), best_caption.start_sec % 60
        comparison["caption_timestamp"] = f"{m_c:02d}:{s_c:06.3f}"
        print(f"      -> Platform Caption: \"{best_caption.text}\" @ {comparison['caption_timestamp']} (Score: {best_caption.score:.1f}%)")

    if audio_candidates and caption_candidates:
        best_audio = max(audio_candidates, key=lambda c: c.score)
        best_caption = max(caption_candidates, key=lambda c: c.score)
        delta = abs(best_audio.start_sec - best_caption.start_sec)
        comparison["delta_sec"] = round(delta, 3)
        if delta > 1.5:
            comparison["note"] = f"Timing discrepancy: Spoken audio occurs at {comparison['audio_timestamp']}, but caption cue appears at {comparison['caption_timestamp']} (delta: {delta:.2f}s)"
            print(f"      [!] {comparison['note']}")
        else:
            comparison["note"] = f"Audio speech and captions are in sync within {delta:.2f}s."
            print(f"      [+] {comparison['note']}")

    all_candidates = sorted(audio_candidates + caption_candidates, key=lambda c: c.start_sec)

    # Priority: audio speech timestamp is the ground truth for when words are spoken
    best = None
    if audio_candidates:
        best = max(audio_candidates, key=lambda c: c.score)
    elif caption_candidates:
        best = max(caption_candidates, key=lambda c: c.score)

    return best, all_candidates, comparison
