#!/usr/bin/env python3
"""clawd-connector HTTP server. Stdlib only.
Routes: / -> intro, /healthz -> status, /skills -> skill count/list,
/skill.md -> the packaged clawd skill, /connector.json -> manifest."""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE, 'skills')
SKILL_FILE = os.path.join(BASE, 'clawd', 'SKILL.md')
MANIFEST_FILE = os.path.join(BASE, 'connector.json')


def skill_dirs():
    if not os.path.isdir(SKILLS_DIR):
        return []
    return sorted(d for d in os.listdir(SKILLS_DIR)
                  if os.path.isdir(os.path.join(SKILLS_DIR, d)))


def manifest():
    try:
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    except Exception:
        return {"name": "clawd", "version": "3.9.1"}


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/', ''):
            self._json({
                "name": "clawd",
                "description": "The full Clawd agent stack as one installable skill",
                "skill": "clawd/SKILL.md",
                "version": manifest().get('version', '3.9.1'),
                "homepage": "https://musebook.trade",
                "endpoints": ["/healthz", "/skills", "/skill.md", "/connector.json"],
            })
        elif self.path == '/healthz':
            self._json({
                "status": "ok",
                "skill": "clawd",
                "version": manifest().get('version', '3.9.1'),
                "skills_installed": len(skill_dirs()),
            })
        elif self.path == '/skills':
            dirs = skill_dirs()
            self._json({"count": len(dirs), "skills": dirs})
        elif self.path == '/skill.md':
            if os.path.isfile(SKILL_FILE):
                with open(SKILL_FILE, 'rb') as f:
                    body = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/markdown; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._json({"error": "clawd/SKILL.md not installed"}, 404)
        elif self.path == '/connector.json':
            self._json(manifest())
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    srv = HTTPServer(('0.0.0.0', port), Handler)
    print(f'clawd-connector listening on :{port}', flush=True)
    srv.serve_forever()
