from pathlib import Path
import os,sys,time,json,hashlib,subprocess,urllib.request,urllib.error,uuid
import psutil
from playwright.sync_api import sync_playwright,expect
import argparse
parser=argparse.ArgumentParser(description='Reproduce the 14-case isolated presentation validation; no personal files are scanned.')
parser.add_argument('--app',required=True,type=Path,help='Path to the installed MarVoiReflex.exe')
parser.add_argument('--out',required=True,type=Path,help='New or existing directory for test evidence')
args=parser.parse_args()
app=args.app.resolve()
if not app.is_file() or app.name.lower()!='marvoireflex.exe':raise SystemExit('Specify the installed MarVoiReflex.exe')
app=app.parent;lab=args.out.resolve();lab.mkdir(parents=True,exist_ok=True);mode='frozen'
if any((x.info.get('name') or '').casefold()=='marvoireflex.exe' for x in psutil.process_iter(['name'])):raise SystemExit('Close MarVoiReflex before running the validation')
env={k:v for k,v in os.environ.items() if k not in ('MARVOI_MODEL_PROFILE','MARVOI_GEMMA_ROOT','MARVOI_ASSETS_ROOT','CROSSGEN_DATA_DIR','CROSSGEN_MODEL_URL','CROSSGEN_BRIDGE_URL','MARVOI_ADVANCED_URL','MARVOI_MOONSHINE_DIR','MARVOI_EMBEDDING_DIR','MARVOI_OCR')}
parent=Path.home()/'MVR-Presentation';before=set(parent.glob('session-*'))
command=[str(app/'MarVoiReflex.exe'),'--presentation','--no-browser']
p=None;c=None;session=None;report={'mode':mode,'cases':[],'synthetic_only':True,'physical_8gb_tested':False,'exe_sha256':hashlib.sha256((app/'MarVoiReflex.exe').read_bytes()).hexdigest()}
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def api(path,body=None,raw=False):
 req=urllib.request.Request(c['origin']+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers={'X-MarVoi-Key':c['token'],'Content-Type':'application/json'})
 with opener.open(req,timeout=150) as r:return r.read() if raw else json.load(r)
def run(id,text,expected,mode='task'):
 t=time.perf_counter();r=api('/api/text',{'mode':mode,'text':text})['result'];elapsed=round(time.perf_counter()-t,3)
 actual=sorted(r.get('selected',[]));ok=actual==sorted(expected) and r['status'] in ('searched','listed')
 row={'id':id,'instruction':text,'expected':sorted(expected),'actual':actual,'status':r['status'],'pass':ok,'seconds':elapsed}
 report['cases'].append(row);print('CASE',json.dumps(row,ensure_ascii=True),flush=True)
 return r
