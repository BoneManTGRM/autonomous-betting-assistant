"""Synthetic ASGI transport tests; no real passwords, providers or network."""
import asyncio
import hashlib
from http.cookies import SimpleCookie
import re
from urllib.parse import urlencode

import pytest

from owner_auth import OwnerAuthMiddleware, read_config, SESSION_COOKIE, CSRF_COOKIE, SESSION_SECONDS

PASSWORD = 'synthetic-validation-only-password'


def config():
    salt = bytes.fromhex('0123456789abcdef0123456789abcdef')
    digest = hashlib.pbkdf2_hmac('sha256', PASSWORD.encode(), salt, 600000).hex()
    return {'ABA_OWNER_USERNAME': 'synthetic-owner', 'ABA_OWNER_ORIGIN': 'https://owner.test',
            'ABA_OWNER_PASSWORD_HASH': 'pbkdf2_sha256$600000$' + salt.hex() + '$' + digest}


@pytest.fixture(scope='module')
def env():
    return config()


class Harness:
    def __init__(self, env):
        self.env = dict(env)
        self.calls = []
        self.now = 100.0
        async def downstream(scope, receive, send):
            self.calls.append(scope)
            if scope['type'] == 'http':
                await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'cache-control', b'public')]})
                await send({'type': 'http.response.body', 'body': b'PRIVATE SYNTHETIC'})
            else:
                await send({'type': 'websocket.accept'})
                while True:
                    msg = await receive()
                    if msg['type'] == 'websocket.disconnect':return
                    await send({'type': 'websocket.send', 'text': 'PRIVATE SYNTHETIC'})
        self.gate = OwnerAuthMiddleware(downstream, environ=self.env, clock=lambda: self.now)

    async def http(self, path='/', method='GET', cookies='', data=None, origin=None, extra=()):
        headers = [(b'host', b'owner.test')]
        if cookies:headers.append((b'cookie', cookies.encode()))
        if origin is not None:headers.append((b'origin', origin.encode()))
        body = urlencode(data).encode() if isinstance(data, dict) else (data or b'')
        if data is not None:headers.append((b'content-type', b'application/x-www-form-urlencoded'))
        headers.extend(extra)
        sent = []
        async def receive():return {'type': 'http.request', 'body': body}
        async def send(msg):sent.append(msg)
        await self.gate({'type': 'http', 'path': path, 'method': method, 'headers': headers}, receive, send)
        return sent

    async def login(self, password=PASSWORD, username='synthetic-owner'):
        start = await self.http('/_owner/login')
        nonce = re.search(r'name="csrf" value="([^"]+)"', start[1]['body'].decode())[1]
        result = await self.http('/_owner/login', 'POST', f'{CSRF_COOKIE}={nonce}',
                                 {'username': username, 'password': password, 'csrf': nonce}, 'https://owner.test')
        jar = SimpleCookie()
        for k, v in result[0]['headers']:
            if k == b'set-cookie':jar.load(v.decode())
        token = jar[SESSION_COOKIE].value if SESSION_COOKIE in jar else ''
        return result, token


def run(coro):return asyncio.run(coro)


@pytest.mark.parametrize('path', ['/', '/dashboard', '/reset_storage', '/pages/reset_storage.py', '/media/private.pdf', '/_stcore/upload_file/synthetic', '/static/js/app.js', '/component/private', '/%2e%2e/media/private', '/_owner/health/../media/private'])
def test_no_unauthorized_path_invokes_downstream(env, path):
    h=Harness(env); result=run(h.http(path))
    assert result[0]['status'] in (303,401)
    assert not h.calls
    assert b'PRIVATE' not in result[1]['body']


@pytest.mark.parametrize('change', [{}, {'ABA_OWNER_USERNAME':''}, {'ABA_OWNER_PASSWORD_HASH':'invalid'}, {'ABA_OWNER_ORIGIN':'http://owner.test'}, {'ABA_OWNER_ORIGIN':'https://owner.test/path'}, {'ABA_OWNER_ORIGIN':'https://user:pass@owner.test'}])
def test_missing_invalid_config_closed(env, change):
    h=Harness({} if not change else {**env,**change})
    assert run(h.http('/_owner/login'))[0]['status']==503
    assert run(h.http('/_owner/health'))[0]['status']==503
    assert not h.calls


def test_health_only_minimal_exception(env):
    h=Harness(env)
    result=run(h.http('/_owner/health',extra=[(b'host',b'railway-healthcheck')]))
    assert result[0]['status']==200 and result[1]['body']==b'ok'
    assert not h.calls
    assert run(h.http('/_owner/health','POST'))[0]['status']==401


