"""Build and validate a native macOS preview. No model weights in Git."""
from pathlib import Path
import os,sys,platform,subprocess,hashlib,shutil,tarfile,tempfile,urllib.request
ROOT=Path(__file__).resolve().parent.parent
ARCH=platform.machine();TAG='b12823'
LLAMA={'arm64':'709005367a1fa0e3bc025355a956b8cdb0e9eeea70f70ed9e9c5b1a04fff483a','x86_64':'ba5ca91d1017e620e1725f86fe713038ddec8cc377c57325017e129bbb732df8'}
ASR={'config.json':'b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828','model.bin':'3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671','tokenizer.json':'fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab','vocabulary.txt':'34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913'}
GEMMA={'gemma-4-E2B_q4_0-it.gguf':'fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634','gemma-4-E2B-it-mmproj.gguf':'021059cce659fe7f9170d5599761d7bbaf644b798dab9503aca30dc43e6beb14'}
NODE='24.13.0'
def run(*args,**kw):subprocess.run([str(x) for x in args],check=True,**kw)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def fetch(url,p,expected):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and sha(p)==expected:return
 tmp=p.with_suffix(p.suffix+'.partial')
 run('/usr/bin/curl','--fail','--location','--retry','3','--connect-timeout','30','--output',tmp,url)
 if sha(tmp)!=expected:raise RuntimeError('SHA256 mismatch: '+p.name)
 tmp.replace(p)
def main():
 if sys.platform!='darwin' or ARCH not in LLAMA:raise SystemExit('Native macOS runner required.')
 dist=ROOT/'dist-macos';dist.mkdir(exist_ok=True);folder=dist/f'MarVoiReflex-macOS-{ARCH}'
 if folder.exists():raise RuntimeError('Clean build folder required')
 folder.mkdir();assets=folder/'assets';assets.mkdir();runtime=assets/'gemma4-e2b/runtime';runtime.mkdir(parents=True)
 with tempfile.TemporaryDirectory() as d:
  tmp=Path(d);label='arm64' if ARCH=='arm64' else 'x64'
  ll=f'llama-{TAG}-bin-macos-{label}.tar.gz';fetch(f'https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/{ll}',tmp/ll,LLAMA[ARCH])
  ext=tmp/'llama';ext.mkdir()
  with tarfile.open(tmp/ll) as t:t.extractall(ext,filter='data')
  servers=list(ext.rglob('llama-server'));assert len(servers)==1,servers
  shutil.copytree(servers[0].parent,runtime,dirs_exist_ok=True,symlinks=True)
  run(runtime/'llama-server','--version')
  nodefile=f'node-v{NODE}-darwin-{label}.tar.gz';nodebase=f'https://nodejs.org/dist/v{NODE}/'
  checks=urllib.request.urlopen(nodebase+'SHASUMS256.txt',timeout=30).read().decode().splitlines()
  expected=next(x.split()[0] for x in checks if x.split()[-1]==nodefile)
  fetch(nodebase+nodefile,tmp/nodefile,expected)
  with tarfile.open(tmp/nodefile) as t:t.extractall(tmp/'node',filter='data')
  node_dir=tmp/'node'/f'node-v{NODE}-darwin-{label}';dest=assets/'node';dest.mkdir()
  shutil.copy2(node_dir/'bin/node',dest/'node');shutil.copy2(node_dir/'LICENSE',dest/'LICENSE')
  env=dict(os.environ,PATH=str(node_dir/'bin')+os.pathsep+os.environ['PATH'])
  run(node_dir/'bin/node',node_dir/'lib/node_modules/npm/bin/npm-cli.js','install','--prefix',dest,'--omit=dev','--no-audit','--no-fund','@wonderwhy-er/desktop-commander@0.3.1','@modelcontextprotocol/sdk@1.32.1',env=env)
  shutil.copy2(ROOT/'runtime/bridge.mjs',assets/'bridge.mjs')
 for name,expected in ASR.items():fetch('https://huggingface.co/Systran/faster-whisper-small/resolve/main/'+name,assets/'asr/faster-whisper-small'/name,expected)
 run(sys.executable,ROOT/'scripts/build_ui.py')
 cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','MarVoiReflex','--osx-bundle-identifier','ai.marvoireflex.app','--target-arch',ARCH,'--distpath',dist/'pyinstaller','--workpath',dist/'work','--specpath',dist,'--paths',ROOT/'src','--collect-data','opencc','--collect-data','faster_whisper','--collect-binaries','ctranslate2','--collect-all','onnxruntime']
 for n in ('torch','tensorflow','transformers','PySide6','tkinter','matplotlib','pandas','scipy','IPython','pyarrow','pytest','ctranslate2.converters','ctranslate2.specs','moonshine_voice','rapidocr_onnxruntime','webview','pythoncom','win32com','pythonnet','native_shell'):cmd+=['--exclude-module',n]
 run(*cmd,ROOT/'src/main.py',cwd=ROOT)
 shutil.move(dist/'pyinstaller/MarVoiReflex.app',folder/'MarVoiReflex.app')
 shutil.copytree(ROOT/'web',folder/'web')
 for n in ('LICENSE','THIRD_PARTY_NOTICES.md'):shutil.copy2(ROOT/n,folder/n)
 shutil.copy2(ROOT/'docs/macos-preview.md',folder/'README-macOS.md')
 for name in ('MarVoiReflex-Install.command','MarVoiReflex-Presentation.command'):
  f=folder/name;shutil.copy2(ROOT/'scripts'/name,f);f.chmod(0o755)
 exe=folder/'MarVoiReflex.app/Contents/MacOS/MarVoiReflex'
 run('/usr/bin/codesign','--verify','--deep','--strict',folder/'MarVoiReflex.app')
 print('APP_BUILT',folder,sha(exe),flush=True)
 for name,expected in GEMMA.items():fetch('https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf/resolve/main/'+name,assets/'gemma4-e2b'/name,expected)
 run(sys.executable,ROOT/'scripts/test_macos.py','--app',exe,'--out',dist/f'validation-{ARCH}.json')
 for n in GEMMA:(assets/'gemma4-e2b'/n).unlink()
 archive=dist/f'MarVoiReflex-macOS-{ARCH}.zip'
 run('/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',folder,archive)
 if archive.stat().st_size>=2_000_000_000:raise RuntimeError('Release asset too large')
 (dist/f'SHA256SUMS-{ARCH}.txt').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf-8')
 print('MAC_PACKAGE_VERIFIED',archive,archive.stat().st_size,flush=True)
if __name__=='__main__':main()