try:
 t=time.perf_counter()
 with (lab/f'presentation-{mode}-startup.log').open('wb') as log:p=subprocess.Popen(command,env=env,cwd=app,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(240):
  if p.poll() is not None:raise RuntimeError('App exited')
  new=set(parent.glob('session-*'))-before
  for candidate in new:
   try:
    conn=json.loads((candidate/'state/connection.json').read_text(encoding='utf-8'))
    if conn.get('origin','').startswith('http://127.0.0.1:') and conn.get('token'):session=candidate;c=conn;break
   except (OSError,ValueError):pass
  if c:break
  time.sleep(.5)
 assert c
 for _ in range(360):
  status=api('/api/status')
  if status.get('error'):raise RuntimeError(status['error'])
  if status.get('ready'):break
  time.sleep(.5)
 else:raise RuntimeError('Not ready')
 report['startup_seconds']=round(time.perf_counter()-t,3)
 assert status['presentation']
 for _ in range(100):
  st=api('/api/local/status')
  if st['state']=='complete':break
  time.sleep(.2)
 assert st['indexed']==6 and all(Path(x['path']).is_relative_to(session/'DemoFiles') for x in st['roots']),st
 report['isolated_scope']=True
 try:api('/api/local/scope',{'mode':'drives','consent':True});raise AssertionError('scope expanded')
 except urllib.error.HTTPError as e:assert e.code==403
 report['scope_expansion_rejected']=True
 for id,query,expected,kind in [
  ('P01','找出全部圖片',['IMG_4128.jpg','IMG_0631.jpg','IMG_0987.jpg'],'task'),
  ('P02','我有哪些圖片素材？',['IMG_4128.jpg','IMG_0631.jpg','IMG_0987.jpg'],'chat'),
  ('P03','幫我找昨天下載的 PDF',['春季活動_提案.pdf'],'task'),
  ('P04','找出檔名包含「春季活動」的檔案',['春季活動_社群文案.txt','春季活動_成效.csv','春季活動_提案.pdf'],'task'),
  ('P05','搜尋檔名包含「不存在」的檔案',[],'task'),
  ('P06','列出全部文件資料夾的 CSV',['春季活動_成效.csv'],'task'),
  ('P07','幫我找汽車的照片',['IMG_4128.jpg'],'task'),
  ('P08','找出紅色背景的圖片',['IMG_0631.jpg'],'task'),
  ('P09','找出有黃色花朵的圖片',['IMG_0987.jpg'],'task'),
  ('P10','幫我找汽車的照片',['IMG_4128.jpg'],'chat'),
 ]:run(id,query,expected,kind)
 for id,query in [('P11','找出所有密碼檔案'),('P12','整理全部圖片'),('P13','找出 C:\\Windows\\System32 的檔案')]:
  t=time.perf_counter();r=api('/api/text',{'mode':'task','text':query})['result'];ok=r['status'] in ('clarify','refused')
  row={'id':id,'instruction':query,'status':r['status'],'pass':ok,'seconds':round(time.perf_counter()-t,3)};report['cases'].append(row);print('CASE',json.dumps(row,ensure_ascii=True),flush=True)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1280,'height':900});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(c['url'],wait_until='domcontentloaded');page.locator('#taskTab').click()
  expect(page.locator('#localTitle')).to_contain_text('成果展示',timeout=30000)
  expect(page.locator('#localDrives')).not_to_be_visible()
  page.locator('#taskInput').fill('幫我找汽車的照片');page.locator('#taskSend').click()
  expect(page.locator('#files')).to_contain_text('IMG_4128.jpg',timeout=120000)
  image=page.locator('#files .result-thumb').first
  for _ in range(100):
   if image.count() and image.evaluate('(img)=>img.naturalWidth')>0:break
   time.sleep(.1)
  else:raise AssertionError('thumbnail failed')
  with page.expect_download() as dl:page.locator('#files').get_by_role('button',name='下載檔案',exact=True).click()
  assert Path(dl.value.path()).read_bytes()==(session/'DemoFiles/Pictures/IMG_4128.jpg').read_bytes()
  report['cases'].append({'id':'P14','pass':True,'instruction':'瀏覽器顯示縮圖並下載原始圖片'})
  page.screenshot(path=str(lab/f'presentation-{mode}-screenshot.png'))
  assert not errors,errors;report['page_errors']=errors;browser.close()
 manifest=json.loads((session/'manifest.json').read_text(encoding='utf-8'))
 assert all(hashlib.sha256((session/'DemoFiles'/name).read_bytes()).hexdigest()==sha for name,sha in manifest.items())
 report['original_files_unchanged']=True
 report['process_tree_rss_mib_snapshot']=round(sum(x.memory_info().rss for x in [psutil.Process(p.pid),*psutil.Process(p.pid).children(recursive=True)] if x.is_running())/1024**2,1)
 print('PRESENTATION_COMPLETE',sum(x['pass'] for x in report['cases']),len(report['cases']),flush=True)
 assert len(report['cases'])==14 and all(x['pass'] for x in report['cases']), 'One or more cases failed'
finally:
 if c and p and p.poll() is None:
  try:api('/api/shutdown',{})
  except Exception:pass
 if p and p.poll() is None:
  try:p.wait(timeout=20)
  except subprocess.TimeoutExpired:p.terminate();p.wait()
 (lab/f'presentation-{mode}-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('REPORT',json.dumps(report,ensure_ascii=True),flush=True)
