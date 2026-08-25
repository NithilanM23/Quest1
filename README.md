# Dialogue Frame Finder

A lightweight tool that takes any video URL and a line of dialogue, finds the exact moment it was spoken, and grabs that exact video frame.

Works with YouTube, ok.ru, Vimeo, or direct video links.

---

## Why I Built It This Way

When thinking about how to find where a dialogue appears in a video:
1. **Why not just use YouTube captions?** 
   Not all videos are on YouTube (like ok.ru or Vimeo), and even on YouTube, auto-generated captions are often out of sync with the actual spoken voice by a few seconds. So we process the actual audio track directly to get the real spoken timestamp. If platform captions are available, we cross-check them against the audio to verify timing.
2. **Why not scan every frame with OCR?**
   Running OCR across thousands of video frames is very slow, and most videos don't have burned-in subtitles anyway. Focusing on audio first makes it way faster and reliable for spoken dialogue.

---

## How It Works

1. **Download & Probe (`src/ingest.py`)**:
   - Uses `yt-dlp` to get the video and any available subtitle tracks.
   - Runs `ffprobe` to get the real video FPS and duration so frame numbers are accurate.
2. **Audio Extraction (`src/ingest.py`)**:
   - Converts the audio track to 16kHz mono WAV using `ffmpeg`.
3. **Speech Recognition & Matching (`src/asr_search.py`)**:
   - Transcribes the audio using **Faster-Whisper** with word-level timestamps.
   - Matches the target line using fuzzy string matching (`rapidfuzz`) so small typos or transcription noise don't break the search.
4. **Frame Capture (`baseline_audio.py`)**:
   - Calculates the exact frame index (`timestamp * FPS`) and saves the image as a `.png`.

---

## Optimizations

- **INT8 Quantization**: Runs quantized Faster-Whisper on CPU so it runs quickly without needing a dedicated GPU.
- **Voice Activity Detection (VAD)**: Skips silence, background music, and sound effects so Whisper only spends time decoding actual speech.
- **Streaming Early Exit**: Checks the dialogue match while streaming segments. If it finds a $\ge 95\%$ match, it stops decoding immediately instead of waiting to finish the whole video.
- **Fuzzy Token Matching**: Uses partial ratio matching instead of strict string equality to handle background noise, accents, and minor transcription differences.

---

## Quickstart

### 1. Install Requirements

Make sure `ffmpeg` is installed on your system, then install the Python dependencies:

```bash
python -m venv venv
# On Windows: venv\Scripts\activate
# On Linux/macOS: source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run via CLI

```bash
python baseline_audio.py --url "https://ok.ru/video/248244667877" --line "My mind rebels at stagnation"
```

The output frame and results will be saved under the `./output/<video_name>/` folder.

### 3. Run with the Web UI

Start the local web server:

```bash
python server.py --port 8000
```

Open `http://localhost:8000` in your browser. You can type in any URL and line of dialogue, watch real-time transcription with live minute tracking and progress bars, view the extracted frame image, and copy the formatted JSON result.

---

## Example Output

When a match is found, you get a `result.json` and a saved image:

```json
{
  "timestamp": "00:05:25.180",
  "timestamp_sec": 325.18,
  "frame_number": 7797,
  "extracted_text": "My mind rebels at stagnation.",
  "target_line": "My mind rebels at stagnation",
  "similarity_score": 100.0,
  "video_fps": 23.98,
  "video_duration_sec": 3261.78,
  "frame_image": "output/ok_ru_248244667877/frame_7797.png",
  "cross_reference": {
    "audio_timestamp": "05:25.180",
    "caption_timestamp": null,
    "delta_sec": null,
    "note": ""
  }
}
```

---

## Project Structure

```
.
├── baseline_audio.py    # Main CLI entry point
├── server.py            # Local backend server with real-time SSE streaming
├── public/              # Web UI (HTML, CSS, JS)
├── src/
│   ├── ingest.py        # Video/audio download & ffprobe metadata
│   ├── asr_search.py    # Whisper transcription + fuzzy search
│   └── types.py         # Data types and models
└── output/              # Extracted frames and result.json files
```
