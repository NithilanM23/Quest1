/**
 * Dialogue Frame Finder — Frontend Controller
 * Handles SSE streaming, real-time stage transitions, ETA calculation,
 * results rendering, and interactive UI utilities.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const searchForm = document.getElementById('searchForm');
  const videoUrlInput = document.getElementById('videoUrl');
  const dialogueLineInput = document.getElementById('dialogueLine');
  const sampleChips = document.getElementById('sampleChips');
  const btnSubmit = document.getElementById('btnSubmit');
  const btnReset = document.getElementById('btnReset');
  const btnText = document.getElementById('btnText');
  const systemStatus = document.getElementById('systemStatus');

  // Progress Section
  const progressSection = document.getElementById('progressSection');
  const currentActionText = document.getElementById('currentActionText');
  const overallProgressBar = document.getElementById('overallProgressBar');
  const progressBarGlow = document.getElementById('progressBarGlow');
  const overallProgressPct = document.getElementById('overallProgressPct');
  const elapsedTimer = document.getElementById('elapsedTimer');
  const etaTimer = document.getElementById('etaTimer');

  // Stepper Elements
  const stepIngest = document.getElementById('step-ingest');
  const stepAudio = document.getElementById('step-audio');
  const stepAsr = document.getElementById('step-asr');
  const stepSync = document.getElementById('step-sync');
  const stepFrame = document.getElementById('step-frame');
  const asrLiveBox = document.getElementById('asrLiveBox');
  const asrSubFill = document.getElementById('asrSubFill');
  const asrTickerText = document.getElementById('asrTickerText');

  // Live Transcription Monitor
  const liveTranscriptionCard = document.getElementById('liveTranscriptionCard');
  const asrMinutePill = document.getElementById('asrMinutePill');
  const asrPctPill = document.getElementById('asrPctPill');
  const speakingTimeTag = document.getElementById('speakingTimeTag');
  const speakingCurrentText = document.getElementById('speakingCurrentText');
  const transcriptFeedContainer = document.getElementById('transcriptFeedContainer');
  const feedEmptyHint = document.getElementById('feedEmptyHint');
  const feedCount = document.getElementById('feedCount');
  let transcribedSegmentCount = 0;
  let lastAppendedText = '';

  // Download Progress Elements
  const downloadPctBadge = document.getElementById('downloadPctBadge');
  const downloadLiveBox = document.getElementById('downloadLiveBox');
  const downloadSubFill = document.getElementById('downloadSubFill');
  const downloadMetaSize = document.getElementById('downloadMetaSize');
  const downloadMetaSpeed = document.getElementById('downloadMetaSpeed');

  // Terminal Logs
  const terminalDrawer = document.getElementById('terminalDrawer');
  const terminalToggle = document.getElementById('terminalToggle');
  const terminalLogs = document.getElementById('terminalLogs');
  const logCount = document.getElementById('logCount');

  // Results Section
  const resultsSection = document.getElementById('resultsSection');
  const resultSubtitle = document.getElementById('resultSubtitle');
  const resultFrameImg = document.getElementById('resultFrameImg');
  const resBadgeTimestamp = document.getElementById('resBadgeTimestamp');
  const resBadgeScore = document.getElementById('resBadgeScore');
  const resBadgeFrame = document.getElementById('resBadgeFrame');
  const resBadgeSource = document.getElementById('resBadgeSource');
  const btnDownloadFrame = document.getElementById('btnDownloadFrame');
  const resTargetLine = document.getElementById('resTargetLine');
  const resExtractedText = document.getElementById('resExtractedText');
  const syncAudioTime = document.getElementById('syncAudioTime');
  const syncCaptionTime = document.getElementById('syncCaptionTime');
  const syncDelta = document.getElementById('syncDelta');
  const syncNote = document.getElementById('syncNote');
  const specFrame = document.getElementById('specFrame');
  const specSec = document.getElementById('specSec');
  const specFps = document.getElementById('specFps');
  const specDuration = document.getElementById('specDuration');
  const jsonOutput = document.getElementById('jsonOutput');
  const btnCopyJson = document.getElementById('btnCopyJson');
  const copyJsonText = document.getElementById('copyJsonText');

  // Lightbox Modal
  const framePreviewWrap = document.getElementById('framePreviewWrap');
  const lightboxModal = document.getElementById('lightboxModal');
  const lightboxImg = document.getElementById('lightboxImg');
  const lightboxCaption = document.getElementById('lightboxCaption');
  const modalClose = document.getElementById('modalClose');

  // Toast
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toastMsg');

  // State Variables
  let eventSource = null;
  let timerInterval = null;
  let startTime = 0;
  let totalEventsCount = 0;
  let currentResultData = null;

  // Initialize
  initSampleChips();
  initTerminalToggle();
  initLightbox();
  initCopyJson();
  initReset();

  // Search Form Submit
  searchForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const url = videoUrlInput.value.trim();
    const line = dialogueLineInput.value.trim();

    if (!url || !line) {
      showToast('Please provide both video URL and target dialogue.');
      return;
    }

    startPipeline(url, line);
  });

  // Start Pipeline Job
  function startPipeline(url, line) {
    if (eventSource) {
      eventSource.close();
    }

    // Reset UI state
    resetPipelineUI();
    setRunningState(true);

    // Show Progress Section
    progressSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    progressSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    startTime = Date.now();
    timerInterval = setInterval(updateElapsedTimer, 500);

    const streamUrl = `/api/stream?url=${encodeURIComponent(url)}&line=${encodeURIComponent(line)}`;
    eventSource = new EventSource(streamUrl);

    appendLog('system', `Connecting to pipeline stream for: "${line}"`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleStreamEvent(data);
      } catch (err) {
        console.error('Error parsing SSE event data:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE stream disconnected or error:', err);
      if (eventSource.readyState === EventSource.CLOSED) {
        setRunningState(false);
      }
    };
  }

  // Format bytes to human readable string
  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // Handle Incoming SSE Stream Events
  function handleStreamEvent(data) {
    totalEventsCount++;
    logCount.textContent = `${totalEventsCount} event${totalEventsCount === 1 ? '' : 's'}`;

    switch (data.type) {
      case 'download_progress':
        handleDownloadProgress(data);
        break;

      case 'stage':
        handleStageUpdate(data);
        break;

      case 'video_info':
        handleVideoInfo(data);
        break;

      case 'asr_progress':
        handleAsrProgress(data);
        break;

      case 'asr_match':
        handleAsrMatch(data);
        break;

      case 'complete':
        handleComplete(data.result);
        break;

      case 'error':
        handleError(data.message);
        break;

      default:
        appendLog('info', JSON.stringify(data));
        break;
    }
  }

  // Live Download Progress Handler
  function handleDownloadProgress(data) {
    downloadLiveBox.classList.remove('hidden');
    downloadPctBadge.classList.remove('hidden');

    const pct = Math.max(0, Math.min(100, data.pct || 0));
    downloadPctBadge.textContent = `${pct.toFixed(1)}%`;
    downloadSubFill.style.width = `${pct}%`;

    // Map download progress (0-100%) to initial overall progress (5% -> 20%)
    const overallPct = 5 + (pct * 0.15);
    setProgress(overallPct);

    if (data.is_cache) {
      document.getElementById('step-ingest-desc').textContent = 'Using cached local video stream';
      downloadMetaSize.textContent = '⚡ Cached media';
      downloadMetaSpeed.textContent = 'Ready';
      return;
    }

    const downloadedStr = formatBytes(data.downloaded_bytes);
    const totalStr = data.total_bytes > 0 ? formatBytes(data.total_bytes) : 'Estimating...';
    downloadMetaSize.textContent = `${downloadedStr} / ${totalStr}`;

    if (data.speed_bytes > 0) {
      const speedStr = `${formatBytes(data.speed_bytes)}/s`;
      downloadMetaSpeed.textContent = speedStr;
      currentActionText.textContent = `Downloading video: ${pct.toFixed(1)}% (${downloadedStr} / ${totalStr} @ ${speedStr})`;
    } else {
      currentActionText.textContent = `Downloading video: ${pct.toFixed(1)}% (${downloadedStr} / ${totalStr})`;
    }

    if (data.eta_sec && data.eta_sec > 0) {
      updateEtaDisplay(data.eta_sec + 10);
    }
  }

  // Stage Transitions
  function handleStageUpdate(data) {
    currentActionText.textContent = data.message;
    appendLog('stage', data.message);

    if (data.stage === 'ingest_start') {
      setStepState(stepIngest, 'active');
      downloadLiveBox.classList.remove('hidden');
      downloadPctBadge.classList.remove('hidden');
      setProgress(5);
    } else if (data.stage === 'audio_extract') {
      setStepState(stepIngest, 'completed');
      setStepState(stepAudio, 'active');
      downloadPctBadge.textContent = '100%';
      downloadSubFill.style.width = '100%';
      downloadMetaSpeed.textContent = 'Completed';
      setProgress(20);
    } else if (data.stage === 'asr_init' || data.stage === 'asr_start') {
      setStepState(stepIngest, 'completed');
      setStepState(stepAudio, 'completed');
      setStepState(stepAsr, 'active');
      asrLiveBox.classList.remove('hidden');
      setProgress(25);
    } else if (data.stage === 'asr_early_exit') {
      setProgress(75);
    } else if (data.stage === 'captions_check' || data.stage === 'captions_none') {
      setStepState(stepAsr, 'completed');
      setStepState(stepSync, 'active');
      setProgress(85);
    } else if (data.stage === 'extract_frame') {
      setStepState(stepSync, 'completed');
      setStepState(stepFrame, 'active');
      setProgress(95);
    }
  }

  function handleVideoInfo(data) {
    appendLog('info', `Video Probed: ${data.width}x${data.height} @ ${data.fps.toFixed(2)} FPS | Duration: ${formatDuration(data.duration_sec)}`);
    document.getElementById('step-ingest-desc').textContent = `${data.width}x${data.height} • ${data.fps.toFixed(2)} FPS • ${formatDuration(data.duration_sec)}`;
  }

  function handleAsrProgress(data) {
    // Map ASR progress (0-100%) to overall progress bar (25% -> 80%)
    const mappedPct = 25 + (data.pct * 0.55);
    setProgress(mappedPct);

    // Sub-bar inside Step 3
    asrSubFill.style.width = `${data.pct}%`;
    if (data.current_text) {
      asrTickerText.textContent = `"${data.current_text}"`;
    }

    // Update Live ASR Monitor Header Badges
    const minuteStr = data.minute_str || formatDurationSeconds(Math.floor(data.current_sec || 0));
    const totalStr = data.total_time_str || formatDurationSeconds(Math.floor(data.duration_sec || 0));
    asrMinutePill.textContent = `⏱ ${minuteStr} / ${totalStr}`;
    asrPctPill.textContent = `${data.pct.toFixed(1)}%`;

    // Update Active Highlight Box
    speakingTimeTag.textContent = `Scanning Audio @ [${minuteStr}] (${data.pct.toFixed(1)}%)`;
    if (data.current_text) {
      speakingCurrentText.textContent = `"${data.current_text}"`;

      // Append to rolling transcript stream if new
      if (data.current_text !== lastAppendedText) {
        lastAppendedText = data.current_text;
        transcribedSegmentCount++;
        feedCount.textContent = `${transcribedSegmentCount} segment${transcribedSegmentCount === 1 ? '' : 's'}`;

        if (feedEmptyHint) {
          feedEmptyHint.style.display = 'none';
        }

        const feedItem = document.createElement('div');
        feedItem.className = 'feed-item';
        feedItem.id = `feed-seg-${transcribedSegmentCount}`;
        feedItem.innerHTML = `
          <span class="feed-item-time">[${minuteStr}]</span>
          <span class="feed-item-text">${escapeHtml(data.current_text)}</span>
        `;
        transcriptFeedContainer.appendChild(feedItem);
        transcriptFeedContainer.scrollTop = transcriptFeedContainer.scrollHeight;
      }
    }

    // Format ETA
    if (data.eta_sec > 0) {
      etaTimer.textContent = formatDurationSeconds(data.eta_sec);
    } else {
      etaTimer.textContent = 'Finishing...';
    }
  }

  function handleAsrMatch(data) {
    appendLog('match', `[Match Found @ ${data.timestamp} | ${data.score.toFixed(1)}%] "${data.text}"`);
    showToast(`Match detected at ${data.timestamp} (${data.score.toFixed(1)}%)`);

    // Highlight the latest item in transcript feed
    const latestItem = transcriptFeedContainer.lastElementChild;
    if (latestItem && latestItem.classList.contains('feed-item')) {
      latestItem.classList.add('match-highlight');
    }
  }

  function handleComplete(result) {
    currentResultData = result;
    setProgress(100);
    setStepState(stepFrame, 'completed');
    setRunningState(false);
    etaTimer.textContent = 'Done';
    currentActionText.textContent = 'Extraction complete!';

    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    clearInterval(timerInterval);

    appendLog('match', `Pipeline finished successfully! Frame #${result.frame_number} at ${result.timestamp}`);

    renderResults(result);
  }

  function handleError(msg) {
    setRunningState(false);
    systemStatus.className = 'badge status-badge error';
    systemStatus.querySelector('.status-text').textContent = 'Error';
    currentActionText.textContent = msg;
    appendLog('error', `[ERROR] ${msg}`);
    showToast(msg);

    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    clearInterval(timerInterval);
  }

  // Render Result Showcase
  function renderResults(res) {
    resultsSection.classList.remove('hidden');

    // Badges & Media
    resultFrameImg.src = res.frame_image_url || res.frame_image;
    resBadgeTimestamp.textContent = res.timestamp;
    resBadgeScore.textContent = `${res.similarity_score}% Match`;
    resBadgeFrame.textContent = `Frame #${res.frame_number}`;
    resBadgeSource.textContent = res.source;

    btnDownloadFrame.href = res.frame_image_url || res.frame_image;
    btnDownloadFrame.download = `frame_${res.frame_number}.png`;

    // Dialogue strings
    resTargetLine.textContent = `"${res.target_line}"`;
    resExtractedText.textContent = `"${res.extracted_text}"`;

    // Cross-Reference Sync
    const cross = res.cross_reference || {};
    syncAudioTime.textContent = cross.audio_timestamp || '--:--.---';
    syncCaptionTime.textContent = cross.caption_timestamp || 'None';
    syncDelta.textContent = cross.delta_sec ? `${cross.delta_sec}s` : '0.00s';
    syncNote.textContent = cross.note || 'Cross-validation complete.';

    // Specs
    specFrame.textContent = `#${res.frame_number}`;
    specSec.textContent = `${res.timestamp_sec.toFixed(3)}s`;
    specFps.textContent = `${res.video_fps.toFixed(2)} FPS`;
    specDuration.textContent = formatDuration(res.video_duration_sec);

    // Syntax-highlighted JSON Result
    jsonOutput.innerHTML = syntaxHighlightJson(res);

    // Scroll to results
    setTimeout(() => {
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);
  }

  // Helper: Syntax Highlighting for JSON
  function syntaxHighlightJson(json) {
    if (typeof json !== 'string') {
      json = JSON.stringify(json, null, 2);
    }
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
      let cls = 'json-number';
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'json-key';
        } else {
          cls = 'json-string';
        }
      } else if (/true|false/.test(match)) {
        cls = 'json-boolean';
      } else if (/null/.test(match)) {
        cls = 'json-null';
      }
      return `<span class="${cls}">${match}</span>`;
    });
  }

  // UI Utilities
  function setProgress(pct) {
    const clamped = Math.min(100, Math.max(0, pct));
    overallProgressBar.style.width = `${clamped}%`;
    progressBarGlow.style.left = `${clamped}%`;
    overallProgressPct.textContent = `${Math.round(clamped)}%`;
  }

  function setStepState(element, state) {
    element.classList.remove('active', 'completed');
    if (state) {
      element.classList.add(state);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function resetPipelineUI() {
    setProgress(0);
    etaTimer.textContent = 'Estimating...';
    elapsedTimer.textContent = 'Elapsed: 00:00';
    currentActionText.textContent = 'Initializing...';
    terminalLogs.innerHTML = '';
    totalEventsCount = 0;
    logCount.textContent = '0 events';

    // Reset Live ASR Monitor
    asrMinutePill.textContent = '⏱ 00:00 / 00:00';
    asrPctPill.textContent = '0.0%';
    speakingTimeTag.textContent = 'Current Segment:';
    speakingCurrentText.textContent = '"Waiting for speech segments..."';
    transcriptFeedContainer.innerHTML = '<div class="feed-empty-hint" id="feedEmptyHint">Transcribed dialogue segments will appear here with exact timestamps...</div>';
    transcribedSegmentCount = 0;
    lastAppendedText = '';
    feedCount.textContent = '0 segments';

    [stepIngest, stepAudio, stepAsr, stepSync, stepFrame].forEach((s) => {
      s.classList.remove('active', 'completed');
    });
    downloadPctBadge.classList.add('hidden');
    downloadLiveBox.classList.add('hidden');
    downloadSubFill.style.width = '0%';
    downloadPctBadge.textContent = '0%';
    downloadMetaSize.textContent = '0 MB / 0 MB';
    downloadMetaSpeed.textContent = '-- MB/s';
    document.getElementById('step-ingest-desc').textContent = 'Downloading stream & probing metadata';

    asrLiveBox.classList.add('hidden');
    asrSubFill.style.width = '0%';
    asrTickerText.textContent = '"..."';
  }

  function setRunningState(isRunning) {
    if (isRunning) {
      btnSubmit.disabled = true;
      btnSubmit.classList.add('loading');
      btnText.textContent = 'Locating Dialogue Frame...';
      systemStatus.className = 'badge status-badge running';
      systemStatus.querySelector('.status-text').textContent = 'Processing';
    } else {
      btnSubmit.disabled = false;
      btnSubmit.classList.remove('loading');
      btnText.textContent = 'Locate Dialogue Frame';
      systemStatus.className = 'badge status-badge';
      systemStatus.querySelector('.status-text').textContent = 'Engine Ready';
    }
  }

  function updateElapsedTimer() {
    const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
    elapsedTimer.textContent = `Elapsed: ${formatDurationSeconds(elapsedSec)}`;
  }

  function formatDurationSeconds(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function formatDuration(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}m ${s}s`;
  }

  function appendLog(type, text) {
    const now = new Date().toTimeString().split(' ')[0];
    const line = document.createElement('span');
    line.className = 'log-line';

    if (type === 'stage') {
      line.innerHTML = `<span class="log-time">[${now}]</span><span class="log-stage">●</span>${text}`;
    } else if (type === 'match') {
      line.innerHTML = `<span class="log-time">[${now}]</span><span class="log-match">★</span>${text}`;
    } else if (type === 'error') {
      line.innerHTML = `<span class="log-time">[${now}]</span><span class="log-error">✖</span>${text}`;
    } else {
      line.innerHTML = `<span class="log-time">[${now}]</span>${text}`;
    }

    terminalLogs.appendChild(line);
    const body = document.getElementById('terminalBody');
    body.scrollTop = body.scrollHeight;
  }

  // Interactive Sample Chips
  function initSampleChips() {
    const chips = sampleChips.querySelectorAll('.chip');
    chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        chips.forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        videoUrlInput.value = chip.getAttribute('data-url');
        dialogueLineInput.value = chip.getAttribute('data-line');
      });
    });
  }

  // Terminal Toggle
  function initTerminalToggle() {
    terminalToggle.addEventListener('click', () => {
      const drawer = terminalToggle.closest('.terminal-drawer');
      drawer.classList.toggle('collapsed');
    });
  }

  // Lightbox Modal
  function initLightbox() {
    framePreviewWrap.addEventListener('click', () => {
      if (!resultFrameImg.src) return;
      lightboxImg.src = resultFrameImg.src;
      lightboxCaption.textContent = `${resBadgeTimestamp.textContent} • ${resBadgeFrame.textContent} • ${resTargetLine.textContent}`;
      lightboxModal.classList.remove('hidden');
    });

    modalClose.addEventListener('click', () => {
      lightboxModal.classList.add('hidden');
    });

    lightboxModal.addEventListener('click', (e) => {
      if (e.target === lightboxModal) {
        lightboxModal.classList.add('hidden');
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !lightboxModal.classList.contains('hidden')) {
        lightboxModal.classList.add('hidden');
      }
    });
  }

  // Copy JSON Button
  function initCopyJson() {
    btnCopyJson.addEventListener('click', () => {
      if (!currentResultData) return;
      const text = JSON.stringify(currentResultData, null, 2);
      navigator.clipboard.writeText(text).then(() => {
        copyJsonText.textContent = 'Copied!';
        showToast('JSON copied to clipboard!');
        setTimeout(() => {
          copyJsonText.textContent = 'Copy JSON';
        }, 2000);
      });
    });
  }

  // Reset Button
  function initReset() {
    btnReset.addEventListener('click', () => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      clearInterval(timerInterval);
      setRunningState(false);
      videoUrlInput.value = '';
      dialogueLineInput.value = '';
      progressSection.classList.add('hidden');
      resultsSection.classList.add('hidden');
      showToast('Form reset');
    });
  }

  // Toast Helper
  function showToast(msg) {
    toastMsg.textContent = msg;
    toast.classList.remove('hidden');
    setTimeout(() => {
      toast.classList.add('hidden');
    }, 3500);
  }
});
