"""Read-only, user-clicked delivery of verified search result files."""
from pathlib import Path
import hashlib,io,os,secrets,stat,threading
from local_files import EXT,IMAGE,safe_stat,plain_path

MAX_DOWNLOAD=128*1024**2
OPEN_EXT={'.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.md','.csv','.rtf','.odt','.ods','.odp','.png','.jpg','.jpeg','.webp','.gif','.bmp','.tif','.tiff','.heic','.psd','.ai','.indd','.fig','.mp4','.mov','.m4v','.avi','.mkv','.mp3','.wav','.m4a','.flac'}
def capabilities(p):
    ext=p.suffix.casefold()
    return {'can_open':ext in OPEN_EXT,'can_download':p.stat().st_size<=MAX_DOWNLOAD,'image_preview':ext in IMAGE,'previewable':ext in ('.txt','.md','.csv')}

def verified_read(p,check,limit,expected=None):
    p=check(p)
    with p.open('rb') as f:
        before=os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>limit:raise ValueError('檔案超過讀取上限，請直接開啟原檔。')
        if os.name=='nt':
            import ctypes,msvcrt
            fn=ctypes.windll.kernel32.GetFinalPathNameByHandleW
            fn.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32];fn.restype=ctypes.c_uint32
            buf=ctypes.create_unicode_buffer(32768);n=fn(msvcrt.get_osfhandle(f.fileno()),buf,len(buf),0)
            if not n or n>=len(buf):raise PermissionError('無法驗證檔案位置。')
            actual=buf.value
            if actual.startswith('\\\\?\\UNC\\'):raise PermissionError('禁止網路路徑。')
            if actual.startswith('\\\\?\\'):actual=actual[4:]
            if os.path.normcase(actual)!=os.path.normcase(str(p)):raise PermissionError('檔案路徑已變更。')
            check(Path(actual))
        data=f.read(limit+1);after=os.fstat(f.fileno())
        if len(data)>limit or before.st_size!=len(data) or before.st_mtime_ns!=after.st_mtime_ns or before.st_size!=after.st_size:raise PermissionError('檔案已變更，請重新搜尋。')
    if expected and hashlib.sha256(data).hexdigest()!=expected:raise PermissionError('原始檔案已變更，請重新搜尋。')
    return data

class ResultFiles:
    def __init__(self,root,local_files):
        self.workspace=Path(root)/'workspace'/'materials';self.local=local_files
        self.items={};self.lock=threading.RLock()
    def checked(self,p):
        p=Path(p)
        if not plain_path(p) or not p.is_relative_to(self.workspace) or p.suffix.casefold() not in EXT:raise PermissionError('檔案不在已授權工作區。')
        for ancestor in (p,*p.parents):
            try:st=ancestor.lstat()
            except OSError:raise PermissionError('檔案路徑不可存取。')
            if stat.S_ISLNK(st.st_mode) or getattr(st,'st_file_attributes',0)&0x400:raise PermissionError('檔案路徑不可包含連結。')
        st=p.lstat()
        if not stat.S_ISREG(st.st_mode):raise PermissionError('不是一般檔案。')
        return p
    def attach(self,result,assets):
        with self.lock:
            self.items.clear()
            rows=[]
            reasons={x['path']:(x['reason'],match) for match in ('yes','uncertain') for x in result.get('visual_results',{}).get(match,[])}
            for a in assets[:100]:
                try:
                    rel=Path(a['path'])
                    if rel.is_absolute() or '..' in rel.parts:continue
                    p=self.checked(self.workspace.parent/rel);st=p.stat()
                    id=secrets.token_hex(16);self.items[id]=(p,st.st_mtime_ns,st.st_size,a.get('sha256'))
                    reason,match=reasons.get(a['path'],('','yes'))
                    rows.append(dict(id=id,source='workspace',name=p.name,path=a['path'],size=st.st_size,match=match,reason=reason,**capabilities(p)))
                except (OSError,ValueError):continue
            result['file_results']=rows
            return result
    def _workspace_path(self,id):
        if not isinstance(id,str) or id not in self.items:raise PermissionError('搜尋結果已失效，請重新搜尋。')
        p,mtime,size,sha=self.items[id];p=self.checked(p);st=p.stat()
        if st.st_mtime_ns!=mtime or st.st_size!=size:raise PermissionError('原始檔案已變更，請重新搜尋。')
        return p,sha
    def get(self,source,id,action):
        if source not in ('local','workspace'):raise ValueError('無效檔案來源。')
        if action not in ('open','download','thumbnail','text'):raise ValueError('無效操作。')
        lock=self.local.lock if source=='local' else self.lock
        with lock:
            if source=='local':
                p=self.local._result_path(id);expected=None;check=self.local.checked
            else:p,expected=self._workspace_path(id);check=self.checked
            cap=capabilities(p)
            if action=='open':
                if not cap['can_open']:raise ValueError('此格式不支援直接開啟，請下載檔案。')
                if expected:
                    with p.open('rb') as f:
                        if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise PermissionError('檔案已變更。')
                if source=='local':self.local._result_path(id)
                else:self._workspace_path(id)
                os.startfile(str(p),'open')
                return {'ok':True,'name':p.name}
            if action=='download':
                data=verified_read(p,check,MAX_DOWNLOAD,expected);mime='application/octet-stream'
            elif action=='thumbnail':
                if not cap['image_preview']:raise ValueError('此格式不支援圖片預覽。')
                from PIL import Image,ImageOps
                raw=verified_read(p,check,32*1024**2,expected)
                with Image.open(io.BytesIO(raw)) as im:
                    if im.width*im.height>40_000_000:raise ValueError('圖片尺寸超過預覽上限。')
                    im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1200,1200));b=io.BytesIO();im.save(b,format='JPEG',quality=85);data=b.getvalue()
                mime='image/jpeg'
            else:
                if not cap['previewable']:raise ValueError('此格式不支援文字預覽。')
                data=verified_read(p,check,64*1024,expected)
                try:t=data.decode('utf-8-sig')
                except UnicodeDecodeError:t=data.decode('cp950',errors='replace')
                return {'name':p.name,'text':t}
            if source=='local':self.local._result_path(id)
            else:self._workspace_path(id)
            return {'name':p.name,'data':data,'mime':mime}
