#!/usr/bin/env python3
"""Static file server with an auto-generated manifest of flow folders.

Run: python3 server.py [port]

It serves the current directory like `python -m http.server`, plus a
`/api/manifest` endpoint that returns JSON describing every top-level
folder and the image files inside it. The web page reads this endpoint so
folders/images are detected automatically - no code edits when things are
renamed, added, or removed.
"""

import json
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def natural_key(name):
    """Sort filenames so 2.PNG comes before 10.PNG."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def build_manifest(root):
    folders = []
    for entry in sorted(os.scandir(root), key=lambda e: natural_key(e.name)):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        images = [
            f.name
            for f in os.scandir(entry.path)
            if f.is_file() and os.path.splitext(f.name)[1].lower() in IMAGE_EXTENSIONS
        ]
        if not images:
            continue
        images.sort(key=natural_key)
        folders.append({"name": entry.name, "images": images})
    return {"folders": folders}


def write_manifest_js(root, manifest):
    """Keep manifest.js in sync so the offline (zip) version is always current."""
    payload = json.dumps(manifest, indent=2, ensure_ascii=False)
    content = (
        "// Auto-generated - kept in sync by server.py / generate_manifest.py.\n"
        "window.FLOW_MANIFEST = " + payload + ";\n"
    )
    path = os.path.join(root, "manifest.js")
    try:
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == content:
                return
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/manifest":
            manifest = build_manifest(os.getcwd())
            # Regenerate manifest.js on every load so a rename/add is captured
            # for the offline build without running any extra command.
            write_manifest_js(os.getcwd(), manifest)
            payload = json.dumps(manifest).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self):
        # Avoid the browser caching stale images.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving on http://localhost:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
