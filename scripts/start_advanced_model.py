"""Launch opt-in Gemma E4B on loopback; E2B remains default."""
import argparse,hashlib,os,subprocess
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--model',required=True);p.add_argument('--port',type=int,default=18787);args=p.parse_args()
    import psutil
    if psutil.virtual_memory().total<16*1024**3 or psutil.virtual_memory().available<8*1024**3:raise SystemExit('Advanced mode requires at least 16 GiB RAM and 8 GiB available; 24 GiB recommended.')
    model=Path(args.model).resolve();engine=Path(args.runtime).resolve()
    if not 1024<=args.port<=65535:raise SystemExit('Invalid port')
    with model.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    if model.stat().st_size!=5154941280 or sha!='676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee':raise SystemExit('E4B model integrity check failed')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='',GGML_VK_VISIBLE_DEVICES='',GGML_BACKEND_PATH=str(engine.parent))
    print(f'Advanced loopback endpoint: http://127.0.0.1:{args.port}',flush=True)
    subprocess.run([str(engine),'-m',str(model),'--host','127.0.0.1','--port',str(args.port),'--device','none','--gpu-layers','0','--no-op-offload','--threads','4','--threads-batch','4','--ctx-size','4096','--parallel','1','--reasoning','off','--cache-ram','512','--offline'],env=env,check=True)
if __name__=='__main__':main()
