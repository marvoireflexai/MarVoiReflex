"""Explicit download of EmbeddingGemma Q4; never download at runtime."""
from pathlib import Path
import argparse,shutil,json,hashlib
def main():
    import moonshine_voice as m
    p=argparse.ArgumentParser();p.add_argument('--app-root',required=True);p.add_argument('--cache-root',required=True);a=p.parse_args()
    path,arch=m.get_embedding_model('embeddinggemma-300m','q4',cache_root=Path(a.cache_root))
    target=Path(a.app_root).resolve()/'assets/embedding/embeddinggemma-300m'
    if target.exists():raise RuntimeError('Destination exists')
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(path,target)
    inventory={f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in target.iterdir() if f.is_file()}
    (target/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
if __name__=='__main__':main()
