"""Small OS boundary; no shell interpretation of user-supplied paths."""
import os,sys,stat,subprocess
from pathlib import Path
MAC=sys.platform=='darwin'
def is_link(p):
    p=Path(p)
    try:
        st=p.lstat()
        return stat.S_ISLNK(st.st_mode) or bool(getattr(st,'st_file_attributes',0)&0x400)
    except FileNotFoundError:return False
def open_target(target,reveal=False):
    if MAC:
        args=['/usr/bin/open']
        if reveal:args.append('-R')
        subprocess.run(args+[str(target)],check=True,timeout=15)
    elif os.name=='nt':
        os.startfile(str(Path(target).parent) if reveal else str(target),'open')
    else:raise RuntimeError('Unsupported operating system')
def open_browser(url):
    if MAC:subprocess.run(['/usr/bin/open',url],check=True,timeout=15)
    else:os.startfile(url)
def lock_instance(f):
    if os.name=='nt':
        import msvcrt
        f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
def verify_mac_handle(f,path,check):
    if not MAC:return
    import fcntl
    actual=Path(os.fsdecode(fcntl.fcntl(f.fileno(),50,b'\0'*1024).split(b'\0',1)[0]))
    if actual.resolve()!=Path(path).resolve():raise PermissionError('File path changed')
    check(actual)