def test_correct_login_cookies_cache_and_restart(env):
    async def scenario():
        h=Harness(env); result,token=await h.login()
        assert result[0]['status']==303 and token
        assert (b'location',b'/') in result[0]['headers']
        for k,v in result[0]['headers']:
            if k==b'set-cookie':
                assert b'Secure' in v and b'HttpOnly' in v and b'SameSite=Strict' in v and b'Path=/' in v
        out=await h.http('/media/private.pdf',cookies=f'{SESSION_COOKIE}={token}')
        assert out[0]['status']==200 and (b'cache-control',b'no-store') in out[0]['headers']
        assert b'public' not in dict(out[0]['headers']).values()
        other=Harness(env)
        assert (await other.http('/media/private.pdf',cookies=f'{SESSION_COOKIE}={token}'))[0]['status']==401
    run(scenario())


def test_wrong_login_throttle_and_retry(env):
    async def scenario():
        h=Harness(env)
        for _ in range(5):
            out,token=await h.login(password='synthetic-wrong-password')
            assert out[0]['status']==401 and not token
        out,_=await h.login();assert out[0]['status']==429
        h.now+=61
        out,token=await h.login();assert out[0]['status']==303 and token
        assert not h.calls
    run(scenario())


def test_csrf_origin_body_and_spoofed_headers(env):
    async def scenario():
        h=Harness(env)
        assert (await h.http('/_owner/login','POST',data={'username':'synthetic-owner'},origin='https://evil.test'))[0]['status']==403
        assert (await h.http('/_owner/login','POST',data=b'x'*4097,origin='https://owner.test'))[0]['status']==403
        assert (await h.http('/_owner/login','POST',data={'csrf':'é'},origin='https://owner.test'))[0]['status']==403
        assert (await h.http('/media/private',extra=[(b'x-forwarded-user',b'synthetic-owner'),(b'x-forwarded-host',b'owner.test')]))[0]['status']==401
        assert (await h.http('/_owner/login',extra=[(b'host',b'evil.test')]))[0]['status']==403
        assert not h.calls
    run(scenario())


def test_logout_csrf_and_session_isolation(env):
    async def scenario():
        h=Harness(env);_,token=await h.login();_,other=await h.login()
        cookie=f'{SESSION_COOKIE}={token}'
        assert (await h.http('/_owner/logout','POST',cookie,{'csrf':'bad'},'https://owner.test'))[0]['status']==403
        page=await h.http('/_owner/logout',cookies=cookie)
        csrf=re.search(r'name="csrf" value="([^"]+)"',page[1]['body'].decode())[1]
        out=await h.http('/_owner/logout','POST',cookie,{'csrf':csrf},'https://owner.test')
        assert out[0]['status']==303
        assert (await h.http('/dashboard',cookies=cookie))[0]['status']==401
        assert (await h.http('/dashboard',cookies=f'{SESSION_COOKIE}={other}'))[0]['status']==200
    run(scenario())


def test_rotation_and_expiry_invalidate_old_session(env):
    async def scenario():
        h=Harness(env);_,token=await h.login()
        h.env['ABA_OWNER_USERNAME']='rotated-owner'
        assert (await h.http('/dashboard',cookies=f'{SESSION_COOKIE}={token}'))[0]['status']==401
        h.env.update(env);_,token=await h.login();h.now+=SESSION_SECONDS
        assert (await h.http('/dashboard',cookies=f'{SESSION_COOKIE}={token}'))[0]['status']==401
    run(scenario())


def test_websocket_handshake_requires_cookie_and_exact_origin(env):
    async def scenario():
        h=Harness(env)
        for headers in [[(b'host',b'owner.test')],[(b'host',b'owner.test'),(b'origin',b'https://evil.test')]]:
            sent=[]
            async def recv():raise AssertionError('unauthenticated receive')
            async def send(msg):sent.append(msg)
            await h.gate({'type':'websocket','path':'/_stcore/stream','headers':headers},recv,send)
            assert sent==[{'type':'websocket.close','code':1008}]
        assert not h.calls
    run(scenario())


@pytest.mark.parametrize('revocation',['logout','rotation','expiry'])
def test_websocket_open_connection_revoked_without_new_message(env, revocation):
    async def scenario():
        h=Harness(env);_,token=await h.login();sent=[];accepted=asyncio.Event()
        async def recv():await asyncio.Future()
        async def send(msg):
            sent.append(msg)
            if msg['type']=='websocket.accept':accepted.set()
        scope={'type':'websocket','path':'/_stcore/stream','headers':[(b'host',b'owner.test'),(b'origin',b'https://owner.test'),(b'cookie',f'{SESSION_COOKIE}={token}'.encode())]}
        task=asyncio.create_task(h.gate(scope,recv,send));await accepted.wait()
        if revocation=='logout':h.gate.sessions.pop(token)
        elif revocation=='rotation':h.env['ABA_OWNER_USERNAME']='rotated'
        else:h.now+=SESSION_SECONDS
        await asyncio.wait_for(task,1)
        assert sent[-1]=={'type':'websocket.close','code':1008}
        assert not any(m['type']=='websocket.send' for m in sent)
    run(scenario())


