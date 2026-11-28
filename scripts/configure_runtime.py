"""Point a source checkout at an existing full App. Does not copy/download models."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parent.parent
REQUIRED=['gemma4-e2b/gemma-4-E2B_q4_0-it.gguf','gemma4-e2b/gemma-4-E2B-it-mmproj.gguf','gemma4-e2b/runtime/llama-server.exe','node/node.exe','bridge.mjs','asr/faster-whisper-small/model.bin','node/node_modules/@wonderwhy-er/desktop-commander/dist/index.js']
def validate(app_root,check_hash=False):
    root=Path(app_root).expanduser().resolve()
    missing=[p for p in REQUIRED if not (root/'assets'/p).is_file()]
    if missing:raise ValueError('Missing runtime assets: '+', '.join(missing))
    if check_hash:
        with (root/'assets'/REQUIRED[0]).open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!='fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634':raise ValueError('Model SHA-256 mismatch')
        with (root/'assets'/REQUIRED[1]).open('rb') as f:vision_digest=hashlib.file_digest(f,'sha256').hexdigest()
        if vision_digest!='021059cce659fe7f9170d5599761d7bbaf644b798dab9503aca30dc43e6beb14':raise ValueError('Vision projector SHA-256 mismatch')
    return root
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--app-root',required=True);p.add_argument('--check-hash',action='store_true');args=p.parse_args()
    root=validate(args.app_root,args.check_hash)
    (ROOT/'app-link.json').write_text(json.dumps({'app_root':str(root)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Runtime configured. app-link.json is local-only; models were not copied.')
