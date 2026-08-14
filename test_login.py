import requests, sys
sys.stdout.reconfigure(encoding='utf-8')
print('=== testing login ===', flush=True)
try:
    r = requests.post('http://localhost:8001/api/auth/login', json={'username':'demo','password':'demo123'}, timeout=5)
    print('login status:', r.status_code, flush=True)
    print('login body:', r.text[:600], flush=True)
    if r.status_code == 200:
        j = r.json()
        token = j.get('access_token') or j.get('token')
        print('token:', token[:30] if token else None, flush=True)
        r2 = requests.get('http://localhost:8001/api/favorites', headers={'Authorization':'Bearer '+token}, timeout=5)
        print('fav status:', r2.status_code, flush=True)
        print('fav body:', r2.text[:600], flush=True)
except Exception as e:
    print('ERR:', repr(e), flush=True)
print('=== done ===', flush=True)
