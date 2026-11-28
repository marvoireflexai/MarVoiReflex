"""Consent-based, read-only search of locally accessible user files.

No administrator privilege, network shares, arbitrary shell, or model-controlled path access.
"""
from pathlib import Path
from datetime import datetime,date,timedelta,time as dt_time
import os,re,stat,sqlite3,threading,time,secrets,json,hashlib,sys
from platform_support import open_target,verify_mac_handle
from contextlib import contextmanager
from search_progress import SearchCancelled

IMAGE={'.jpg','.jpeg','.png','.webp'}
EXT=IMAGE|{'.gif','.bmp','.tif','.tiff','.svg','.heic','.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.md','.csv','.rtf','.odt','.ods','.odp','.psd','.ai','.indd','.fig','.mp4','.mov','.m4v','.avi','.mkv','.mp3','.wav','.m4a','.flac'}
SKIP_DIR={'windows','program files','program files (x86)','programdata','system volume information','$recycle.bin','recovery','perflogs','documents and settings','appdata','application data','local settings','node_modules','__pycache__','data-marvoivoice','marvoireflex','mvr-presentation','library','applications','system','private','volumes','windowsapps','msocache','users','profiles','cache','caches','browser','credentials','secrets','private keys'}
SECRET=re.compile(r'password|passwd|credential|secret|token|api[-_ ]?key|private[-_ ]?key|wallet|seed[-_ ]?phrase|密碼|憑證|金鑰|私鑰|助記詞',re.I)
ATTR_SKIP=0x2|0x4|0x400|0x1000|0x40000|0x400000
FOLDERS={'desktop':'桌面','downloads':'下載','documents':'文件','pictures':'圖片','videos':'影片','music':'音樂'}
KNOWN={'desktop':'B4BFCC3A-DB2C-424C-B029-7FE99A87C641','downloads':'374DE290-123F-4565-9164-39C4925E467B','documents':'FDD39AD0-238F-46AF-ADB4-6C85480369C7','pictures':'33E28130-4E1E-4676-835A-98395C3BC3BB','videos':'18989B1D-99B5-455B-841C-AB7C74E4DDFC','music':'4BD8D571-6D19-48D3-BE97-422220080E43'}

def known_folders():
    home=Path.home()
    out={}
    for k,guid in KNOWN.items():
        p=home/('Movies' if sys.platform=='darwin' and k=='videos' else k.capitalize())
        if os.name=='nt':
            try:
                import ctypes,uuid
                from ctypes import wintypes
                g=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID(guid).bytes_le)
                ptr=ctypes.c_wchar_p()
                rc=ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g),0,None,ctypes.byref(ptr))
                if rc==0 and ptr.value:p=Path(ptr.value)
                if ptr:ctypes.windll.ole32.CoTaskMemFree(ptr)
            except Exception:pass
        out[k]=p
    return out

def plain_path(p):
    p=Path(p)
    if not p.is_absolute() or str(p).startswith(('\\\\','//')):return False
    if os.name=='nt' and not re.fullmatch(r'[A-Za-z]:',p.drive):return False
    return all(part not in ('.','..') and ':' not in part for part in p.parts[1:])

def safe_stat(p,root=False):
    try:
        s=Path(p).lstat()
        mask=ATTR_SKIP & ~6 if Path(p).parent==Path(p) else ATTR_SKIP
        if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&mask:return None
        return s
    except OSError:return None

def normal_name(name,is_dir=False):
    n=name.casefold()
    return not n.startswith(('.','$')) and not SECRET.search(n) and (not is_dir or n not in SKIP_DIR)

def discover_roots(mode):
    known=known_folders();out=[]
    for k,p in known.items():
        if plain_path(p) and p.is_dir():
            if os.name=='nt':
                import ctypes
                if ctypes.windll.kernel32.GetDriveTypeW(p.anchor) not in (2,3):continue
            out.append((p,k))
    home=Path.home()
    if os.name=='nt' and plain_path(home) and home.is_dir():out.append((home,'profile'))
    if mode=='drives' and os.name=='nt':
        import ctypes
        mask=ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask&(1<<i):
                p=Path(chr(65+i)+':\\')
                if ctypes.windll.kernel32.GetDriveTypeW(str(p)) in (2,3):out.append((p,'drive'))
    return out

