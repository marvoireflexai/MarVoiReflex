from pathlib import Path
import os,sys,time,json,hashlib,subprocess,urllib.request,urllib.error,threading,uuid
from playwright.sync_api import sync_playwright,expect
import argparse
parser=argparse.ArgumentParser(description='Run isolated image search responsiveness acceptance tests.')
parser.add_argument('--app',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args();exe=args.app.resolve()
if not exe.is_file() or exe.name.casefold()!='marvoireflex.exe':raise SystemExit('Specify an installed MarVoiReflex.exe')
import psutil
if any((p.info.get('name') or '').casefold()=='marvoireflex.exe' for p in psutil.process_iter(['name'])):raise SystemExit('Close MarVoiReflex first')
app=exe.parent;lab=args.out.resolve();lab.mkdir(parents=True,exist_ok=True);mode='frozen'
env={k:v for k,v in os.environ.items() if k not in ('MARVOI_MODEL_PROFILE','MARVOI_GEMMA_ROOT','MARVOI_ASSETS_ROOT','CROSSGEN_DATA_DIR','CROSSGEN_MODEL_URL','CROSSGEN_BRIDGE_URL','MARVOI_ADVANCED_URL','MARVOI_MOONSHINE_DIR','MARVOI_EMBEDDING_DIR','MARVOI_OCR')}
parent=Path.home()/'MVR-Presentation';before=set(parent.glob('session-*'))
cmd=[str(exe),'--presentation','--no-browser']
report={'mode':mode,'passed':[],'timings':[],'isolated':True,'physical_8gb_tested':False,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
p=None;c=None;session=None
def api(path,body=None,raw=False):
 req=urllib.request.Request(c['origin']+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers={'X-MarVoi-Key':c['token'],'Content-Type':'application/json'})
 with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=150) as r:return r.read() if raw else json.load(r)
def ok(name):
 report['passed'].append(name);print('PASS',name,flush=True)
def query(text,mode='task'):
 t=time.perf_counter();r=api('/api/text',{'mode':mode,'text':text})['result'];dt=round(time.perf_counter()-t,4)
 report['timings'].append({'query':text,'seconds':dt,'selected':r.get('selected'),'cached':r.get('cached'),'status':r['status']})
 print('QUERY',json.dumps(report['timings'][-1],ensure_ascii=True),flush=True);return r
try:
 with (lab/f'responsive-{mode}.log').open('wb') as log:p=subprocess.Popen(cmd,env=env,cwd=app,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(200):
  if p.poll() is not None:raise RuntimeError('App exited')
  for d in set(parent.glob('session-*'))-before:
   try:
    conn=json.loads((d/'state/connection.json').read_text(encoding='utf-8'))
    if conn.get('origin','').startswith('http://127.0.0.1:') and conn.get('token'):session=d;c=conn;break
   except (OSError,ValueError):pass
  if c:break
  time.sleep(.5)
 assert c
 for _ in range(360):
  state=api('/api/status')
  if state.get('error'):raise RuntimeError(state['error'])
  if state['ready']:break
  time.sleep(.5)
 else:raise RuntimeError('Not ready')
 for _ in range(100):
  st=api('/api/local/status')
  if st['state']=='complete':break
  time.sleep(.2)
 assert st['indexed']==6
 # Validate real cold inference and warm cache results on identical files and conditions.
 r=query('幫我找汽車的照片')
 assert r['selected']==['IMG_4128.jpg'] and r['cached']==0,r
 ok('cold_visual_car')
 r=query('幫我找汽車的照片。','chat')
 assert r['selected']==['IMG_4128.jpg'] and r['cached']==3,r
 assert report['timings'][-1]['seconds']<1.0
 ok('warm_cache_reuses_all_three_candidates')
 r=query('找出紅色背景的圖片');assert r['selected']==['IMG_0631.jpg'],r
 r=query('找出有黃色花朵的圖片');assert r['selected']==['IMG_0987.jpg'],r
 ok('other_visual_queries_preserve_accuracy')
 # Clearing memory removes all prior local answers.
 r=query('清除圖片辨識快取');assert '已清除' in r['text']
 with sync_playwright() as pw:
  browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1280,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(c['url'],wait_until='domcontentloaded');page.locator('#taskTab').click()
  expect(page.locator('#import')).to_be_enabled(timeout=30000)
  page.locator('#taskInput').fill('幫我找汽車的照片')
  page.locator('#taskSend').click()
  expect(page.locator('#taskSearchProgress')).to_be_visible(timeout=15000)
  expect(page.locator('#taskSearchLabel')).to_contain_text('/ 3')
  status=api('/api/search/status')['progress'];assert status and status['total']==3 and not status['cancelling']
  assert api('/api/search/cancel',{'id':'not-real'})['cancelled'] is False
  t=time.perf_counter();page.locator('#taskSearchCancel').click()
  expect(page.locator('#taskFeedback')).to_contain_text('已停止',timeout=120000)
  expect(page.locator('#taskSearchProgress')).not_to_be_visible(timeout=10000)
  expect(page.locator('#taskInput')).to_have_value('幫我找汽車的照片')
  assert api('/api/search/status')['progress'] is None
  report['cancel_seconds']=round(time.perf_counter()-t,3)
  ok('real_ui_progress_and_cancel_keeps_text')
  # Retry succeeds, rendering an actual file card, not fabricated output.
  page.locator('#taskSend').click()
  expect(page.locator('#files')).to_contain_text('IMG_4128.jpg',timeout=120000)
  expect(page.locator('#taskSearchProgress')).not_to_be_visible(timeout=10000)
  with page.expect_download() as dl:page.locator('#files').get_by_role('button',name='下載檔案',exact=True).click()
  assert Path(dl.value.path()).read_bytes()==(session/'DemoFiles/Pictures/IMG_4128.jpg').read_bytes()
  assert not errors,errors;report['page_errors']=errors;browser.close()
 ok('retry_and_original_file_download')
 manifest=json.loads((session/'manifest.json').read_text(encoding='utf-8'))
 assert all(hashlib.sha256((session/'DemoFiles'/name).read_bytes()).hexdigest()==sha for name,sha in manifest.items())
 ok('originals_unchanged')
 print('RESPONSIVENESS_PASS',len(report['passed']),flush=True)
finally:
 if c and p and p.poll() is None:
  try:api('/api/shutdown',{})
  except Exception:pass
 if p and p.poll() is None:
  try:p.wait(timeout=20)
  except subprocess.TimeoutExpired:p.terminate();p.wait()
 (lab/f'responsive-{mode}-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('REPORT',json.dumps(report,ensure_ascii=True),flush=True)
