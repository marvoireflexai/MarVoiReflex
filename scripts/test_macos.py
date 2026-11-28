"""Frozen native macOS validation with real local model and synthetic fixtures."""
import argparse,os,sys,json,time,subprocess,urllib.request,urllib.error,hashlib,platform,psutil,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
app=a.app.resolve();root=Path.home()/'MVR-Presentation';before=set(root.glob('session-*'))
env={k:v for k,v in os.environ.items() if k not in ('MARVOI_ASSETS_ROOT','CROSSGEN_DATA_DIR','MARVOI_MODEL_PROFILE','MARVOI_GEMMA_ROOT','CROSSGEN_MODEL_URL','CROSSGEN_BRIDGE_URL','MARVOI_ADVANCED_URL','MARVOI_MOONSHINE_DIR','MARVOI_EMBEDDING_DIR','MARVOI_OCR')}
proc=None;c=None;session=None;report={'arch':platform.machine(),'macos':platform.mac_ver()[0],'passed':[],'synthetic_only':True,'physical_mac_tested':False,'tts':'not yet tested'}
def api(path,body=None,headers=None,raw=False,timeout=900):
 req=urllib.request.Request(c['origin']+path,data=None if body is None else (body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode()),headers={'X-MarVoi-Key':c['token'],'Content-Type':'application/json',**(headers or {})})
 with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as r:return r.read() if raw else json.load(r)
def ok(name):report['passed'].append(name);print('PASS',name,flush=True)
try:
 with a.out.with_suffix('.log').open('wb') as log:proc=subprocess.Popen([str(app),'--presentation','--no-browser'],env=env,cwd=app.parents[3],stdout=log,stderr=subprocess.STDOUT)
 for _ in range(240):
  if proc.poll() is not None:raise RuntimeError('App exited')
  for d in set(root.glob('session-*'))-before:
   try:
    v=json.loads((d/'state/connection.json').read_text(encoding='utf-8'))
    if v.get('pid')==proc.pid:c=v;session=d;break
   except (OSError,ValueError):pass
  if c:break
  time.sleep(.5)
 assert c,'No startup connection'
 for _ in range(360):
  status=api('/api/status')
  if status.get('error'):raise RuntimeError(status['error'])
  if status.get('ready'):break
  time.sleep(.5)
 else:raise RuntimeError('App not ready')
 assert status['platform']=='darwin' and status['presentation']
 ok('native_frozen_cpu_model_and_mcp_ready')
 for _ in range(100):
  st=api('/api/local/status')
  if st['state']=='complete':break
  time.sleep(.2)
 assert st['indexed']==6 and all(Path(x['path']).is_relative_to(session/'DemoFiles') for x in st['roots'])
 ok('isolated_index')
 try:api('/api/local/scope',{'mode':'drives','consent':True});raise AssertionError('Scope expanded')
 except urllib.error.HTTPError as e:assert e.code==403
 ok('disk_scope_rejected')
 def query(text,mode='task'):
  t=time.perf_counter();result=api('/api/text',{'mode':mode,'text':text})['result']
  print('TASK_RESULT',result.get('status'),round(time.perf_counter()-t,3),flush=True)
  return result
 r=query('幫我找昨天下載的 PDF');assert r['selected']==['春季活動_提案.pdf'],r
 ok('metadata_search')
 r=query('幫我找汽車的照片');assert r['selected']==['IMG_4128.jpg'],r
 row=next(x for x in r['file_results'] if x['name']=='IMG_4128.jpg')
 data=api('/api/results/file',{'source':row['source'],'id':row['id'],'action':'download'},raw=True)
 assert data==(session/'DemoFiles/Pictures/IMG_4128.jpg').read_bytes()
 ok('vision_and_original_file_download')
 assert b'taskSearchProgress' in api('/?launch='+c['token'],raw=True)
 ok('web_interface_served')
 fixture=Path(__file__).parent/'fixtures/mandarin-task.wav'
 assert fixture.is_file()
 call=api('/api/call/start',{})
 r=api('/api/voice/turn',fixture.read_bytes(),{'Content-Type':'audio/wav','X-Voice-Mode':'task','X-Call-ID':call['call_id']})
 assert r['recognized'] and '汽車' in r['recognized'],r
 report['recognized']=r['recognized'];report['tts']='wav generated' if r.get('audio') else 'Chinese system voice unavailable or TTS unsuccessful'
 if r.get('audio'):assert api(r['audio']['url'],raw=True)[:4]==b'RIFF'
 api('/api/call/end',{})
 ok('synthetic_mandarin_asr')
 api('/api/local/scope',{'mode':None})
 for img in (session/'DemoFiles/Pictures').glob('*.jpg'):
  api('/api/assets/import?name='+img.name,img.read_bytes(),{'Content-Type':'application/octet-stream'})
 r=query('整理全部圖片，先給我預覽。');assert r['status']=='preview',r
 plan=r['plan_id'];assert len(r['items'])==3
 result=api('/api/task/control',{'action':'confirm','plan_id':plan})['result']
 assert result['status']=='completed' and result['moved']==3,result
 for img in (session/'DemoFiles/Pictures').glob('*.jpg'):
  assert (session/'state/workspace/materials/已整理/圖片'/img.name).read_bytes()==img.read_bytes()
 ok('confirmed_no_replace_workspace_move')
 manifest=json.loads((session/'manifest.json').read_text(encoding='utf-8'))
 assert all(hashlib.sha256((session/'DemoFiles'/n).read_bytes()).hexdigest()==h for n,h in manifest.items())
 ok('originals_unchanged')
 report['success']=True
finally:
 report.setdefault('success',False)
 if session:
  logs=session/'state'/'logs'
  for name in ('model.log','runtime-profile.json','vision-timing.jsonl','startup-error.txt'):
   f=logs/name
   if f.is_file():
    shutil.copy2(f,a.out.with_name(a.out.stem+'-'+name))
  status_path=session/'state'/'service-status.json'
  if status_path.is_file():report['service_status']=json.loads(status_path.read_text())
 report['runner_memory_bytes']=psutil.virtual_memory().total
 report['runner_cpu_count']=os.cpu_count()
 a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False),flush=True)
 children=[]
 if proc and proc.poll() is None:
  try:children=psutil.Process(proc.pid).children(recursive=True)
  except psutil.Error:pass
  if c:
   try:api('/api/search/status',timeout=3)
   except Exception:pass
   try:
    job=api('/api/search/status',timeout=3).get('progress')
    if job:api('/api/search/cancel',{'id':job['id']},timeout=3)
   except Exception:pass
   try:api('/api/shutdown',{},timeout=5)
   except Exception:pass
  try:proc.wait(timeout=15)
  except subprocess.TimeoutExpired:
   for child in reversed(children):
    try:child.terminate()
    except psutil.Error:pass
   proc.terminate()
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)
   _,alive=psutil.wait_procs(children,timeout=3)
   for child in alive:
    try:child.kill()
    except psutil.Error:pass
