"""Persistent on-device retrieval cache. Never treat cached results as file authority."""
import json,sqlite3
from pathlib import Path
class VisionIndex:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS matches (digest TEXT NOT NULL, query TEXT NOT NULL, revision TEXT NOT NULL, result TEXT NOT NULL, touched INTEGER NOT NULL DEFAULT (unixepoch()), PRIMARY KEY(digest,query,revision))')
    def get(self,digest,query,revision):
        with sqlite3.connect(self.path) as db:
            row=db.execute('SELECT result FROM matches WHERE digest=? AND query=? AND revision=?',(digest,query,revision)).fetchone()
            if row:db.execute('UPDATE matches SET touched=unixepoch() WHERE digest=? AND query=? AND revision=?',(digest,query,revision))
        if not row:return None
        try:
            value=json.loads(row[0])
            if value.get('match') in ('yes','no') and isinstance(value.get('reason'),str):return value
        except (ValueError,TypeError):pass
        return None
    def put(self,digest,query,revision,result):
        if result.get('match') not in ('yes','no'):return
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO matches (digest,query,revision,result) VALUES (?,?,?,?)',(digest,query,revision,json.dumps(result,ensure_ascii=False)))
            db.execute('DELETE FROM matches WHERE rowid IN (SELECT rowid FROM matches ORDER BY touched DESC,rowid DESC LIMIT -1 OFFSET 10000)')
