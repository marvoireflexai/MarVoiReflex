"""Explicit provisioning only. Runtime never downloads speech models."""
from pathlib import Path
import argparse,hashlib,json,shutil
def main():
    import moonshine_voice as m
    p=argparse.ArgumentParser();p.add_argument('--app-root',required=True);p.add_argument('--cache-root',required=True);args=p.parse_args()
    path,arch=m.get_model_for_language('zh',m.ModelArch.TINY_STREAMING,cache_root=Path(args.cache_root))
    if arch!=m.ModelArch.TINY_STREAMING:raise RuntimeError('Unexpected model architecture')
    target=Path(args.app_root).resolve()/'assets/asr/moonshine-zh-tiny-streaming'
    if target.exists():raise RuntimeError('Destination already exists; do not overwrite existing weights')
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(path,target)
    inventory={f.relative_to(target).as_posix():{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(target.rglob('*')) if f.is_file()}
    (target/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    print('Moonshine Mandarin Tiny Streaming installed locally.')
if __name__=='__main__':main()