def test_csrf_nonce_one_use_and_capacity(env):
    async def scenario():
        h=Harness(env)
        page=await h.http('/_owner/login')
        first=re.search(r'name="csrf" value="([^"]+)"',page[1]['body'].decode())[1]
        for _ in range(70):await h.http('/_owner/login')
        assert len(h.gate.consumed_csrf)==0
        cookie=f'{CSRF_COOKIE}={first}'
        data={'username':'synthetic-owner','password':PASSWORD,'csrf':first}
        assert (await h.http('/_owner/login','POST',cookie,data,'https://owner.test'))[0]['status']==303
        assert (await h.http('/_owner/login','POST',cookie,data,'https://owner.test'))[0]['status']==403
    run(scenario())


def test_session_cap_revokes_oldest(env):
    async def scenario():
        h=Harness(env);tokens=[]
        for _ in range(9):
            _,token=await h.login();tokens.append(token);h.now+=61
        assert len(h.gate.sessions)==8
        assert not h.gate._valid(tokens[0],h.gate.fingerprint)
        assert h.gate._valid(tokens[-1],h.gate.fingerprint)
    run(scenario())


def test_inflight_http_send_revocation_stops_private_bytes(env):
    async def scenario():
        h=Harness(env);_,token=await h.login()
        async def downstream(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            h.gate.sessions.pop(token)
            await send({'type':'http.response.body','body':b'SHOULD NOT ESCAPE'})
        h.gate.app=downstream
        out=await h.http('/media/private',cookies=f'{SESSION_COOKIE}={token}')
        assert all(b'SHOULD NOT ESCAPE' not in m.get('body',b'') for m in out)
        assert out[-1]['body']==b''
    run(scenario())


def test_websocket_revoked_during_send_never_forwards_payload(env):
    async def scenario():
        h=Harness(env);_,token=await h.login();sent=[]
        async def downstream(scope,receive,send):
            await send({'type':'websocket.accept'})
            h.gate.sessions.pop(token)
            await send({'type':'websocket.send','text':'SHOULD NOT ESCAPE'})
        h.gate.app=downstream
        async def receive():return {'type':'websocket.connect'}
        async def send(msg):sent.append(msg)
        scope={'type':'websocket','path':'/_stcore/stream','headers':[(b'host',b'owner.test'),(b'origin',b'https://owner.test'),(b'cookie',f'{SESSION_COOKIE}={token}'.encode())]}
        await h.gate(scope,receive,send)
        assert sent==[{'type':'websocket.accept'},{'type':'websocket.close','code':1008}]
    run(scenario())


def test_anonymous_get_flood_cannot_evict_owner_login_form(env):
    async def scenario():
        h=Harness(env)
        page=await h.http('/_owner/login')
        nonce=re.search(r'name="csrf" value="([^"]+)"',page[1]['body'].decode())[1]
        for _ in range(100):await h.http('/_owner/login')
        out=await h.http('/_owner/login','POST',f'{CSRF_COOKIE}={nonce}',
                         {'username':'synthetic-owner','password':PASSWORD,'csrf':nonce},'https://owner.test')
        assert out[0]['status']==303
    run(scenario())


def test_signed_challenge_tampering_expiry_restart_rotation(env):
    async def scenario():
        h=Harness(env);page=await h.http('/_owner/login')
        nonce=re.search(r'name="csrf" value="([^"]+)"',page[1]['body'].decode())[1]
        cfg=h.gate._config()
        assert h.gate._challenge_expiry(nonce,cfg)==400
        for invalid in [nonce[:-1]+'z',nonce.replace('v1.','v2.'),nonce.replace('.100.','.999.'),nonce.replace('.100.','.nan.'),'x'*1000]:
            assert h.gate._challenge_expiry(invalid,cfg) is None
        h.now=401;assert h.gate._challenge_expiry(nonce,cfg) is None
        h.now=100;other=Harness(env);other.gate._config()
        assert other.gate._challenge_expiry(nonce,cfg) is None
        h.env['ABA_OWNER_USERNAME']='rotated';h.gate._config();h.env.update(env);cfg=h.gate._config()
        assert h.gate._challenge_expiry(nonce,cfg) is None
    run(scenario())


def test_concurrent_challenge_replay_only_admitted_once(env):
    async def scenario():
        h=Harness(env);page=await h.http('/_owner/login')
        nonce=re.search(r'name="csrf" value="([^"]+)"',page[1]['body'].decode())[1]
        async def attempt():
            return await h.http('/_owner/login','POST',f'{CSRF_COOKIE}={nonce}',
                         {'username':'synthetic-owner','password':PASSWORD,'csrf':nonce},'https://owner.test')
        results=await asyncio.gather(attempt(),attempt())
        assert sorted(result[0]['status'] for result in results)==[303,403]
        assert len(h.gate.consumed_csrf)==1 and len(h.gate.attempts)==1
    run(scenario())