def blocked_request(text):
    # Never reinterpret a write, secret search, or external path as a broad read.
    return bool(re.search(r'刪除|清空|覆寫|覆蓋|搬移|搬到|移動|移到|複製|拷貝|重新命名|改名|歸檔|歸類|分類|整理|備份|上傳|傳送|分享|執行|安裝|密碼|憑證|金鑰|私鑰|助記詞|cookie|credential|password|api[-_ ]?key|token|passwords',text,re.I))

def wants_search(text):
    return bool(re.search(r'搜尋|搜索|找出|幫我找|找一下|找找|尋找|列出|查找|^找|^查詢|^我有(?:哪些|哪幾|什麼)',text,re.I))

def workspace_request(text):
    return bool(re.search(r'\bmaterials\b|已匯入|匯入的|工作區|素材庫',text,re.I))

def parse_query(text,visual=False,clock=None):
    clock=clock or date.today()
    if blocked_request(text):raise ValueError('本機搜尋為唯讀，不處理檔案修改、敏感資料或外部傳送。')
    if re.search(r'[A-Za-z]:[\\/]|\\\\|(?:^|\s)/',text):raise ValueError('請使用已授權的資料夾或磁碟名稱，而非任意路徑。')
    if re.search(r'排除|不含|略過|除了|以外|最大|最小|最新|最舊|大小|建立日期|建立時間|創建日期|建立於',text):raise ValueError('此條件尚未支援，請以檔案名稱、類型、資料夾或修改日期搜尋。')
    if len(text)>500:raise ValueError('搜尋條件請控制在 500 字內。')
    dates=[('昨天',clock-timedelta(days=1),clock),('今天',clock,clock+timedelta(days=1)),('前天',clock-timedelta(days=2),clock-timedelta(days=1))]
    mon=clock-timedelta(days=clock.weekday());month=clock.replace(day=1);last=month-timedelta(days=1)
    dates.extend([('本週',mon,mon+timedelta(days=7)),('這週',mon,mon+timedelta(days=7)),('上週',mon-timedelta(days=7),mon),('本月',month,clock+timedelta(days=1)),('這個月',month,clock+timedelta(days=1)),('上個月',last.replace(day=1),month),('上月',last.replace(day=1),month)])
    found=[(k,a,b) for k,a,b in dates if k in text]
    if len(found)>1:raise ValueError('請指定單一日期範圍。')
    lo,hi=None,None
    if found:
        _,a,b=found[0];lo=datetime.combine(a,dt_time.min).timestamp();hi=datetime.combine(b,dt_time.min).timestamp()
    if re.search(r'20\d{2}[年/\-]|\d{1,2}月\d{1,2}|去年|前年|上半年|下半年|去年|最近\d|最近幾',text):raise ValueError('目前支援今天、昨天、前天、本週、上週、本月或上個月。')
    drive=re.search(r'([A-Za-z])\s*(?:槽|磁碟)',text)
    locations=[k for k,v in FOLDERS.items() if (v in text and (k in ('desktop','downloads') or re.search(v+r'(?:資料夾|目錄)',text)))]
    if len(locations)>1:raise ValueError('一次請指定一個搜尋位置。')
    scope=locations[0] if locations else None
    ext=re.search(r'(?<![A-Za-z])\.?(pdf|docx?|xlsx?|pptx?|psd|ai|png|jpe?g|webp|txt|md|csv|mp4|mov|mp3|wav|heic|gif)(?![A-Za-z])',text,re.I)
    extensions={'.'+ext[1].lower()} if ext else None
    if not extensions:
        if re.search(r'圖片|照片|相片|圖檔|海報|主視覺',text):extensions=IMAGE|{'.gif','.bmp','.tif','.tiff','.heic','.svg'}
        elif re.search(r'簡報|投影片',text):extensions={'.ppt','.pptx','.odp'}
        elif re.search(r'試算表|表格',text):extensions={'.xls','.xlsx','.csv','.ods'}
        elif re.search(r'影片|影音',text):extensions={'.mp4','.mov','.m4v','.avi','.mkv'}
        elif re.search(r'文案|文字檔',text):extensions={'.txt','.md','.docx','.doc'}
        elif re.search(r'文件',text):extensions={'.pdf','.doc','.docx','.txt','.md','.rtf','.odt'}
    if visual:extensions=IMAGE
    quoted=re.search(r'[「“"]([^」”"]{1,100})[」”"]',text)
    explicit_name=bool(re.search(r'檔名|檔案名稱|名稱包含',text))
    keyword=quoted[1] if quoted and not visual else ''
    if not keyword and not visual:
        if explicit_name:
            m=re.search(r'(?:檔名|檔案名稱|名稱)\s*(?:包含|含有|含|為|叫做|是)?\s*([^，。！？]{1,100})',text)
            if m:keyword=m[1].strip()
        else:
            keyword=re.sub(r'^(?:(?:請|幫我|麻煩|可以|一下)\s*)*(?:找出|找一下|找找|找|搜尋|搜索|尋找|列出|查找|查詢)\s*','',text.strip())
            for k,_,_ in found:keyword=keyword.replace(k,'')
            if drive:keyword=keyword.replace(drive[0],'')
            if scope:keyword=keyword.replace(FOLDERS[scope],'')
            keyword=re.sub(r'所有|全部|電腦裡|電腦中|電腦內|整台電腦|本機|磁碟|資料夾|目錄|裡面|中的|最近|下載的|修改的|做過的|製作的|檔案|素材|圖片|照片|相片|圖檔|文件|文案|文字檔|簡報|投影片|試算表|表格|影片|影音|的|一下','',keyword)
            if ext:keyword=re.sub(r'(?<![A-Za-z])\.?'+re.escape(ext[1])+r'(?![A-Za-z])','',keyword,flags=re.I)
        keyword=keyword.strip(' ，。！？?!「」"')
        if not quoted and not explicit_name:keyword=re.sub(r'(?:給我看|讓我看看|可以嗎|好嗎|嗎|呢)$','',keyword).strip()
    if keyword and len(keyword)>100:raise ValueError('請縮短檔名搜尋條件。')
    return {'keyword':keyword.casefold(),'extensions':extensions,'scope':scope,'drive':drive[1].upper()+':' if drive else None,'lo':lo,'hi':hi,'visual':visual,'query':text}

