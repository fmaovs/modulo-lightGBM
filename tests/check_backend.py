import requests
import json

BASE = 'http://localhost:8080/api'

def login(user='admin', pwd='admin123'):
    url = f"{BASE}/auth/login"
    try:
        r = requests.post(url, json={"username": user, "password": pwd}, timeout=5)
    except Exception as e:
        print('LOGIN ERROR:', e)
        return None
    print('LOGIN STATUS:', r.status_code)
    try:
        print('LOGIN BODY:', r.text)
    except Exception:
        pass
    try:
        j = r.json()
    except Exception:
        return None
    token = j.get('token') or j.get('accessToken') or j.get('access_token')
    return token

def get_active(token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        r = requests.get(f"{BASE}/scoring/config/models/active", headers=headers, timeout=5)
    except Exception as e:
        print('ACTIVE ERROR:', e)
        return None
    print('ACTIVE STATUS:', r.status_code)
    print('ACTIVE BODY:', r.text)
    return r.text

def get_variables(version, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        r = requests.get(f"{BASE}/scoring/config/models/{version}/variables", headers=headers, timeout=5)
    except Exception as e:
        print('VARS ERROR:', e)
        return None
    print('VARS STATUS:', r.status_code)
    print('VARS BODY:', r.text)
    return r.text

if __name__ == '__main__':
    t = login()
    print('TOKEN:', t)
    active = get_active(t)
    # si devuelve un campo 'modelVersion' intentamos obtener variables
    if active:
        try:
            j = json.loads(active)
            ver = j.get('modelVersion') or j.get('id') or '1'
            get_variables(ver, t)
        except Exception:
            pass
