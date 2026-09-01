import os, json, sqlite3, secrets, hashlib, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DB=os.environ.get('DB_PATH','/data/motion365.db')
PORT=int(os.environ.get('PORT','8080'))
ROLE_ALIASES={'explorer':'explorer','member':'member','members':'member','world':'world','worlds':'world','portal':'portal','portals':'portal','architect':'architect','admin':'architect','ecosystem':'explorer','ecosystems':'explorer','node':'member'}
PERMS={
 'explorer':['read'],
 'member':['read'],
 'world':['read'],
 'portal':['read'],
 'architect':['read','create','update','delete','codes','manage']
}
ENTITY_TYPES={'ecosystem','world','portal','node'}

def conn():
 c=sqlite3.connect(DB, timeout=15)
 c.row_factory=sqlite3.Row
 return c

def init_db():
 os.makedirs(os.path.dirname(DB) or '.',exist_ok=True)
 c=conn()
 c.execute('CREATE TABLE IF NOT EXISTS codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, role TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, used_at TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, role TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS destinations (id TEXT PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT \'\', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
 c.commit(); c.close()

def normalize_role(role): return ROLE_ALIASES.get(str(role or '').strip().lower(), str(role or '').strip().lower())
def clean(s, default=''): return str(s if s is not None else default).strip()
def token_hash(t): return hashlib.sha256(t.encode()).hexdigest()[:24]
def new_id(): return secrets.token_urlsafe(9).replace('-','_')
def new_code(role): return 'M365-%s-%s' % (role.upper(), secrets.token_hex(5).upper())
def make_token(role):
 t=secrets.token_urlsafe(32); c=conn(); c.execute('INSERT OR REPLACE INTO sessions(token,role,created_at,expires_at) VALUES(?,?,?,?)',(t,role,time.time(),time.time()+86400)); c.commit(); c.close(); return t

def get_role(h):
 raw=h.get('Authorization','')
 if not raw.lower().startswith('bearer '): return None
 t=raw.split(None,1)[1].strip(); c=conn(); r=c.execute('SELECT role FROM sessions WHERE token=? AND expires_at>?',(t,time.time())).fetchone(); c.close(); return r['role'] if r else None

def item(r): return {'id':r['id'],'type':r['type'],'name':r['name'],'description':r['description'],'created_at':r['created_at'],'updated_at':r['updated_at']}

class Handler(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*a): pass
 def send_json(self,status,data):
  b=json.dumps(data,separators=(',',':')).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
 def read_json(self):
  try:
   n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n) or b'{}')
  except Exception: return {}
 def auth(self,needed=None):
  role=get_role(self.headers)
  if not role: self.send_json(401,{'error':'Authentication required'}); return None
  if needed and needed not in PERMS.get(role,[]): self.send_json(403,{'error':'Permission denied'}); return None
  return role
 def do_GET(self):
  p=urlparse(self.path).path
  if p in ('/api/health','/health'):
   self.send_json(200,{'ok':True,'service':'motion365'}); return
  if p=='/api/session':
   role=get_role(self.headers)
   self.send_json(200,{'authenticated':bool(role),'role':role,'permissions':PERMS.get(role,[]) if role else []}); return
  if p in ('/api/destinations','/api/entities'):
   if not self.auth('read'): return
   c=conn(); rows=c.execute('SELECT * FROM destinations ORDER BY created_at DESC').fetchall(); c.close(); self.send_json(200,[item(r) for r in rows]); return
  if p=='/':
   self.send_response(404); self.end_headers(); return
  self.send_json(404,{'error':'Not found'})
 def do_POST(self):
  p=urlparse(self.path).path; d=self.read_json()
  if p=='/api/access':
   code=clean(d.get('code')).upper(); c=conn(); r=c.execute('SELECT id,role FROM codes WHERE code=? AND used=0', (code,)).fetchone()
   if not r: c.close(); self.send_json(401,{'error':'Invalid or already used access code'}); return
   role=normalize_role(r['role'])
   if role not in PERMS: c.close(); self.send_json(400,{'error':'Invalid role'}); return
   c.execute('UPDATE codes SET used=1,used_at=CURRENT_TIMESTAMP WHERE id=?',(r['id'],)); c.commit(); c.close(); self.send_json(200,{'token':make_token(role),'role':role,'permissions':PERMS[role]}); return
  if p=='/api/codes':
   if not self.auth('codes'): return
   role=normalize_role(d.get('role'))
   if role not in PERMS: self.send_json(400,{'error':'Unsupported role'}); return
   code=new_code(role); c=conn(); c.execute('INSERT INTO codes(code,role) VALUES(?,?)',(code,role)); c.commit(); c.close(); self.send_json(201,{'code':code,'role':role}); return
  if p in ('/api/destinations','/api/entities'):
   if not self.auth('create'): return
   typ=clean(d.get('type')).lower(); name=clean(d.get('name')); desc=clean(d.get('description'))
   if typ not in ENTITY_TYPES: self.send_json(400,{'error':'Choose ecosystem, world, portal, or node'}); return
   if not name: self.send_json(400,{'error':'Name is required'}); return
   ident=new_id(); c=conn(); c.execute('INSERT INTO destinations(id,type,name,description) VALUES(?,?,?,?)',(ident,typ,name,desc)); c.commit(); r=c.execute('SELECT * FROM destinations WHERE id=?',(ident,)).fetchone(); c.close(); self.send_json(201,item(r)); return
  self.send_json(404,{'error':'Not found'})
 def do_PATCH(self):
  p=urlparse(self.path).path; ident=p.rsplit('/',1)[-1]
  if not p.startswith('/api/destinations/') and not p.startswith('/api/entities/'): self.send_json(404,{'error':'Not found'}); return
  if not self.auth('update'): return
  d=self.read_json(); fields=[]; vals=[]
  for k in ('type','name','description'):
   if k in d:
    v=clean(d[k]).lower() if k=='type' else clean(d[k]);
    if k=='type' and v not in ENTITY_TYPES: self.send_json(400,{'error':'Invalid entity type'}); return
    if k=='name' and not v: self.send_json(400,{'error':'Name is required'}); return
    fields.append(k+'=?'); vals.append(v)
  if not fields: self.send_json(400,{'error':'Nothing to update'}); return
  vals.extend([ident]); c=conn(); cur=c.execute('UPDATE destinations SET '+','.join(fields)+",updated_at=CURRENT_TIMESTAMP WHERE id=?",vals); c.commit(); r=c.execute('SELECT * FROM destinations WHERE id=?',(ident,)).fetchone(); c.close()
  if not cur.rowcount: self.send_json(404,{'error':'Entity not found'}); return
  self.send_json(200,item(r))
 def do_DELETE(self):
  p=urlparse(self.path).path; ident=p.rsplit('/',1)[-1]
  if not p.startswith('/api/destinations/') and not p.startswith('/api/entities/'): self.send_json(404,{'error':'Not found'}); return
  if not self.auth('delete'): return
  c=conn(); cur=c.execute('DELETE FROM destinations WHERE id=?',(ident,)); c.commit(); c.close();
  if not cur.rowcount: self.send_json(404,{'error':'Entity not found'}); return
  self.send_json(200,{'ok':True,'id':ident})

init_db()
ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