class LocalFiles:
    def __init__(self,root,excluded=(),discover=discover_roots,max_entries=500000,max_seconds=120,presentation=False):
        self.root=Path(root)/'local-search';self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'files.sqlite3';self.settings=self.root/'consent.json'
        self.discover=discover;self.presentation=presentation;self.excluded=tuple(Path(p).absolute() for p in (*excluded,root));self.max_entries=max_entries;self.max_seconds=max_seconds
        self.lock=threading.RLock();self.mode=None;self.roots=[];self.epoch=0;self.worker=None;self.state='disabled';self.count=0;self.skipped=0;self.last_scan=0;self.results={};self.last=None
        try:
            v=json.loads(self.settings.read_text(encoding='utf-8'))
            if v.get('version')==1 and v.get('mode') in ('personal','drives'):self.set_scope(v['mode'])
        except (OSError,ValueError,TypeError):pass
    @contextmanager
    def _db(self):
        c=sqlite3.connect(self.db,timeout=5)
        try:
            with c:
                c.execute('PRAGMA secure_delete=ON')
                c.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,name TEXT NOT NULL,folder TEXT NOT NULL,ext TEXT NOT NULL,mtime REAL NOT NULL,size INTEGER NOT NULL,drive TEXT NOT NULL)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_local_mtime ON files(mtime DESC)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_local_type ON files(ext,folder,mtime DESC)')
                yield c
        finally:c.close()
    def _clear_db(self):
        # Connection handles are closed before removal (required on Windows).
        if self.db.exists():
            try:self.db.unlink()
            except OSError:
                with self._db() as c:c.execute('DELETE FROM files')
                try:self.db.unlink()
                except OSError:pass
        for suffix in ('-wal','-shm','-journal'):
            try:Path(str(self.db)+suffix).unlink(missing_ok=True)
            except OSError:pass
    def _excluded(self,p):return any(p==x or p.is_relative_to(x) for x in self.excluded)
    def _root_for(self,p):
        matches=[(r,k) for r,k in self.roots if p==r or p.is_relative_to(r)]
        return max(matches,key=lambda x:len(x[0].parts)) if matches else None
    def checked(self,value,require_file=True):
        p=Path(value)
        if not self.mode or not plain_path(p) or self._excluded(p):raise PermissionError('不在已授權的本機搜尋範圍。')
        match=self._root_for(p)
        if not match:raise PermissionError('不在已授權的本機搜尋範圍。')
        r,k=match
        # Reject redirection at every ancestor, not merely the leaf.
        for ancestor in reversed(r.parents):
            if safe_stat(ancestor,True) is None:raise PermissionError('不支援連結、離線或不可存取的位置。')
        if safe_stat(r,True) is None:raise PermissionError('搜尋位置不可存取。')
        rel=p.relative_to(r);cur=r
        for i,part in enumerate(rel.parts):
            cur=cur/part
            is_dir=i<len(rel.parts)-1 or not require_file
            if not normal_name(part,is_dir) or self._excluded(cur) or safe_stat(cur) is None:raise PermissionError('此路徑已排除或不可存取。')
        st=safe_stat(p)
        if not st or (require_file and (not stat.S_ISREG(st.st_mode) or p.suffix.casefold() not in EXT)):raise PermissionError('不支援或不可讀取的檔案。')
        return p
    def status(self):
        with self.lock:return {'mode':self.mode,'state':self.state,'indexed':self.count,'skipped':self.skipped,'roots':[{'path':str(p),'kind':k} for p,k in self.roots]}
    def set_scope(self,mode):
        if mode not in ('personal','drives',None):raise ValueError('無效搜尋範圍。')
        with self.lock:
            self.epoch+=1;self.mode=None;self.results={};self.last=None;self.roots=[];self.count=0;self.skipped=0
            self._clear_db()
            self.settings.unlink(missing_ok=True)
            if mode is None:self.state='disabled';return self.status()
            roots=[]
            for p,k in self.discover(mode):
                p=Path(p).absolute()
                if plain_path(p) and not self._excluded(p) and safe_stat(p) and all(safe_stat(q,True) for q in p.parents) and all(normal_name(part,True) or part.casefold()=='users' or (self.presentation and part.casefold()=='mvr-presentation') for part in p.parts[1:]):
                    if not any(p==r for r,_ in roots):roots.append((p,k))
            if not roots:self.state='disabled';raise ValueError('沒有可使用的本機資料夾。')
            self.mode=mode;self.roots=roots
            tmp=self.settings.with_suffix('.tmp');tmp.write_text(json.dumps({'version':1,'mode':mode}),encoding='utf-8');os.replace(tmp,self.settings)
            self._start_locked()
            return self.status()
    def _start_locked(self):
        self.epoch+=1;e=self.epoch;self.count=0;self.skipped=0;self.state='scanning';self.results={};self.last=None;self.last_scan=time.monotonic()
        self._clear_db()
        self.worker=threading.Thread(target=self._scan,args=(e,list(self.roots)),daemon=True,name='local-file-index');self.worker.start()
    def refresh(self):
        with self.lock:
            if not self.mode:raise PermissionError('請先啟用本機搜尋。')
            if self.state!='scanning':return self.set_scope(self.mode)
            return self.status()
    def _scan(self,e,roots):
        start=time.monotonic();seen=set();batch=[];examined=0;skipped=0;limited=False
        def flush():
            with self.lock:
                if e!=self.epoch:return False
                if batch:
                    with self._db() as c:c.executemany('INSERT OR IGNORE INTO files VALUES (?,?,?,?,?,?,?)',batch)
                    self.count+=len(batch);batch.clear()
                self.skipped=skipped
                return True
        try:
            # User folders first; skip duplicates when later visiting the drive.
            stack=list(reversed(roots))
            while stack:
                if e!=self.epoch:return
                if examined>=self.max_entries or time.monotonic()-start>self.max_seconds:limited=True;break
                folder,kind=stack.pop()
                key=os.path.normcase(str(folder))
                if key in seen:continue
                seen.add(key)
                if self._excluded(folder) or not safe_stat(folder):skipped+=1;continue
                try:self.checked(folder,require_file=False)
                except PermissionError:skipped+=1;continue
                try:
                    with os.scandir(folder) as it:
                        for entry in it:
                            if e!=self.epoch:return
                            examined+=1
                            if examined>=self.max_entries or time.monotonic()-start>self.max_seconds:limited=True;break
                            p=Path(entry.path)
                            if self._excluded(p):continue
                            s=safe_stat(p)
                            if not s:skipped+=1;continue
                            if stat.S_ISDIR(s.st_mode):
                                if normal_name(entry.name,True):stack.append((p,kind))
                                else:skipped+=1
                            elif stat.S_ISREG(s.st_mode) and normal_name(entry.name) and p.suffix.casefold() in EXT:
                                # Index metadata only. All reads are separately revalidated.
                                batch.append((str(p),entry.name,kind,p.suffix.casefold(),s.st_mtime,s.st_size,p.drive.upper()))
                                if len(batch)>=256 and not flush():return
                        if limited:break
                except OSError:skipped+=1
                if batch and not flush():return
            if not flush():return
            with self.lock:
                if e==self.epoch:self.state='partial' if limited else 'complete'
        except Exception:
            with self.lock:
                if e==self.epoch:self.state='error'
    def read_bytes(self,path,limit):
        p=self.checked(path)
        with p.open('rb') as f:
            s=os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_size>limit:raise ValueError('檔案大小超過讀取上限。')
            if os.name=='nt':
                import ctypes,msvcrt
                fn=ctypes.windll.kernel32.GetFinalPathNameByHandleW;fn.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32];fn.restype=ctypes.c_uint32
                buf=ctypes.create_unicode_buffer(32768);n=fn(msvcrt.get_osfhandle(f.fileno()),buf,len(buf),0)
                if not n or n>=len(buf):raise PermissionError('無法核對實際讀取路徑。')
                actual=buf.value
                if actual.startswith('\\\\?\\UNC\\'):raise PermissionError('不支援網路檔案。')
                if actual.startswith('\\\\?\\'):actual=actual[4:]
                if os.path.normcase(actual)!=os.path.normcase(str(p)):raise PermissionError('實際檔案路徑已變更。')
                self.checked(Path(actual))
            verify_mac_handle(f,p,self.checked)
            data=f.read(limit+1)
            if len(data)>limit:raise ValueError('檔案大小超過讀取上限。')
            return data
    def _remember(self,p,mtime,size):
        id=secrets.token_hex(16);self.results[id]=(str(p),mtime,size,self.epoch)
        if len(self.results)>1000:self.results.pop(next(iter(self.results)))
        return id
    def _result_path(self,id):
        with self.lock:
            if not self.mode or not isinstance(id,str) or id not in self.results:raise PermissionError('搜尋結果已失效，請重新搜尋。')
            path,mtime,size,epoch=self.results[id]
            if epoch!=self.epoch:raise PermissionError('搜尋結果已失效。')
            p=self.checked(path);s=p.stat()
            if s.st_mtime!=mtime or s.st_size!=size:raise PermissionError('原始檔案已變更，請重新搜尋。')
            return p
    def preview(self,id):
        with self.lock:
            p=self._result_path(id)
            if p.suffix.lower() not in ('.txt','.md','.csv'):raise ValueError('僅支援純文字預覽；其他格式請前往原始位置。')
            b=self.read_bytes(p,64*1024)
            try:t=b.decode('utf-8-sig')
            except UnicodeDecodeError:t=b.decode('cp950',errors='replace')
            return {'name':p.name,'text':t,'truncated':False}
    def reveal(self,id):
        with self.lock:
            p=self._result_path(id)
            open_target(p,reveal=True)
            return {'ok':True}
    def close(self):
        with self.lock:self.epoch+=1;self.results={};self.last=None
    def search(self,text,visual=False,classifier=None,continuation=False,progress=None):
        with self.lock:
            if not self.mode:raise PermissionError('請先啟用本機搜尋。')
            if continuation:
                if not self.last:raise ValueError('沒有可繼續的搜尋。')
                q,offset,e=self.last
                if e!=self.epoch:raise ValueError('索引已更新，請重新搜尋。')
            else:
                q=parse_query(text,visual);offset=0;e=self.epoch
                self.last=None
            if q['scope'] and not any(k==q['scope'] for _,k in self.roots):raise ValueError('指定資料夾尚未授權或不存在。')
            if q['drive'] and not any(p.drive.upper()==q['drive'] for p,_ in self.roots):raise ValueError('指定磁碟尚未授權。')
            where=[];args=[]
            if q['keyword']:where.append('instr(lower(name),?)>0');args.append(q['keyword'])
            if q['extensions']:
                ex=sorted(q['extensions']);where.append('ext IN ('+','.join('?' for _ in ex)+')');args.extend(ex)
            if q['scope']:where.append('folder=?');args.append(q['scope'])
            if q['drive']:where.append('drive=?');args.append(q['drive'])
            if q['lo'] is not None:where.extend(['mtime>=?','mtime<?']);args.extend([q['lo'],q['hi']])
            clause=' WHERE '+' AND '.join(where) if where else ''
            limit=12 if q['visual'] else 50
            with self._db() as c:
                total=c.execute('SELECT count(*) FROM files'+clause,args).fetchone()[0]
                rows=c.execute('SELECT path,name,ext,mtime,size FROM files'+clause+' ORDER BY mtime DESC,path LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()
            state=self.state;indexed=self.count
        results=[];errors=0;cached=0
        if q['visual'] and progress:progress.begin(len(rows),'local')
        for path,name,ext,mtime,size in rows:
            if progress:progress.check()
            v=None
            try:
                with self.lock:
                    if e!=self.epoch:raise PermissionError('搜尋已取消。')
                    p=self.checked(path);st=p.stat()
                    if st.st_mtime!=mtime or st.st_size!=size:raise ValueError('檔案已變更')
                    if q['visual']:
                        if not classifier:raise RuntimeError('視覺模型尚未就緒')
                        data=self.read_bytes(p,32*1024**2)
                reason='';match='yes'
                if q['visual']:
                    def check_search():
                        if progress:progress.check()
                        with self.lock:
                            if e!=self.epoch:raise SearchCancelled('授權或索引已變更，搜尋已停止。')
                    v=classifier(p,q['query'],hashlib.sha256(data).hexdigest(),data,check=check_search)
                    cached+=int(bool(v.get('cached')))
                    match=v['match'];reason=v['reason']
                    if match=='no':continue
                with self.lock:
                    if e!=self.epoch:raise PermissionError('搜尋已取消。')
                    rid=self._remember(p,mtime,size)
                results.append({'id':rid,'name':name,'path':str(p),'match':match,'reason':reason,'previewable':ext in ('.txt','.md','.csv'),'mtime':mtime,'size':size})
            except SearchCancelled:raise
            except (OSError,ValueError,RuntimeError):errors+=1
            finally:
                if q['visual'] and progress:progress.step(v)
        if progress:progress.check()
        with self.lock:
            if e!=self.epoch:raise PermissionError('搜尋已取消或授權已變更。')
            next_offset=offset+len(rows)
            more=next_offset<total and state!='scanning'
            self.last=(q,next_offset,e) if more else None
        note='索引建立中，結果尚未完整。' if state=='scanning' else '已達掃描上限或索引未完成，結果並非全磁碟完整清單。' if state!='complete' else '已掃描目前授權範圍內符合索引條件的檔案。'
        text=f'{note} 本頁檢查 {len(rows)} 個候選，找到 {len(results)} 個結果；候選總數 {total}，索引 {indexed} 個檔案。'
        if q['visual']:
            text+=' 圖片依內容辨識；需確認項目不視為確定命中。'
            if cached:text+=f' 本次重用 {cached} 張辨識結果。'
        if q['lo'] is not None:text+=' 日期依最後修改時間判定。'
        if errors:text+=f' {errors} 個檔案已變更、無法讀取或辨識失敗。'
        if more:text+=' 可繼續搜尋下一批。'
        return {'status':'searched','mode':'task','text':text,'selected':[r['name'] for r in results if r['match']=='yes'],'local_results':results,'local_more':more,'local_index_state':state,'candidates':total,'scanned':len(rows),'cached':cached}
