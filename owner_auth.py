"""Owner-only ASGI transport boundary for the optional Railway entrypoint.

No Streamlit internals, provider calls, persistent credentials, or auth cookies
from the legacy local-profile helper are used. One process/replica is required.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
from http.cookies import SimpleCookie
import os
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit

SESSION_COOKIE = '__Host-aba_owner'
CSRF_COOKIE = '__Host-aba_owner_csrf'
LOGIN_PATH = '/_owner/login'
LOGOUT_PATH = '/_owner/logout'
HEALTH_PATH = '/_owner/health'
SESSION_SECONDS = 3600
CSRF_SECONDS = 300
MAX_SESSIONS = 8
MAX_CONSUMED_CSRF = 32
MAX_BODY = 4096


@dataclass(frozen=True)
class OwnerConfig:
    username: str
    origin: str
    host: str
    salt: bytes
    digest: bytes
    fingerprint: str


def read_config(environ=None) -> OwnerConfig | None:
    env = os.environ if environ is None else environ
    username = env.get('ABA_OWNER_USERNAME', '')
    encoded = env.get('ABA_OWNER_PASSWORD_HASH', '')
    origin = env.get('ABA_OWNER_ORIGIN', '')
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,128}', username):
        return None
    match = re.fullmatch(r'pbkdf2_sha256\$600000\$([a-f0-9]{32})\$([a-f0-9]{64})', encoded)
    try:
        parsed = urlsplit(origin)
        valid_origin = (parsed.scheme == 'https' and parsed.hostname and parsed.port != 0
                        and not parsed.username and not parsed.password
                        and not parsed.path and not parsed.query and not parsed.fragment
                        and re.fullmatch(r'[a-z0-9.-]+(?::[0-9]{1,5})?', parsed.netloc))
    except ValueError:
        return None
    if not match or not valid_origin:
        return None
    fingerprint = hashlib.sha256((username + '\0' + encoded + '\0' + origin).encode()).hexdigest()
    return OwnerConfig(username, origin, parsed.netloc, bytes.fromhex(match[1]), bytes.fromhex(match[2]), fingerprint)


def password_matches(config: OwnerConfig, username: str, password: str) -> bool:
    if not 16 <= len(password) <= 1024:
        return False
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), config.salt, 600000)
    return hmac.compare_digest(digest, config.digest) & hmac.compare_digest(username.encode(), config.username.encode())


def _cookie(name, value, *, clear=False):
    return (f'{name}={value}; Path=/; Secure; HttpOnly; SameSite=Strict; '
            f'Max-Age={0 if clear else (SESSION_SECONDS if name == SESSION_COOKIE else CSRF_SECONDS)}').encode()


def _headers(scope):
    """Reject ambiguous security headers rather than guessing duplicate values."""
    result = {}
    for key, value in scope.get('headers', []):
        name = key.lower()
        if name in result and name in {b'host', b'origin', b'cookie', b'content-type'}:
            return {}
        result[name] = value.decode('latin1')
    return result


def _cookies(headers):
    try:
        jar = SimpleCookie()
        jar.load(headers.get(b'cookie', ''))
        return {name: item.value for name, item in jar.items()}
    except Exception:
        return {}


class _Revoked(Exception):
    pass


class OwnerAuthMiddleware:
    def __init__(self, app, *, environ=None, clock=None):
        self.app = app
        self.environ = environ
        self.clock = clock or time.monotonic
        self.fingerprint = None
        self.sessions = {}  # opaque random token -> (expiry, fingerprint, csrf)
        self.csrf_key = secrets.token_bytes(32)
        self.consumed_csrf = {}  # consumed challenge digest -> expiry; never evict live entries
        self.attempts = deque(maxlen=5)

    def _config(self):
        config = read_config(self.environ)
        fingerprint = config.fingerprint if config else None
        if fingerprint != self.fingerprint:
            self.sessions.clear()
            self.consumed_csrf.clear()
            self.csrf_key = secrets.token_bytes(32)
            self.fingerprint = fingerprint
        now = self.clock()
        self.sessions = {k: v for k, v in self.sessions.items() if v[0] > now}
        self.consumed_csrf = {k: v for k, v in self.consumed_csrf.items() if v > now}
        return config

    def _valid(self, token, fingerprint):
        config = self._config()
        session = self.sessions.get(token)
        return bool(config and config.fingerprint == fingerprint and session
                    and session[1] == fingerprint and session[0] > self.clock())

    async def _respond(self, send, status, body='', extra=()):
        headers = [(b'content-type', b'text/html; charset=utf-8'),
                   (b'cache-control', b'no-store'), (b'pragma', b'no-cache'),
                   (b'x-content-type-options', b'nosniff'),
                   (b'content-security-policy', b"default-src 'none'; form-action 'self'; frame-ancestors 'none'"),
                   *extra]
        await send({'type': 'http.response.start', 'status': status, 'headers': headers})
        await send({'type': 'http.response.body', 'body': body.encode()})

    async def _form(self, receive, headers):
        if headers.get(b'content-type', '').split(';')[0].strip() != 'application/x-www-form-urlencoded':
            return None
        data = bytearray()
        deadline = asyncio.get_running_loop().time() + 5
        chunks = 0
        while True:
            chunks += 1
            if chunks > 64:
                return None
            try:
                message = await asyncio.wait_for(receive(), timeout=max(0, deadline - asyncio.get_running_loop().time()))
            except asyncio.TimeoutError:
                return None
            if message['type'] != 'http.request':
                return None
            data.extend(message.get('body', b''))
            if len(data) > MAX_BODY:
                return None
            if not message.get('more_body'):
                break
        try:
            fields = parse_qs(data.decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=3)
            if any(len(values) != 1 for values in fields.values()):
                return None
            return {key: values[0] for key, values in fields.items()}
        except (ValueError, UnicodeError):
            return None

    async def __call__(self, scope, receive, send):
        kind = scope['type']
        if kind not in {'http', 'websocket'}:
            return await self.app(scope, receive, send)
        config = self._config()
        path = scope.get('path', '')
        method = scope.get('method', '')
        if kind == 'http' and path == HEALTH_PATH and method in {'GET', 'HEAD'}:
            return await self._respond(send, 200 if config else 503, '' if method == 'HEAD' else ('ok' if config else 'unavailable'))
        if not config:
            if kind == 'websocket':
                return await send({'type': 'websocket.close', 'code': 1008})
            return await self._respond(send, 503, 'Owner access is not configured. Contact the operator.')
        headers = _headers(scope)
        origin = headers.get(b'origin')
        # Never trust forwarded host/proto/client headers. Host and browser Origin
        # must match the operator-configured HTTPS public origin.
        if headers.get(b'host') != config.host or (origin is not None and origin != config.origin):
            if kind == 'websocket':
                return await send({'type': 'websocket.close', 'code': 1008})
            return await self._respond(send, 403, 'Request not allowed.')
        cookies = _cookies(headers)
        token = cookies.get(SESSION_COOKIE, '')
        valid = self._valid(token, config.fingerprint)
        if kind == 'websocket':
            if not valid or origin != config.origin:
                return await send({'type': 'websocket.close', 'code': 1008})
            return await self._websocket(scope, receive, send, token, config.fingerprint)
        if path == LOGIN_PATH:
            return await self._login(scope, receive, send, headers, cookies, config)
        if path == LOGOUT_PATH:
            if not valid:
                return await self._respond(send, 401, 'Sign in required.')
            csrf = self.sessions[token][2]
            if method == 'GET':
                return await self._respond(send, 200, f'<h1>Sign out</h1><form method="post" action="{LOGOUT_PATH}"><input type="hidden" name="csrf" value="{csrf}"><button>Sign out</button></form>')
            form = await self._form(receive, headers) if method == 'POST' and origin == config.origin else None
            if not form or not hmac.compare_digest(form.get('csrf', '').encode(), csrf.encode()):
                return await self._respond(send, 403, 'Request not allowed.')
            self.sessions.pop(token, None)
            return await self._respond(send, 303, extra=[(b'location', LOGIN_PATH.encode()), (b'set-cookie', _cookie(SESSION_COOKIE, '', clear=True))])
        if not valid:
            if path == '/' and method == 'GET':
                return await self._respond(send, 303, extra=[(b'location', LOGIN_PATH.encode())])
            return await self._respond(send, 401, 'Sign in required.')
        if method not in {'GET', 'HEAD', 'OPTIONS'} and origin != config.origin:
            return await self._respond(send, 403, 'Request not allowed.')
        started = False
        async def protected_send(message):
            nonlocal started
            if not self._valid(token, config.fingerprint):
                raise _Revoked()
            if message['type'] == 'http.response.start':
                message = dict(message)
                message['headers'] = [(k, v) for k, v in message.get('headers', []) if k.lower() not in {b'cache-control', b'pragma'}] + [(b'cache-control', b'no-store'), (b'pragma', b'no-cache')]
                started = True
            await send(message)
        async def protected_receive():
            if not self._valid(token, config.fingerprint):
                raise _Revoked()
            message = await receive()
            if not self._valid(token, config.fingerprint):
                raise _Revoked()
            return message
        try:
            await self.app(scope, protected_receive, protected_send)
        except _Revoked:
            if started:
                await send({'type': 'http.response.body', 'body': b''})
            else:
                await self._respond(send, 401, 'Sign in required.')

    def _challenge_expiry(self, token, config):
        match = re.fullmatch(r'v1\.([0-9]{1,20})\.([A-Za-z0-9_-]{43})\.([a-f0-9]{64})', token)
        if not match:
            return None
        issued = int(match[1])
        now = self.clock()
        if issued > now or issued + CSRF_SECONDS <= now:
            return None
        payload = token.rsplit('.', 1)[0]
        expected = hmac.new(self.csrf_key, (config.fingerprint + '.' + payload).encode(), hashlib.sha256).hexdigest()
        return issued + CSRF_SECONDS if hmac.compare_digest(match[3], expected) else None

    async def _login(self, scope, receive, send, headers, cookies, config):
        if scope['method'] == 'GET':
            payload = f'v1.{int(self.clock())}.{secrets.token_urlsafe(32)}'
            signature = hmac.new(self.csrf_key, (config.fingerprint + '.' + payload).encode(), hashlib.sha256).hexdigest()
            nonce = payload + '.' + signature
            body = f'<h1>ABA owner sign-in</h1><form method="post" action="{LOGIN_PATH}"><input type="hidden" name="csrf" value="{nonce}"><label>Owner <input name="username" autocomplete="username" maxlength="128" required></label><label>Password <input name="password" type="password" autocomplete="current-password" maxlength="1024" required></label><button>Sign in</button></form>'
            return await self._respond(send, 200, body, [(b'set-cookie', _cookie(CSRF_COOKIE, nonce))])
        if scope['method'] != 'POST':
            return await self._respond(send, 405, 'Method not allowed.')
        if headers.get(b'origin') != config.origin:
            return await self._respond(send, 403, 'Request not allowed.')
        form = await self._form(receive, headers)
        nonce = cookies.get(CSRF_COOKIE, '')
        expiry = self._challenge_expiry(nonce, config)
        nonce_digest = hashlib.sha256(nonce.encode()).hexdigest()
        if (not form or expiry is None
                or not hmac.compare_digest(form.get('csrf', '').encode(), nonce.encode())
                or nonce_digest in self.consumed_csrf):
            return await self._respond(send, 403, 'Request not allowed. Reload sign-in to retry.')
        now = self.clock()
        if (len(self.attempts) == 5 and now - self.attempts[0] < 60) or len(self.consumed_csrf) >= MAX_CONSUMED_CSRF:
            return await self._respond(send, 429, 'Too many attempts. Wait one minute and reload sign-in.', [(b'retry-after', b'60')])
        # These reservations are atomic within the ASGI event loop: no await
        # between replay check, rate reservation and consumption. Even concurrent
        # requests cannot verify the same challenge twice.
        self.attempts.append(now)
        self.consumed_csrf[nonce_digest] = expiry
        accepted = await asyncio.to_thread(password_matches, config, form.get('username', ''), form.get('password', ''))
        current = self._config()
        if not accepted or not current or current.fingerprint != config.fingerprint:
            return await self._respond(send, 401, 'Sign-in failed. Reload sign-in to retry.')
        old = cookies.get(SESSION_COOKIE, '')
        self.sessions.pop(old, None)
        if len(self.sessions) >= MAX_SESSIONS:
            self.sessions.pop(next(iter(self.sessions)))
        token = secrets.token_urlsafe(32)
        self.sessions[token] = (self.clock() + SESSION_SECONDS, config.fingerprint, secrets.token_urlsafe(32))
        return await self._respond(send, 303, extra=[(b'location', b'/'), (b'set-cookie', _cookie(SESSION_COOKIE, token)), (b'set-cookie', _cookie(CSRF_COOKIE, '', clear=True))])

    async def _websocket(self, scope, receive, send, token, fingerprint):
        closed = False
        async def close():
            nonlocal closed
            if not closed:
                closed = True
                await send({'type': 'websocket.close', 'code': 1008})
        async def protected_send(message):
            if not self._valid(token, fingerprint):
                raise _Revoked()
            await send(message)
        async def protected_receive():
            if not self._valid(token, fingerprint):
                raise _Revoked()
            message = await receive()
            if not self._valid(token, fingerprint):
                raise _Revoked()
            return message
        async def watch():
            while self._valid(token, fingerprint):
                await asyncio.sleep(.25)
        task = asyncio.create_task(self.app(scope, protected_receive, protected_send))
        watcher = asyncio.create_task(watch())
        try:
            done, _ = await asyncio.wait({task, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if watcher in done:
                await close()
            else:
                try:
                    await task
                except _Revoked:
                    await close()
        finally:
            task.cancel()
            watcher.cancel()
            await asyncio.gather(task, watcher, return_exceptions=True)
