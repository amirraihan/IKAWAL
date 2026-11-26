import asyncio
import json
import logging
import os
import ssl
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

from . import store
from .agent import answer
from .reman import summarize

ROOT = Path(__file__).resolve().parent.parent
MODELS = ('deepseek-ai/deepseek-v4.1-flash', 'qwen2.5:32b', 'gpt-oss:20b', 'llama3.2:3b')
VPN_BASE = 'https://litellm.htp-ai-ai-application.awanheitech.local/v1'


def model_missing(response):
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        return False
    error = payload.get('error', {}) if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        return False
    code = str(error.get('code', '')).lower()
    message = str(error.get('message', '')).lower()
    return code in {'model_not_found', 'model_not_available'} or any(phrase in message for phrase in ('model not found', 'model does not exist', 'unknown model'))


@dataclass
class Settings:
    base_url: str = VPN_BASE
    api_key: str = ''
    model: str = MODELS[0]
    ca_file: str = str(ROOT / 'certs/pcai-ca.crt')
    auth_mode: str = 'local'
    public_url: str = ''
    reman_file: str = ''
    tool_models: tuple = MODELS[:2]

    @classmethod
    def load(cls):
        path = ROOT / '.local/app.json'
        values = json.loads(path.read_text()) if path.exists() else {}
        for name in ('base_url', 'api_key', 'model', 'ca_file', 'auth_mode', 'public_url', 'reman_file'):
            if (value := os.getenv('APP_' + name.upper())) is not None:
                values[name] = value
        settings = cls(**values)
        settings.base_url = settings.base_url.rstrip('/')
        url = urlsplit(settings.base_url)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('LiteLLM base URL must be an HTTP(S) URL without embedded credentials.')
        if url.scheme == 'http' and url.hostname != 'litellm.litellm.svc.cluster.local':
            raise ValueError('Plain HTTP is supported only for the supplied in-cluster LiteLLM service.')
        if settings.auth_mode not in ('local', 'proxy'):
            raise ValueError('APP_AUTH_MODE must be local or proxy.')
        if settings.auth_mode == 'proxy' and urlsplit(settings.public_url).scheme != 'https':
            raise ValueError('Proxy mode needs the HTTPS public app URL.')
        if settings.model not in MODELS:
            raise ValueError('Choose one of the four configured LiteLLM chat models.')
        return settings


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=8000)


class Chat(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=1, max_length=8000)
    history: list[Message] = Field(default_factory=list, max_length=8)


