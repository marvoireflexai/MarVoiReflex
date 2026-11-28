"""Local-only inference routing; execution authority remains with the controller."""
import os,re
from urllib.parse import urlsplit
import requests
from app_paths import model_url

def local_endpoint(value):
    if not value:return None
    try:
        u=urlsplit(value)
        if u.scheme!='http' or u.hostname!='127.0.0.1' or u.username or u.password or not u.port or u.path not in ('','/') or u.query or u.fragment:return None
        return f'http://127.0.0.1:{u.port}'
    except ValueError:return None

def complex_text(text):
    return len(text)>140 or bool(re.search(r'比較|分析|策略|多步驟|規劃|依序|逐一|同時.*並且|先.+再.+最後',text))

def complete(payload,prefer_advanced=False,validator=None):
    primary=local_endpoint(model_url())
    if not primary:raise ValueError('Invalid local model endpoint')
    advanced=local_endpoint(os.environ.get('MARVOI_ADVANCED_URL'))
    candidates=[('advanced',advanced),('local',primary)] if advanced and advanced!=primary and prefer_advanced else [('local',primary)]
    error=None
    with requests.Session() as session:
        session.trust_env=False
        for name,endpoint in candidates:
            try:
                if name=='advanced':
                    h=session.get(endpoint+'/health',timeout=(1,2),allow_redirects=False)
                    if h.status_code!=200:raise RuntimeError('Advanced model unavailable')
                r=session.post(endpoint+'/v1/chat/completions',json=payload,timeout=(3,90 if name=='advanced' else 60),allow_redirects=False)
                if r.status_code!=200:raise RuntimeError(f'Model HTTP {r.status_code}')
                raw=r.json();choice=raw['choices'][0]
                if not isinstance(choice['message'].get('content'),str) or not choice['message']['content'].strip():raise ValueError('Empty model output')
                if validator:validator(raw)
                return raw,name
            except (requests.RequestException,ValueError,KeyError,IndexError,TypeError,RuntimeError) as exc:error=exc
    raise RuntimeError('Local model could not complete this request') from error
