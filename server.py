#!/usr/bin/env python3
"""Loopback dashboard server with a private match-summary service."""
import json
import os
import re
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from decision_analysis.service import handle_get as decision_get, handle_post as decision_post
from decision_analysis.agents import run as run_bound_agents, configuration
from decision_analysis.service import repository
from video_review.service import handle_upload as video_upload, handle_get as video_get, handle_post as video_post
from decision.outcome import review_record
from decision.agents import run_team
from decision.rollout import simulate
from decision.engine import analyze as analyze_decision, review as review_decision
from analysis_agent import build_report
from model_service import narrate, validate_base_url

ROOT = Path(__file__).resolve().parent
CONFIG = Path(os.environ.get('NEXTPLAY_STATE_DIR', str(ROOT / '.local'))) / 'model-service.json'
LOCK = threading.Lock()
AGENT_SLOT = threading.BoundedSemaphore(1)
DEFAULTS = {'base_url': os.getenv('NEXTPLAY_MODEL_BASE_URL', os.getenv('ITG_MODEL_BASE_URL', '')), 'model': os.getenv('NEXTPLAY_MODEL', os.getenv('ITG_MODEL_NAME', '')), 'api_key': os.getenv('NEXTPLAY_MODEL_API_KEY', os.getenv('ITG_MODEL_API_KEY', ''))}


def read_config():
    saved = {**DEFAULTS, **json.loads(CONFIG.read_text())} if CONFIG.exists() else DEFAULTS.copy()
    return configuration(saved)


def public_config(config):
    return {k: config[k] for k in ('base_url', 'model')} | {'has_key': bool(config['api_key'])}


