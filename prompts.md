# Engineering Prompts & Design Process

**Author:** Nithilan M  
**Roll No:** 23110306  

---

## Overview

Gemini and Antigravity were the only AI coding assistants used during this project.

Before using either tool, I independently analyzed the problem statement and documented an initial solution approach in a text editor. I then provided both the problem statement and my proposed approach to Gemini to refine the design, evaluate technology choices, and identify potential failure cases.

The AI tools were therefore used as engineering assistants rather than as the source of the initial solution. The architecture evolved through implementation, testing, and debugging, with several design decisions being changed after issues were encountered on real video URLs.

The following sections document the major prompts that guided the design and implementation process.

---

## Prompts & Iterations

### Prompt 1: Initial Problem Analysis & Conceptual Architecture
> "So first I thought of downloading the vid along with its audio for the link given (any vid url, not only YouTube). Then Check if the transcription is readily available, if yes then the job is easy. We can just check the matching string for the first occurrence and its timestamp and get the vid frame. If the CC transcription is not available, i just need to extract the audio and convert that to text using some transformer and get the text along with its timestamp back. Then use the same string matching. But what if the audio or the transformer arch is not that great and mediocre. Then we must find the most relevant match and use a sliding window like +-3 sec on that timestamp and check the text and find out.  
> Next is if the subtitles are printed on the vid itself, then use the same audio approach, then after we get the approx. timestamp window, we use OCR to scan the frames, we can use skip 24 frames or 30 depending on the FPS of the vid. Then visually confirm the word phrase is occurring there.  
> This is the basic approach I had, I don’t know about what tech stack to use to do these things, first lets refine the idea."

---

### Prompt 2: Technology Stack Evaluation & Comparison
> "For the solution I provide, let’s discuss what technology stack can be used and its alternatives. Give me the best tech to use in each step of my sol by comparing it with its alternative and tell why it’s better."

---

### Prompt 3: Environment Setup
> "Now give the requirements.txt file content, so I can first create a venv after you decide the stack."

---

### Prompt 4: Antigravity Master Implementation Prompt
> "Now give a master prompt for antigravity to implement my solution with the tech stack we decided on, make sure it follows all the correct coding principle and good practices."

---

### Prompt 5: Performance Benchmarking
> "Give me the estimated time for running my pipeline for a 1 hr video."

---

### Prompt 6: Ingestion Bottleneck Optimization
> "Broo, that’s soo expensive, ig downloading the vid in high quality is the bottleneck, how can we mitigate that."

---

### Prompt 7: ASR Bottleneck & Quantization Strategy
> "Nah my bad, the audio processing is the actual bottleneck. Is there some way to use a efficient model, I used quantized version of llama for my daily task. Search for some quantized version of the whisper so it can be done efficiently."

---

### Prompt 8: Additional Pipeline Optimizations
> "Except for quantization what other optimizations can we use?"

---

### Prompt 9: Subtitle Drift & Ground Truth Realization
> "Ji, I found a hole in my solution. When the vid has inbuilt CC, it is somewhat delayed or not correctly synced with the audio spoken. So let’s always run the audio processing pipeline even when .srt file is present. Then we can cross check both and display the delay of CC aswell (like a extra additional feature). Fix this now."

---

### Prompt 10: Interactive Modern Web Frontend
> "As of now we are only gonna run the baseline_audio file, Make a classy sleek modern frontend for this using only HTML, CSS, JS. it should take the url, show all the processing steps with ETA and loading bars, then after result is generated, it should print the json result and also display the video frame. Plan first, wait till I approve the plan, then only start to code."

---

### Prompt 11: Live Minute Tracking & Dialogue Streaming
> "While transcibing in the UI it would be good to show the exact minute and the text it transcipted, so that users won’t feel stuck at a same position."

---

### Prompt 12: Testing & Sanity Check
> "Do a final sanity check and do some testing also of the code generated so far."

---

### Prompt 13: Zero-Touch Windows Packaging & Runner
> "Fine now the UI and solution is done, now I have an idea to pack it as a zero-touch installer and give the .exe file alone to the user. It should open in cmd and start creating a venv and install all the dependencies and start in a available localhost port."

---

## Debugging & Edge-Case Resolution

While testing with various video formats and platforms (including `ok.ru` and `youtube.com`), each video source revealed different edge cases (e.g., SSL connection drops, missing subtitle streams, Variable Bitrate fragment estimates, and missing codecs). 

These edge cases were solved iteratively by feeding real-time tracebacks and logs into the AI assistants to arrive at a resilient, production-ready solution.