def create_app(settings=None, transport=None):
    settings = settings or Settings.load()
    limits = asyncio.Semaphore(4)

    @asynccontextmanager
    async def lifespan(app):
        trust = ssl.create_default_context()
        if settings.ca_file:
            trust.load_verify_locations(cafile=settings.ca_file)
        async with httpx.AsyncClient(verify=trust, transport=transport, follow_redirects=False, timeout=httpx.Timeout(120, connect=10), trust_env=False) as client:
            app.state.gateway = client
            yield

    app = FastAPI(title='HPE PCAI starter', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def identity(request, call_next):
        if request.url.path not in ('/health/live', '/health/ready') and settings.auth_mode == 'proxy':
            if not request.headers.get('x-forwarded-user'):
                return JSONResponse({'detail': 'Sign in through the application URL.'}, status_code=401)
            if request.method == 'POST' and request.headers.get('origin') != settings.public_url.rstrip('/'):
                return JSONResponse({'detail': 'Request origin is not allowed.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.get('/health/live')
    async def live():
        return {'status': 'alive'}

    @app.get('/health/ready')
    async def ready():
        return JSONResponse({'status': 'ready' if settings.api_key else 'key missing'}, status_code=200 if settings.api_key else 503)

    @app.get('/')
    async def index():
        return FileResponse(ROOT / 'app/static/index.html')

    @app.get('/app.js')
    async def javascript():
        return FileResponse(ROOT / 'app/static/app.js', media_type='application/javascript')

    @app.get('/app.css')
    async def stylesheet():
        return FileResponse(ROOT / 'app/static/app.css', media_type='text/css')

    @app.get('/api/info')
    async def info(request: Request):
        return {'model': settings.model, 'tools_enabled': settings.model in settings.tool_models, 'identity': request.headers.get('x-forwarded-preferred-username', 'Local workshop user'), 'auth_mode': settings.auth_mode}

    def register(today):
        try:
            return store.load_from_settings(ROOT, settings.reman_file, today)
        except store.RegisterMissing as exc:
            raise HTTPException(503, str(exc))

    def filters(request):
        params = request.query_params
        return {
            'label': params.get('label', '').strip(),
            'depot': params.get('depot', '').strip().upper(),
            'officer': params.get('officer', '').strip().upper(),
            'status': params.get('status', '').strip(),
            'query': params.get('q', '').strip().upper(),
            'open_only': params.get('open', '') in ('1', 'true', 'yes'),
        }

    @app.get('/api/uc2/summary')
    async def uc2_summary():
        today = date.today()
        path, cases = register(today)
        data = summarize(cases)
        return {'file': path.name, 'generated': today.isoformat(), **data}

    @app.get('/api/uc2/cases')
    async def uc2_cases(request: Request):
        today = date.today()
        path, cases = register(today)
        active = filters(request)
        selected = []
        for case in cases:
            if active['label'] and case.label != active['label']:
                continue
            if active['depot'] and case.depot.upper() != active['depot']:
                continue
            if active['officer'] and active['officer'] not in case.nama_pegawai.upper():
                continue
            if active['status'] and case.status_reman != active['status']:
                continue
            if active['query'] and active['query'] not in case.no_reman.upper() and active['query'] not in case.nama.upper():
                continue
            if active['open_only'] and case.status_reman in ('selesai', 'tidak sah'):
                continue
            selected.append(case)
        selected.sort(key=lambda c: (-c.score, c.hari_berbaki if c.hari_berbaki is not None else 9999, c.no_reman))
        try:
            limit = max(1, min(int(request.query_params.get('limit', '200')), 1000))
        except ValueError:
            raise HTTPException(422, 'limit must be a whole number.')
        return {'file': path.name, 'generated': today.isoformat(), 'total': len(selected), 'shown': min(limit, len(selected)), 'cases': [c.to_public() for c in selected[:limit]]}

    @app.get('/api/uc2/case/{no_reman}')
    async def uc2_case(no_reman: str):
        today = date.today()
        path, cases = register(today)
        key = no_reman.strip().upper()
        matches = [c for c in cases if c.no_reman.upper() == key]
        if not matches:
            raise HTTPException(404, 'No case with that NO.REMAN was found.')
        return {'file': path.name, 'generated': today.isoformat(), 'duplicates': len(matches) - 1, 'case': matches[0].to_public()}

    @app.post('/api/chat')
    async def chat(request: Request):
        if not settings.api_key:
            raise HTTPException(503, 'Run Setup App.cmd and enter your LiteLLM key.')
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                raise HTTPException(413, 'The conversation is too large. Start a new chat.')
        try:
            data = Chat.model_validate_json(body)
        except ValidationError:
            raise HTTPException(422, 'Enter a prompt up to 8,000 characters with at most eight recent messages.')
        try:
            async with asyncio.timeout(180), limits:
                try:
                    _, cases = store.load_from_settings(ROOT, settings.reman_file, date.today())
                except store.RegisterMissing:
                    cases = []
                return await answer(request.app.state.gateway, settings, data.prompt, [m.model_dump() for m in data.history], cases)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logging.getLogger('pcai').warning('LiteLLM request failed with HTTP %d for model %s; response body omitted.', status, settings.model)
            if status in (401, 403):
                detail = 'LiteLLM rejected the key or model access. In LiteLLM, create a virtual key without selecting a team, or allow this exact model on the key. Then run Setup App.cmd again.'
            elif status == 404 or (status == 400 and model_missing(exc.response)):
                detail = f'LiteLLM could not find model {settings.model} for this request. Confirm the VPN endpoint ends in /v1, this exact model is deployed, and your virtual key was created without a team or allows this model. Then run Setup App.cmd again.'
            elif status == 400:
                detail = 'LiteLLM rejected the chat request. Check the selected model and ask the LiteLLM administrator to review the gateway policy.'
            else:
                detail = 'LiteLLM could not complete the request. Check the LiteLLM service and try again.'
            raise HTTPException(502, detail)
        except (httpx.RequestError, TimeoutError):
            raise HTTPException(504, 'Cannot reach LiteLLM. Check VPN, certificates, and endpoint access.')
        except (KeyError, IndexError, TypeError, ValueError):
            logging.getLogger('pcai').warning('Unexpected model response; response body omitted.')
            raise HTTPException(502, 'The model returned an unsupported response. Try DeepSeek or Qwen2.5.')

    return app


app = create_app()
