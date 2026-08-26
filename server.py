"""Backend server for Dialogue Frame Finder (Baseline Audio).

Provides:
- Web static files serving (HTML/CSS/JS in /public)
- Output image and file serving (/output/*)
- Real-time Server-Sent Events (SSE) streaming on /api/stream?url=...&line=...
- Samples & history on /api/samples
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
import traceback
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Ensure base directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Reconfigure stdout/stderr for utf-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from baseline_audio import run_audio_baseline

PUBLIC_DIR = BASE_DIR / "public"
OUTPUT_DIR = BASE_DIR / "output"

PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class AppRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self):
        # Allow CORS and prevent caching for development
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            return self._serve_file(PUBLIC_DIR / "index.html", "text/html; charset=utf-8")

        elif path.startswith("/public/"):
            rel_path = path[len("/public/"):]
            file_path = PUBLIC_DIR / rel_path
            return self._serve_file(file_path)

        elif path.startswith("/output/"):
            rel_path = path[len("/output/"):]
            file_path = OUTPUT_DIR / rel_path
            return self._serve_file(file_path)

        elif path == "/api/samples":
            return self._handle_samples()

        elif path == "/api/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return

        elif path == "/api/stream":
            return self._handle_stream(parsed.query)

        else:
            # Fallback to default handler
            super().do_GET()

    def _serve_file(self, file_path: Path, content_type: str | None = None):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, f"File not found: {file_path.name}")
            return

        ext_to_mime = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".wav": "audio/wav",
            ".mp4": "video/mp4",
        }

        mime = content_type or ext_to_mime.get(file_path.suffix.lower(), "application/octet-stream")
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            if file_path.suffix in {".png", ".jpg", ".jpeg", ".mp4"}:
                self.send_header("Cache-Control", "public, max-age=3600")
            else:
                self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading file: {e}")

    def _handle_samples(self):
        samples = [
            {
                "title": "Sherlock Holmes (ok.ru)",
                "url": "https://ok.ru/video/248244667877",
                "line": "My mind rebels at stagnation",
                "tag": "ok.ru Full Movie",
            },
            {
                "title": "Steve Jobs Stanford Speech",
                "url": "https://www.youtube.com/watch?v=UF8uR6Z6KLc",
                "line": "Stay hungry. Stay foolish.",
                "tag": "YouTube Keynote",
            },
            {
                "title": "Short Clip Test",
                "url": "https://www.youtube.com/watch?v=8s2ODsSscWo",
                "line": "Hello world",
                "tag": "YouTube Clip",
            }
        ]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(samples).encode("utf-8"))

    def _handle_stream(self, query_string: str):
        params = parse_qs(query_string)
        url = params.get("url", [""])[0].strip()
        line = params.get("line", [""])[0].strip()

        if not url or not line:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing 'url' or 'line' query parameter"}).encode("utf-8"))
            return

        # Setup SSE headers
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        event_queue = queue.Queue()
        done_flag = threading.Event()

        def push_event(event_data: dict):
            event_queue.put(event_data)

        def worker():
            try:
                push_event({"type": "stage", "stage": "init", "message": f"Starting job for URL: {url}"})
                res = run_audio_baseline(
                    url=url,
                    target_line=line,
                    outdir=str(OUTPUT_DIR),
                    progress_cb=push_event,
                )
                if not res:
                    push_event({"type": "error", "message": f"Dialogue line '{line}' was not found in the audio or captions."})
            except Exception as exc:
                push_event({"type": "error", "message": f"Pipeline failed: {str(exc)}"})
            finally:
                done_flag.set()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        try:
            while not done_flag.is_set() or not event_queue.empty():
                try:
                    event = event_queue.get(timeout=0.25)
                    payload = f"data: {json.dumps(event)}\n\n"
                    self.wfile.write(payload.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Heartbeat comment to keep connection alive
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            print("[-] Client disconnected from SSE stream.")
        except Exception as e:
            print(f"[-] SSE Stream error: {e}")


def run_server(port: int = 8000, host: str = "0.0.0.0"):
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, AppRequestHandler)
    print(f"==================================================")
    print(f"[*] Dialogue Frame Finder UI Server Running!")
    print(f"[*] Local Access:   http://localhost:{port}")
    print(f"[*] Network Access: http://127.0.0.1:{port}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] Server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Dialogue Frame Finder Web Server")
        parser.add_argument("--port", type=int, default=8000, help="Port to run on (default: 8000)")
        parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
        args = parser.parse_args()
        run_server(port=args.port, host=args.host)
    except Exception as e:
        sys.stderr.write(f"\n[FATAL SERVER ERROR] {e}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)
