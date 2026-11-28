"""Cooperative, read-only search cancellation; never controls file mutations."""
import threading,secrets
from contextlib import contextmanager
class SearchCancelled(Exception):pass
class SearchProgress:
    def __init__(self):
        self.lock=threading.RLock();self.job=None;self.owner=None
    @contextmanager
    def operation(self,owner=None):
        with self.lock:self.owner=owner
        try:yield self
        finally:
            with self.lock:self.job=None;self.owner=None
    def begin(self,total,kind):
        with self.lock:
            self.job={'id':secrets.token_hex(12),'kind':kind,'total':total,'done':0,'matched':0,'cached':0,'cancelling':False}
    def status(self):
        with self.lock:return dict(self.job) if self.job else None
    def cancel(self,id):
        with self.lock:
            if not self.job or id!=self.job['id']:return False
            self.job['cancelling']=True;return True
    def cancel_owner(self,owner):
        with self.lock:
            if owner and self.job and self.owner==owner:self.job['cancelling']=True
    def cancel_local(self):
        with self.lock:
            if self.job and self.job['kind']=='local':self.job['cancelling']=True
    def check(self):
        with self.lock:
            if self.job and self.job['cancelling']:raise SearchCancelled('已停止圖片搜尋；原始檔案未修改。')
    def step(self,result=None):
        with self.lock:
            self.check()
            if self.job:
                self.job['done']+=1
                self.job['matched']+=int(bool(result and result.get('match')=='yes'))
                self.job['cached']+=int(bool(result and result.get('cached')))