def save_config(data):
    with LOCK:
        config = read_config()
        config['base_url'] = validate_base_url(data.get('base_url', config['base_url']))
        model = data.get('model', config['model'])
        key = data.get('api_key', '')
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError('Enter a model name.')
        if not isinstance(key, str) or len(key) > 4096 or any(c in key for c in '\r\n'):
            raise ValueError('Invalid API key.')
        if config['base_url'] != read_config()['base_url'] and not key.strip() and not data.get('clear_key'):
            raise ValueError('Enter the API key again when changing the service URL.')
        config['model'] = model.strip()
        if data.get('clear_key'):
            config['api_key'] = ''
        elif key.strip():
            config['api_key'] = key.strip()
        CONFIG.parent.mkdir(mode=0o700, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=CONFIG.parent, delete=False) as f:
            json.dump(config, f)
        os.replace(f.name, CONFIG)
        return public_config(config)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def trusted(self):
        host = self.headers.get('Host', '')
        public_origin = os.environ.get('NEXTPLAY_PUBLIC_ORIGIN', '').rstrip('/')
        if public_origin:
            origin = urlsplit(public_origin)
            return (origin.scheme == 'https' and host == origin.netloc
                    and self.headers.get('Origin', public_origin) == public_origin)
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        return host in allowed and self.headers.get('Origin', f'http://{host}') == f'http://{host}'

    def reply(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_head(self):
        if not self.trusted():
            self.send_error(403)
            return None
        path = Path(self.translate_path(self.path)).resolve()
        relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else None
        if relative is None or any(p.startswith('.') for p in relative.parts):
            self.send_error(404)
            return None
        if path.is_dir() and path != ROOT:
            self.send_error(404)
            return None
        return super().send_head()

    def do_GET(self):
        if urlsplit(self.path).path == '/healthz':
            self.reply(200, {'status': 'ready', 'service': 'nextplay'})
            return
        if video_get(self):return
        if urlsplit(self.path).path == '/api/decision-analysis/agent-status':
            if not self.trusted():
                self.reply(403, {'error': 'Same-origin requests only.'})
                return
            config = configuration(read_config())
            self.reply(200, {'configured': all(config.get(k) for k in ('base_url', 'model', 'api_key')),
                             'daily_call_limit': int(os.environ.get('NEXTPLAY_DAILY_MODEL_CALLS', '100'))})
            return
        if decision_get(self):return
        if urlsplit(self.path).path == '/api/model-settings':
            if not self.trusted() or os.environ.get('NEXTPLAY_PUBLIC_ORIGIN'):
                self.reply(403, {'error': 'Only same-origin local requests are accepted.'})
                return
            self.reply(200, public_config(read_config()))
        else:
            super().do_GET()

    def do_POST(self):
        if video_upload(self):return
        if not self.trusted() or self.headers.get('Content-Type') != 'application/json':
            self.reply(403, {'error': 'Only same-origin JSON requests are accepted.'})
            return
        try:
            route = urlsplit(self.path).path
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= (524288 if route.startswith('/api/video-review/') else 16384):
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object.')
            if os.environ.get('NEXTPLAY_PUBLIC_ORIGIN') and not route.startswith(('/api/decision-analysis/', '/api/video-review/')):
                self.reply(403, {'error': 'Legacy model routes and settings are disabled in public demo mode.'})
                return
            if route.startswith('/api/video-review/'):
                is_agent = route.endswith('/agents')
                if is_agent and not AGENT_SLOT.acquire(blocking=False):
                    self.reply(429, {'error': 'An agent review is already running.'})
                    return
                try:
                    with LOCK:
                        config = configuration(read_config())
                    video_post(self, route, data, repository(), config)
                finally:
                    if is_agent:AGENT_SLOT.release()
                return
            if route == '/api/decision-analysis/agents':
                if set(data) != {'request', 'candidate_set_id'}:
                    raise ValueError('Invalid bound request')
                if not AGENT_SLOT.acquire(blocking=False):
                    self.reply(429, {'error': 'An agent review is already running.'})
                    return
                try:
                    with LOCK:
                        config = configuration(read_config())
                    self.reply(200, run_bound_agents(data['request'], data['candidate_set_id'], config, repository()))
                finally:
                    AGENT_SLOT.release()
                return
            if decision_post(self, route, data):return
            if route == '/api/agent-review':
                if not AGENT_SLOT.acquire(blocking=False):
                    self.reply(429, {'error': 'An agent review is already running. Try again when it finishes.'})
                    return
                try:
                    with LOCK:
                        config = read_config()
                    result = run_team(data['frame'], data['metadata'], data.get('question', ''),
                                      data.get('mode', 'fan'), config, language=data.get('language', 'en'))
                    self.reply(200, result)
                finally:
                    AGENT_SLOT.release()
                return
            if route == '/api/rollout':
                self.reply(200, simulate(data['frame'], data['metadata'], data['action_id']))
                return
            if route == '/api/action-review':
                result = review_record(ROOT, data.get('dataset','league'), data.get('match_id',''), data.get('decision_id',''), data.get('replay_at_ms'))
                self.reply(200,result)
                return
            if route == '/api/decision':
                if data.get('mode', 'fan') not in ('fan', 'analyst'):
                    raise ValueError('Invalid audience mode.')
                report = analyze_decision(data['frame'], data['metadata'])
                self.reply(200, {**report, 'review': review_decision(report, data.get('mode', 'fan'))})
                return
            if route == '/api/model-settings':
                self.reply(200, save_config(data))
                return
            if route != '/api/match-summary':
                self.reply(404, {'error': 'Unknown endpoint.'})
                return
            match_id = data.get('match_id', '')
            if not isinstance(match_id, str) or not re.fullmatch(r'[A-Za-z0-9-]+', match_id):
                raise ValueError('Invalid match ID.')
            folder = ROOT / 'data' / 'league' / 'matches' / match_id
            if not folder.is_dir():
                raise ValueError('Match not found.')
            with LOCK:
                config = read_config()
            if not config['api_key'] or not config['model']:
                self.reply(400, {'error': 'Configure a model and API key in Settings first.'})
                return
            report = build_report(json.loads((folder / 'metadata.json').read_text()),
                                  json.loads((folder / 'summary.json').read_text()),
                                  [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines() if line.strip()])
            if report is None:
                raise ValueError('The match has not finished yet.')
            try:
                narrate(report, config['model'], config['api_key'], config['base_url'])
            except Exception:
                self.reply(502, {'error': 'Model service unavailable or returned an invalid report. Check your API key, model and service URL, then retry. Your existing report is unchanged.'})
                return
            with tempfile.NamedTemporaryFile(mode='w', dir=folder, suffix='.tmp', delete=False) as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            os.replace(f.name, folder / 'analysis.json')
            self.reply(200, report)
        except (ValueError, TypeError, KeyError, IndexError):
            self.reply(400, {'error': 'Invalid request. Check the snapshot, model settings or match ID.'})
        except Exception:
            self.reply(500, {'error': 'Unable to process the request.'})


if __name__ == '__main__':
    port=int(os.environ.get('TOUCHLINE_PORT','5173'))
    print(f'NextPlay AI: http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer((os.environ.get('TOUCHLINE_HOST', '127.0.0.1'), port), Handler).serve_forever()
