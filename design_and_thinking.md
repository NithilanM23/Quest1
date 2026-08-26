# Design & Architecture Thinking

**Author:** Nithilan M  
**Roll No:** 23110306  

---

## 1. Problem Understanding & Initial Exploration (24th Aug)

When first analyzing the problem statement — locating the exact frame of a dialogue within an arbitrary video URL — my mind went to Brave browser’s video summarization feature.

By looking into how they operate, I found a common pattern:
1. Pre-fetch the caption file provided along with the YouTube video.
2. Feed that caption file to an inbuilt LLM to generate a summary.

While this pattern is simple, it **breaks down immediately** when dealing with arbitrary video platforms (e.g., `ok.ru`, raw MP4 streams, or uncaptioned YouTube uploads) where no subtitle tracks exist. A robust system cannot rely solely on the presence of uploaded CC files.

### The Audio Processing Pipeline Approach

Processing entire video files at full resolution (1080p / 30–60 FPS) using computer vision or Vision-Language Models (VLMs) across a full-length video is computationally prohibitive and slow.

Instead, my approach is:
1. **Bandwidth Optimization**: Download and extract the audio stream separately to minimize bandwidth and compute.
2. **Acoustic ASR**: Transcribe the audio stream with local ASR to generate time-aligned text segments.
3. **Fuzzy Search**: Search for the target input phrase to locate the exact spoken occurrence.
4. **Targeted Visual Verification**: Use a narrow sliding window (±5s) around the target timestamp to inspect visual frames using OCR only if captions are burned into the video.
5. **Precise Frame Calculation**: Once the correct match and timestamp $T$ are derived, extract the exact frame using:
   $$\text{Estimated Frame} = \text{round}(T \times \text{FPS})$$

---

## 2. Technical Discoveries & Architecture Evolution (25th & 26th Aug)

### Issue A: Inbuilt Captions vs. Audio Desynchronization
During initial testing with videos that provided `.srt` files, I discovered two critical failure modes:
- **Low Transcription Quality**: Auto-generated YouTube CC frequently missed low-frequency words or suffered from truncation.
- **Audio-Visual Desync**: Spoken audio onset frequently drifted by $0.5 - 2.0\text{s}$ relative to the `.srt` timestamps.

> **Architecture Decision:** Rather than trusting caption tracks blindly, I shifted the primary source of truth to direct acoustic speech processing. Caption tracks are treated as a secondary heuristic, with ground truth anchored to audio-derived speech boundaries.

### Issue B: OCR Overhead vs. Reality
Running OCR across an entire video blindly is wasteful because most web videos do not have hardcoded (burned-in) subtitles.
- OCR was isolated strictly to a targeted verification pass. The system searches acoustically first, isolates a tightly bound temporal window, and only decodes frames within that window.

---

## 3. Core Optimizations

Instead of adding heavy dependencies, I focused on eliminating latency bottlenecks directly:

### 1. INT8 Model Quantization
Standard PyTorch Whisper in FP32 was the single largest computational bottleneck. Migrating to INT8 quantization (`ctranslate2` Faster-Whisper) reduced inference latency by roughly **4×** and slashed memory footprint, with no observable degradation in transcript quality.

### 2. Voice Activity Detection (VAD)
Real-world videos contain prolonged stretches of background music, ambient soundscapes, and silence. Feeding non-speech audio into Whisper wastes compute and introduces hallucinations. Using a Silero VAD filter before passing audio to Whisper ensures only active dialogue segments are decoded.

### 3. Streaming Early Exit
For long videos (e.g., 1-hour files), transcribing past the target phrase is unnecessary. The pipeline checks transcription chunks as they are generated. If a sliding-window match reaches $\ge 95\%$ similarity, the pipeline triggers an immediate early exit.

### 4. Noise Resilience & Denoising Trade-offs
Audio quality in arbitrary web uploads is rarely studio-grade (muffled audio, accents, sound effects):
- **RapidFuzz Partial Ratio**: Used Levenshtein edit distance and partial ratio token matching to handle noisy transcriptions.
- **Why Avoid Pre-processing Spectral Denoising?**: Adding aggressive denoising filters often introduces phase distortion and suppresses subtle speech phonemes, degrading transcription accuracy. Raw audio with VAD yielded far superior transcript fidelity.

---

## 4. Key Questions & Design Answers

### Q1: How the solution extracts text and determines where to look in the video
The system ingests the video URL and extracts a 16kHz mono WAV audio stream. Before passing audio to the Faster-Whisper transformer, a Voice Activity Detection (VAD) filter strips out silence and background music. Whisper decodes active speech into time-stamped word tokens, and a sliding-window fuzzy matcher scans the stream in real-time to isolate the exact moment the dialogue occurs.

### Q2: How it determines the relevant frame
During the ingestion stage, `ffprobe` probes the true video metadata to get the exact frame rate (FPS). Once the dialogue timestamp $T$ (in seconds) is identified from the acoustic ground truth:
$$\text{Frame Number} = \text{round}(T \times \text{FPS})$$
OpenCV then seeks directly to that frame index (`CAP_PROP_POS_FRAMES`) and extracts the frame as a PNG.

### Q3: How cases with ambiguous or uncertain results are handled
When audio is degraded or partially masked by background noise, fuzzy string similarity (Levenshtein edit distance) evaluates partial matches and token permutations. If no candidate exceeds the confidence threshold ($\ge 80\%$), the pipeline cleanly reports that the line was not found rather than hallucinating an incorrect frame.
