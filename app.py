"""IITM-inspired reimbursement tracker demo. Python standard library only.
Fictional demo accounts and claims. Not affiliated with IIT Madras.
"""
import os
import io
import re
import json
import html
import time
import hmac
import base64
import hashlib
import secrets
import sqlite3
import mimetypes
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from email.parser import BytesParser
from email.policy import default

ROOT = Path(__file__).resolve().parent
INSTANCE = ROOT / 'instance'
UPLOADS = INSTANCE / 'uploads'
DB = INSTANCE / 'claims.sqlite3'
PORT = int(os.environ.get('PORT', '8000'))
DEMO_MODE = os.environ.get('DEMO_MODE', '1') == '1'
MAX_POST = 7 * 1024 * 1024
ROLE_ORDER = ['faculty', 'department', 'accounts']
ROLE_LABEL = {'student':'Student', 'faculty':'Faculty Advisor', 'department':'Department', 'accounts':'Accounts', 'admin':'Administrator'}


def utcnow():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def connect():
    INSTANCE.mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB, timeout=20)
    cx.row_factory = sqlite3.Row
    cx.execute('PRAGMA foreign_keys=ON')
    cx.execute('PRAGMA journal_mode=WAL')
    return cx


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 170000)
    return salt.hex() + ':' + digest.hex()


def valid_password(password, stored):
    try:
        salt, expected = stored.split(':')
        got = hash_password(password, bytes.fromhex(salt)).split(':')[1]
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def init_database():
    with connect() as cx:
        cx.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
          name TEXT NOT NULL, role TEXT NOT NULL, club TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS claims (
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL REFERENCES users(id),
          club TEXT NOT NULL, purpose TEXT NOT NULL, amount_paise INTEGER NOT NULL,
          expense_date TEXT NOT NULL, receipt_file TEXT, receipt_name TEXT,
          stage TEXT NOT NULL DEFAULT 'faculty', status TEXT NOT NULL DEFAULT 'pending',
          version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          paid_at TEXT, payment_ref TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id INTEGER NOT NULL REFERENCES claims(id),
          actor_id INTEGER NOT NULL REFERENCES users(id), action TEXT NOT NULL,
          detail TEXT NOT NULL DEFAULT '', happened_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          csrf TEXT NOT NULL, expires INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_claim_student ON claims(student_id);
        CREATE INDEX IF NOT EXISTS idx_claim_stage ON claims(stage, status);
        ''')
        if not cx.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
            sample_users = [
                ('student@demo.local', 'Student123!', 'Asha Kumar', 'student', 'Robotics Club'),
                ('treasurer@demo.local', 'Treasurer123!', 'Ravi Mehta', 'student', 'Robotics Club'),
                ('faculty@demo.local', 'Faculty123!', 'Dr. Nair', 'faculty', ''),
                ('department@demo.local', 'Department123!', 'Department Officer', 'department', ''),
                ('accounts@demo.local', 'Accounts123!', 'Accounts Officer', 'accounts', ''),
                ('admin@demo.local', 'Admin123!', 'Demo Administrator', 'admin', '')
            ]
            cx.executemany('INSERT INTO users(email,password_hash,name,role,club) VALUES(?,?,?,?,?)',
                           [(a, hash_password(b), c, d, e) for a,b,c,d,e in sample_users])


def esc(x):
    return html.escape(str(x if x is not None else ''), quote=True)


def rupees(paise):
    return '₹' + format(paise / 100, ',.2f')


def display_id(cid):
    return 'RMB-' + str(cid).zfill(4)


def user_by_token(cx, token):
    if not token: return None
    row = cx.execute('''SELECT u.*, s.csrf FROM sessions s JOIN users u ON s.user_id=u.id
                        WHERE s.token_hash=? AND s.expires>?''',
                     (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
    return row


def status_label(row):
    if row['status'] == 'paid': return 'Paid / Completed'
    if row['status'] == 'rejected': return 'Rejected'
    if row['status'] == 'returned': return 'Returned for Correction'
    if row['stage'] == 'payment': return 'Approved, Awaiting Payment'
    return ROLE_LABEL.get(row['stage'], 'Unknown') + ' Pending'


def badge(row):
    state = row['status']
    css = 'good' if state == 'paid' else 'bad' if state in ('rejected','returned') else 'wait'
    return f'<span class="badge {css}">{esc(status_label(row))}</span>'


def accessible(cx, user, claim):
    if user['role'] == 'admin': return True
    if user['role'] in ROLE_ORDER: return True  # one approver account per stage in this scoped demo
    if claim['student_id'] == user['id']: return True
    return user['email'] == 'treasurer@demo.local' and claim['club'] == user['club']


def notice(msg, type_='success'):
    return f'<div class="notice {esc(type_)}">{esc(msg)}</div>'


def layout(title, body, user=None, refresh=False):
    nav = ''
    pending_notifications = 0
    if user and user['role'] == 'faculty':
        with connect() as ncx:
            pending_notifications = ncx.execute("SELECT COUNT(*) FROM claims WHERE stage='faculty' AND status='pending'").fetchone()[0]
    if user:
        nav = f'''<nav><a href="/">Dashboard</a> <a href="/claims">Claims</a>'''
        if user['role']=='student': nav += ' <a href="/new">Submit Claim</a>'
        if user['role']=='admin': nav += ' <a href="/admin">Administration</a>'
        if user['role']=='faculty': nav += f' <a class="notification-link" href="/notifications" aria-label="Notifications: {pending_notifications} claims waiting">&#128276; Notifications <span class="notification-count">{pending_notifications}</span></a>'
        nav += f'''<span class="right">{esc(user['name'])} ({esc(ROLE_LABEL[user['role']])})
          <form method="post" action="/logout" class="inline"><input type="hidden" name="csrf" value="{esc(user['csrf'])}"><button class="linkbutton">Sign out</button></form></span></nav>'''
    else:
        nav = '<nav><a href="/login">Sign in</a></nav>'
    reload_script = '''<script>
    let lastInteraction = Date.now();
    for (const evt of ['input','focusin','pointerdown','keydown']) document.addEventListener(evt,()=>lastInteraction=Date.now());
    setInterval(()=>{ if(Date.now()-lastInteraction>5000 && !document.querySelector('dialog[open]')) location.reload(); },5000);
    </script>''' if refresh else ''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{esc(title)} | Reimbursement Tracker Demo</title>
      <link rel="stylesheet" href="/static/style.css"></head>
      <body><header><div class="container header-inner"><div class="brand-mark">R</div><div class="brand-copy"><strong>Club Reimbursement Tracker</strong>
        <span class="subtitle">A simpler way to track every approval</span></div><span class="demo-pill">DEMO ENVIRONMENT</span></div></header>
        <div class="container">{nav}<main><div class="page-heading"><div><p class="eyebrow">REIMBURSEMENT PORTAL</p><h1>{esc(title)}</h1></div></div>{body}</main>
        <footer>Academic prototype with fictional information. No official IIT Madras systems or real payments are connected.</footer></div>
        {reload_script}</body></html>'''


def parse_request(handler):
    length = int(handler.headers.get('Content-Length', '0'))
    if length > MAX_POST: raise ValueError('Request is too large. Maximum upload size is 6 MB.')
    raw = handler.rfile.read(length)
    content_type = handler.headers.get('Content-Type', '')
    if content_type.startswith('multipart/form-data'):
        email_data = b'MIME-Version: 1.0\r\nContent-Type: ' + content_type.encode() + b'\r\n\r\n' + raw
        msg = BytesParser(policy=default).parsebytes(email_data)
        result = {}
        for part in msg.iter_parts():
            field = part.get_param('name', header='content-disposition')
            if not field: continue
            filename = part.get_filename()
            blob = part.get_payload(decode=True) or b''
            if filename is not None: result[field] = (filename, blob)
            else: result[field] = blob.decode('utf-8', 'replace')
        return result
    decoded = urllib.parse.parse_qs(raw.decode('utf-8', 'replace'), keep_blank_values=True)
    return {k:v[-1] for k,v in decoded.items()}


def receipt_upload(upload):
    if not upload or not isinstance(upload, tuple) or not upload[0]:
        return None
    filename, content = upload
    if len(content) > 5 * 1024 * 1024: raise ValueError('Receipt exceeds 5 MB.')
    ext = Path(filename).suffix.lower()
    checks = {'.pdf': content.startswith(b'%PDF-'), '.png':content.startswith(b'\x89PNG\r\n\x1a\n'),
              '.jpg':content.startswith(b'\xff\xd8\xff'), '.jpeg':content.startswith(b'\xff\xd8\xff')}
    if ext not in checks or not checks[ext]: raise ValueError('Upload a valid PDF, JPG or PNG receipt.')
    safe_name = Path(filename).name[:100]
    saved = secrets.token_hex(18) + ('.jpg' if ext=='.jpeg' else ext)
    (UPLOADS / saved).write_bytes(content)
    return saved, safe_name


def new_claim_form(user, msg=''):
    return (notice(msg,'error') if msg else '') + f'''<p>Enter a fictional reimbursement request for the video demonstration.</p>
      <form method="post" action="/new" enctype="multipart/form-data" class="formbox">
      <input type="hidden" name="csrf" value="{esc(user['csrf'])}">
      <label>Club <input name="club" required maxlength="80" value="{esc(user['club'])}"></label>
      <label>Purpose <input name="purpose" required maxlength="160" placeholder="Event supplies"></label>
      <label>Amount in rupees <input name="amount" type="number" min="1" max="1000000" step="0.01" required placeholder="3500"></label>
      <label>Expense date <input name="expense_date" type="date" required value="{datetime.now().date().isoformat()}"></label>
      <label>Receipt (PDF, JPG or PNG, max 5 MB) <input name="receipt" type="file" accept=".pdf,.jpg,.jpeg,.png"></label>
      <button type="submit">Submit Reimbursement Claim</button></form>'''


def claim_table(rows):
    if not rows: return '<p>No claims yet. Create one using the Submit Claim page.</p>'
    parts = ['<div class="tablewrap"><table><thead><tr><th>Claim ID</th><th>Purpose</th><th>Club</th><th>Amount</th><th>Current status</th><th>Updated</th></tr></thead><tbody>']
    for row in rows:
        parts.append(f'''<tr><td><a href="/claim/{row['id']}">{display_id(row['id'])}</a></td>
          <td>{esc(row['purpose'])}</td><td>{esc(row['club'])}</td><td>{rupees(row['amount_paise'])}</td>
          <td>{badge(row)}</td><td>{esc(row['updated_at'][:16])}</td></tr>''')
    parts.append('</tbody></table></div>')
    return ''.join(parts)


def progress_tracker(claim, compact=False):
    """Show true stage state; returned/rejected cases are not represented as completed."""
    steps = [('Submitted','submitted'), ('Faculty Advisor','faculty'),
             ('Department','department'), ('Accounts','accounts'), ('Paid','payment')]
    order = {'faculty':1, 'department':2, 'accounts':3, 'payment':4}
    position = order.get(claim['stage'], 1)
    end_state = claim['status']
    parts = ['<div class="progress-track'+(' compact' if compact else '')+'" aria-label="Reimbursement progress">']
    for idx, (label, stage) in enumerate(steps):
        if end_state == 'paid': state = 'complete'
        elif idx == 0 or idx < position: state = 'complete'
        elif idx == position and end_state == 'pending': state = 'active'
        elif idx == position and end_state in ('returned','rejected'): state = 'stopped'
        else: state = 'upcoming'
        symbol = '&#10003;' if state == 'complete' else str(idx + 1)
        parts.append(f'<div class="progress-step {state}"><span class="progress-dot">{symbol}</span><span class="progress-caption">{esc(label)}</span></div>')
    parts.append('</div>')
    if not compact and end_state in ('returned','rejected'):
        parts.append(f'<p class="progress-note">This claim is {esc(status_label(claim).lower())}. The approval flow is paused or stopped.</p>')
    return ''.join(parts)


def student_cards(cx, user):
    counts = cx.execute("""SELECT COUNT(*) AS total,
       SUM(CASE WHEN status='pending' AND stage!='payment' THEN 1 ELSE 0 END) AS pending,
       SUM(CASE WHEN status='pending' AND stage='payment' THEN 1 ELSE 0 END) AS approved,
       SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) AS reimbursed
       FROM claims WHERE student_id=?""", (user['id'],)).fetchone()
    cards = [('Total Claims',counts['total'] or 0,'all'),
             ('Pending Approval',counts['pending'] or 0,'pending'),
             ('Approved',counts['approved'] or 0,'approved'),
             ('Reimbursed',counts['reimbursed'] or 0,'paid')]
    return '<section class="summary-grid" aria-label="Claim overview">'+''.join(
        f'<div class="summary-card {kind}"><span>{esc(label)}</span><strong>{value}</strong></div>'
        for label,value,kind in cards)+'</section>'


def empty_dashboard():
    return """<section class="empty-state dashboard-empty">
      <div class="empty-illustration" aria-hidden="true">&#128196;</div>
      <h2>No reimbursement claims yet</h2>
      <p>Submit your first claim to receive a tracking ID and follow each approval stage in one place.</p>
      <a href="/new" class="button">Create First Claim &rarr;</a>
    </section>"""


def demo_login_buttons():
    if not DEMO_MODE: return ''
    buttons=[]
    for role,label in [('student','Student'),('faculty','Faculty Advisor')]:
        buttons.append(f'<form method="post" action="/demo-login" class="demo-login-form"><input type="hidden" name="role" value="{role}"><button type="submit" class="button secondary">Continue as {label} &rarr;</button></form>')
    return '<section class="quick-login"><div><h2>Quick login for the video</h2><p>Fictional demo accounts only. Choose a role to enter without typing a password.</p></div><div class="quick-login-actions">'+''.join(buttons)+'</div></section>'


def confirmation_screen(claim, kind):
    cid = display_id(claim['id'])
    if kind == 'submitted':
        title='Claim submitted successfully!'
        intro='Your reimbursement request is saved and has been sent to the Faculty Advisor for review.'
        when_label='Submission date'
        timestamp=claim['created_at']
        next_label='Faculty Advisor Pending' if claim['stage']=='faculty' and claim['status']=='pending' else status_label(claim)
        cta='Track My Claim'
    else:
        title='Claim approved successfully!'
        intro='Faculty Advisor approval has been recorded. The claim has moved to the Department for the next review.'
        when_label='Last updated'
        timestamp=claim['updated_at']
        next_label=status_label(claim)
        cta='View Claim &amp; Timeline'
    return f"""<section class="confirmation-card"><div class="success-emblem" aria-hidden="true">&#10003;</div>
      <h2>{title}</h2><p>{intro}</p>
      <dl class="confirmation-details"><div><dt>Claim ID</dt><dd>{cid}</dd></div>
      <div><dt>Amount requested</dt><dd>{rupees(claim['amount_paise'])}</dd></div>
      <div><dt>{when_label}</dt><dd>{esc(timestamp)}</dd></div>
      <div><dt>Current status</dt><dd>{esc(next_label)}</dd></div></dl>
      <a class="button" href="/claim/{claim['id']}">{cta} &rarr;</a>
      <a class="text-link" href="/">Back to dashboard</a></section>"""


def timeline(cx, claim):
    events = cx.execute('''SELECT e.*, u.name actor FROM events e JOIN users u ON e.actor_id=u.id
                           WHERE e.claim_id=? ORDER BY e.id''',(claim['id'],)).fetchall()
    out=['<h2>Approval timeline and audit history</h2><ol class="timeline">']
    for ev in events:
        out.append(f'<li><strong>{esc(ev["action"])}</strong> by {esc(ev["actor"])}<br><small>{esc(ev["happened_at"])}</small>' +
                   (f'<p>{esc(ev["detail"])}</p>' if ev['detail'] else '')+'</li>')
    out.append('</ol><h2>Current approval pipeline</h2><div class="stages">')
    for stage in ['faculty','department','accounts','payment']:
        title = 'Payment recorded' if stage == 'payment' else ROLE_LABEL[stage]
        events_for_stage = [e for e in events if e['action'].startswith(ROLE_LABEL.get(stage,'') + ' approved')]
        if stage=='payment': phase = 'Completed' if claim['status']=='paid' else 'Awaiting' if claim['stage']=='payment' else 'Not reached'
        elif events_for_stage: phase = 'Approved'
        elif claim['stage']==stage and claim['status']=='pending': phase = 'Pending now'
        else: phase = 'Not reached'
        out.append(f'<div class="stage"><b>{esc(title)}</b><span>{esc(phase)}</span></div>')
    out.append('</div>')
    return ''.join(out)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try: self.route_get()
        except Exception as exc:
            self.log_error('GET error: %r', exc)
            self.send_page('Error', notice('An unexpected error occurred.','error'), status=500)

    def do_POST(self):
        try: self.route_post()
        except ValueError as exc:
            self.send_page('Request error', notice(str(exc),'error'),status=400)
        except Exception as exc:
            self.log_error('POST error: %r', exc)
            self.send_page('Error', notice('An unexpected error occurred.','error'),status=500)

    def cookie(self):
        cook = SimpleCookie()
        try: cook.load(self.headers.get('Cookie', ''))
        except Exception: return None
        return cook.get('sid').value if 'sid' in cook else None

    def current_user(self, cx): return user_by_token(cx, self.cookie())

    def send_page(self, title, body, user=None, status=200, refresh=False, cookie=None):
        data = layout(title,body,user,refresh).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline' 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, url, cookie=None):
        self.send_response(303)
        self.send_header('Location',url)
        self.send_header('Cache-Control','no-store')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers()

    def route_get(self):
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        if path=='/static/style.css':
            data = (ROOT/'static'/'style.css').read_bytes()
            self.send_response(200); self.send_header('Content-Type','text/css'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
        with connect() as cx:
            user = self.current_user(cx)
            if not user:
                if path!='/login': return self.redirect('/login')
                login = '''<p>This demonstration uses fictional accounts and no real institutional data.</p><form class="formbox" method="post" action="/login">
                <label>Email <input type="email" required name="email" value="student@demo.local"></label>
                <label>Password <input type="password" required name="password" placeholder="Student123!"></label>
                <button>Sign in</button></form><h2>Demo accounts</h2>
                <div class="tablewrap"><table><tr><th>Role</th><th>Email</th><th>Password</th></tr>
                <tr><td>Student</td><td>student@demo.local</td><td>Student123!</td></tr>
                <tr><td>Faculty Advisor</td><td>faculty@demo.local</td><td>Faculty123!</td></tr>
                <tr><td>Department</td><td>department@demo.local</td><td>Department123!</td></tr>
                <tr><td>Accounts</td><td>accounts@demo.local</td><td>Accounts123!</td></tr>
                <tr><td>Treasurer (read-only for club peers)</td><td>treasurer@demo.local</td><td>Treasurer123!</td></tr>
                <tr><td>Administrator</td><td>admin@demo.local</td><td>Admin123!</td></tr></table></div>'''
                return self.send_page('Sign in',demo_login_buttons()+login)
            if path=='/notifications':
                if user['role']!='faculty':
                    return self.send_page('Access denied',notice('Only the Faculty Advisor can see these notifications.','error'),user,403)
                pending=cx.execute("""SELECT c.*, u.name submitter FROM claims c JOIN users u ON c.student_id=u.id
                    WHERE c.stage='faculty' AND c.status='pending' ORDER BY c.created_at DESC,c.id DESC""").fetchall()
                if pending:
                    alert=f'<div class="notification-banner"><div class="alert-icon">&#128276;</div><div><strong>{len(pending)} claim(s) waiting for your review</strong><p>Open a claim below to review its receipt and approve, return or reject it.</p></div></div>'
                    cards=''.join(f'<a class="notification-card" href="/claim/{c["id"]}"><span class="notification-dot"></span><span><strong>New reimbursement request · {display_id(c["id"])}</strong><small>{esc(c["submitter"])} · {esc(c["club"])} · {rupees(c["amount_paise"])} · {esc(c["created_at"][:16])}</small></span><span class="notification-arrow">Review &rarr;</span></a>' for c in pending)
                    body=alert+f'<div class="notification-list">{cards}</div>'
                else:
                    body='<div class="empty-state"><span class="empty-icon">&#10003;</span><h2>All caught up!</h2><p>No reimbursement claims currently require Faculty Advisor approval.</p><a class="button secondary" href="/">Back to dashboard</a></div>'
                return self.send_page('Notifications',body,user,refresh=True)
            if path in ('/', '/claims'):
                query = urllib.parse.parse_qs(url.query)
                clauses=[];params=[]
                if user['role']=='student':
                    if user['email']=='treasurer@demo.local': clauses.append('(c.student_id=? OR c.club=?)');params.extend([user['id'],user['club']])
                    else: clauses.append('c.student_id=?');params.append(user['id'])
                if user['role'] in ROLE_ORDER and path=='/':
                    clauses.append('c.stage=? AND c.status=?');params.extend([user['role'],'pending'])
                if query.get('q'):
                    q=query['q'][0].strip().upper()
                    numeric=re.sub(r'^(RMB-)?0*','',q)
                    if numeric.isdigit(): clauses.append('c.id=?');params.append(int(numeric))
                    else: clauses.append('0=1')
                if query.get('status') and query['status'][0] in ('pending','returned','rejected','paid'):
                    clauses.append('c.status=?');params.append(query['status'][0])
                where = (' WHERE '+' AND '.join(clauses)) if clauses else ''
                rows=cx.execute('SELECT c.*,u.name submitter FROM claims c JOIN users u ON u.id=c.student_id'+where+' ORDER BY c.updated_at DESC,c.id DESC',params).fetchall()
                heading = 'My claims' if user['role']=='student' else ('Pending approvals' if path=='/' and user['role'] in ROLE_ORDER else 'All claims')
                if user['role']=='admin':heading='All claims'
                summary=f'<p>Logged in as <strong>{esc(user["name"])}</strong>. {esc(ROLE_LABEL[user["role"]])} view.</p>'
                if user['role']=='student':
                    summary += student_cards(cx,user)
                    if path=='/' and rows:
                        summary += '<section class="latest-progress"><div class="section-header"><div><h2>Latest claim progress</h2><p>'+esc(display_id(rows[0]['id']))+' · '+esc(rows[0]['purpose'])+'</p></div><a class="button secondary" href="/claim/'+str(rows[0]['id'])+'">View Claim</a></div>'+progress_tracker(rows[0])+'</section>'
                    if path=='/' and not rows:
                        summary += empty_dashboard()
                    else:
                        summary += '<p><a class="button" href="/new">+ Submit new reimbursement</a></p>'
                if user['role']=='faculty' and path=='/':
                    count=cx.execute("SELECT COUNT(*) FROM claims WHERE stage='faculty' AND status='pending'").fetchone()[0]
                    if count:
                        summary+=f'<div class="notification-banner"><div class="alert-icon">&#128276;</div><div><strong>{count} new reimbursement claim(s) need your approval</strong><p>Students have submitted claims awaiting Faculty Advisor review. <a href="/notifications">View notifications &rarr;</a></p></div></div>'
                    else:
                        summary+='<div class="notification-banner quiet"><div class="alert-icon">&#10003;</div><div><strong>You are all caught up</strong><p>There are no claims awaiting your approval.</p></div></div>'
                if user['role']=='admin':
                    total=cx.execute('SELECT COUNT(*) FROM claims').fetchone()[0]
                    pending=cx.execute("SELECT COUNT(*) FROM claims WHERE status='pending'").fetchone()[0]
                    summary+=f'<div class="stats"><div>Total claims<strong>{total}</strong></div><div>Pending claims<strong>{pending}</strong></div></div><p><a href="/admin">View bottleneck analytics</a></p>'
                if path=='/claims':
                    summary+='''<form method="get" class="filters"><label>Claim ID <input name="q" placeholder="RMB-0001"></label>
                    <label>Status <select name="status"><option value="">All</option><option value="pending">Pending</option><option value="returned">Returned</option><option value="rejected">Rejected</option><option value="paid">Paid</option></select></label><button>Filter</button></form>'''
                if not (user['role']=='student' and path=='/' and not rows): summary+=claim_table(rows)
                if user['role'] in ROLE_ORDER and path=='/':summary+='<p><a href="/claims">View all claims</a></p>'
                return self.send_page(heading,summary,user,refresh=True)
            if path=='/new':
                if user['role']!='student':return self.send_page('Access denied',notice('Only students can submit claims.','error'),user,403)
                return self.send_page('Submit reimbursement',new_claim_form(user),user)
            confirmation_match=re.fullmatch(r'/(submitted|approved)/(\d+)',path)
            if confirmation_match:
                kind,cid=confirmation_match.group(1),int(confirmation_match.group(2))
                claim=cx.execute('SELECT * FROM claims WHERE id=?',(cid,)).fetchone()
                if not claim or not accessible(cx,user,claim):
                    return self.send_page('Not found',notice('Claim not available.','error'),user,404)
                if kind=='submitted' and (user['role']!='student' or claim['student_id']!=user['id']):
                    return self.send_page('Access denied',notice('Only the submitting student can open this confirmation.','error'),user,403)
                if kind=='approved' and user['role']!='faculty':
                    return self.send_page('Access denied',notice('Only the Faculty Advisor can open this confirmation.','error'),user,403)
                return self.send_page('Submission confirmed' if kind=='submitted' else 'Approval confirmed',confirmation_screen(claim,kind),user)
            if path.startswith('/claim/'):
                try: claim_id=int(path.split('/')[2])
                except (IndexError,ValueError):return self.send_page('Not found',notice('Invalid claim ID.','error'),user,404)
                claim=cx.execute('SELECT * FROM claims WHERE id=?',(claim_id,)).fetchone()
                if not claim or not accessible(cx,user,claim):return self.send_page('Not found',notice('Claim not available to your account.','error'),user,404)
                student=cx.execute('SELECT name FROM users WHERE id=?',(claim['student_id'],)).fetchone()['name']
                age=round((datetime.now(timezone.utc)-datetime.strptime(claim['updated_at'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)).total_seconds()/86400,1)
                days_threshold=5
                is_overdue=claim['status']=='pending' and age>days_threshold
                body=f'''<p>{badge(claim)} {'<span class="badge bad">Overdue</span>' if is_overdue else ''}</p>
                  <dl class="details"><dt>Submitted by</dt><dd>{esc(student)}</dd>
                  <dt>Club</dt><dd>{esc(claim['club'])}</dd><dt>Purpose</dt><dd>{esc(claim['purpose'])}</dd>
                  <dt>Amount</dt><dd>{rupees(claim['amount_paise'])}</dd>
                  <dt>Expense date</dt><dd>{esc(claim['expense_date'])}</dd>
                  <dt>Submitted</dt><dd>{esc(claim['created_at'])}</dd>
                  <dt>Last updated</dt><dd>{esc(claim['updated_at'])}</dd></dl>'''
                if claim['receipt_file']: body+=f'<p><a href="/receipt/{claim_id}" target="_blank">View uploaded receipt: {esc(claim["receipt_name"])}</a></p>'
                else:body+='<p>No receipt was attached.</p>'
                body+='<section class="claim-progress-panel"><h2>Approval progress</h2>'+progress_tracker(claim)+'</section>'
                body+=timeline(cx,claim)
                csrf=f'<input type="hidden" name="csrf" value="{esc(user["csrf"])}"><input type="hidden" name="version" value="{claim["version"]}">'
                if user['role']=='student' and claim['student_id']==user['id'] and claim['status']=='returned':
                    body+=f'''<h2>Correct and resubmit</h2><p>Keep the same claim ID and upload a replacement receipt if needed.</p>
                    <form method="post" action="/resubmit/{claim_id}" enctype="multipart/form-data" class="formbox">{csrf}
                    <label>Updated purpose <input name="purpose" required maxlength="160" value="{esc(claim['purpose'])}"></label>
                    <label>Replacement receipt <input type="file" name="receipt" accept=".pdf,.jpg,.jpeg,.png"></label>
                    <button>Resubmit claim</button></form>'''
                if user['role'] in ROLE_ORDER and claim['status']=='pending' and claim['stage']==user['role']:
                    body+=f'''<h2>Approval decision</h2><form method="post" action="/decide/{claim_id}" class="formbox">{csrf}
                    <label>Reason or note <textarea name="reason" rows="3" placeholder="Required for return or rejection"></textarea></label>
                    <div class="actions"><button name="decision" value="approve">Approve</button>
                    <button name="decision" value="return" class="secondary">Return for Correction</button>
                    <button name="decision" value="reject" class="danger">Reject</button></div></form>'''
                if user['role']=='accounts' and claim['stage']=='payment' and claim['status']=='pending':
                    body+=f'''<h2>Record payment</h2><p>This records a fictional payment only. No funds move.</p>
                    <form method="post" action="/pay/{claim_id}" class="formbox">{csrf}
                    <label>Simulated transaction reference <input name="payment_ref" maxlength="80" placeholder="DEMO-PAID-001"></label>
                    <button>Mark as Paid</button></form>'''
                if claim['status']=='paid':body+=f'<p>Payment recorded: {esc(claim["paid_at"])}. Reference: {esc(claim["payment_ref"] or "Not provided")}</p>'
                return self.send_page(display_id(claim_id),body,user,refresh=(user['role']=='student' and claim['status']=='pending'))
            if path.startswith('/receipt/'):
                try: claim_id=int(path.rsplit('/',1)[1])
                except ValueError: return self.redirect('/claims')
                claim=cx.execute('SELECT * FROM claims WHERE id=?',(claim_id,)).fetchone()
                if not claim or not accessible(cx,user,claim) or not claim['receipt_file']:
                    return self.send_page('Not found',notice('Receipt not available.','error'),user,404)
                stored = UPLOADS / Path(claim['receipt_file']).name
                if not stored.is_file():return self.send_page('Not found',notice('Receipt file missing.','error'),user,404)
                data=stored.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type',mimetypes.guess_type(str(stored))[0] or 'application/octet-stream')
                self.send_header('Content-Disposition','inline; filename="receipt"')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data);return
            if path=='/admin':
                if user['role']!='admin':return self.send_page('Access denied',notice('Administrator access required.','error'),user,403)
                allrows=cx.execute('SELECT * FROM claims').fetchall()
                pending=[r for r in allrows if r['status']=='pending']
                def days(row):return (datetime.now(timezone.utc)-datetime.strptime(row['updated_at'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)).total_seconds()/86400
                overdue=sum(days(r)>5 for r in pending)
                counts=[(ROLE_LABEL[role],sum(r['stage']==role for r in pending)) for role in ROLE_ORDER]
                rows=''.join(f'<tr><td>{esc(k)}</td><td>{v}</td></tr>' for k,v in counts)
                body=f'''<p>All figures come from the local demonstration database, not IIT Madras records.</p>
                    <div class="stats"><div>Pending<strong>{len(pending)}</strong></div><div>Overdue (&gt;5 days)<strong>{overdue}</strong></div><div>Paid<strong>{sum(r['status']=='paid' for r in allrows)}</strong></div></div>
                    <h2>Current bottleneck counts</h2><table><tr><th>Stage</th><th>Pending claims</th></tr>{rows}</table>
                    <p>A stage's pending count is not a reliable measure of its average processing duration until historical cases are collected.</p>
                    <h2>Demo reset</h2><p>Use the command <code>python reset_demo.py</code> in the Codespaces terminal to clear fictional claims.</p>'''
                return self.send_page('Demo analytics',body,user,refresh=True)
            return self.send_page('Not found',notice('Page not found.','error'),user,404)

    def route_post(self):
        path=urllib.parse.urlsplit(self.path).path
        data=parse_request(self)
        with connect() as cx:
            if path=='/demo-login':
                if not DEMO_MODE:
                    return self.send_page('Unavailable',notice('Demo quick login is disabled.','error'),status=403)
                selected=str(data.get('role',''))
                credentials={'student':'student@demo.local','faculty':'faculty@demo.local'}
                if selected not in credentials:
                    return self.send_page('Request error',notice('Unknown demo role.','error'),status=400)
                row=cx.execute('SELECT * FROM users WHERE email=?',(credentials[selected],)).fetchone()
                if not row: return self.send_page('Unavailable',notice('Demo account was not found.','error'),status=500)
                token=secrets.token_urlsafe(32)
                cx.execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),row['id'],secrets.token_urlsafe(24),int(time.time())+8*3600))
                cx.commit()
                return self.redirect('/',f'sid={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=28800')
            if path=='/login':
                row=cx.execute('SELECT * FROM users WHERE email=?',(str(data.get('email','')).lower().strip(),)).fetchone()
                if not row or not valid_password(str(data.get('password','')),row['password_hash']):
                    return self.send_page('Sign in',notice('Incorrect email or password.','error')+'<p><a href="/login">Try again</a></p>',status=401)
                token=secrets.token_urlsafe(32)
                cx.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],secrets.token_urlsafe(24),int(time.time())+8*3600))
                cx.commit()
                return self.redirect('/', f'sid={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=28800')
            user=self.current_user(cx)
            if not user:return self.redirect('/login')
            if not hmac.compare_digest(str(data.get('csrf','')),user['csrf']):
                return self.send_page('Forbidden',notice('Invalid form token. Refresh the page.','error'),user,403)
            if path=='/logout':
                cx.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256((self.cookie() or '').encode()).hexdigest(),))
                cx.commit();return self.redirect('/login','sid=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
            if path=='/new':
                if user['role']!='student':return self.send_page('Forbidden',notice('Only students can submit.','error'),user,403)
                club=str(data.get('club','')).strip()[:80]
                purpose=str(data.get('purpose','')).strip()[:160]
                expense_date=str(data.get('expense_date','')).strip()
                try: amount=round(float(data.get('amount',''))*100)
                except (TypeError,ValueError):raise ValueError('Enter a valid amount.')
                if not club or not purpose or amount<100 or amount>100000000:raise ValueError('Provide a club, purpose and valid amount.')
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',expense_date):raise ValueError('Enter a valid expense date.')
                receipt=receipt_upload(data.get('receipt'))
                now=utcnow()
                cur=cx.execute('''INSERT INTO claims(student_id,club,purpose,amount_paise,expense_date,receipt_file,receipt_name,stage,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,'faculty','pending',?,?)''',
                   (user['id'],club,purpose,amount,expense_date,receipt[0] if receipt else None,receipt[1] if receipt else None,now,now))
                cid=cur.lastrowid
                cx.execute('INSERT INTO events(claim_id,actor_id,action,detail,happened_at) VALUES(?,?,?,?,?)',
                           (cid,user['id'],'Submitted','Claim sent to Faculty Advisor for review.',now))
                cx.commit();return self.redirect(f'/submitted/{cid}')
            match=re.fullmatch(r'/(decide|resubmit|pay)/(\d+)',path)
            if match:
                action,cid=match.group(1),int(match.group(2))
                claim=cx.execute('SELECT * FROM claims WHERE id=?',(cid,)).fetchone()
                if not claim:return self.send_page('Not found',notice('Claim not found.','error'),user,404)
                try: version=int(data.get('version','-1'))
                except ValueError:version=-1
                if version!=claim['version']:
                    return self.send_page('Updated elsewhere',notice('Claim changed in another window. Open the current claim and try again.','error')+f'<p><a href="/claim/{cid}">View latest claim</a></p>',user,409)
                now=utcnow()
                if action=='decide':
                    if user['role']!=claim['stage'] or user['role'] not in ROLE_ORDER or claim['status']!='pending':
                        return self.send_page('Forbidden',notice('You are not the current approver.','error'),user,403)
                    decision=data.get('decision','')
                    if decision not in ('approve','return','reject'):raise ValueError('Invalid decision.')
                    reason=str(data.get('reason','')).strip()[:500]
                    if decision in ('return','reject') and not reason:raise ValueError('Enter a reason for returning or rejecting a claim.')
                    if decision=='approve':
                        next_stage={'faculty':'department','department':'accounts','accounts':'payment'}[claim['stage']]
                        newstatus='pending'; label=ROLE_LABEL[user['role']]+' approved'
                    else:
                        next_stage=claim['stage'];newstatus='returned' if decision=='return' else 'rejected'
                        label='Returned for Correction' if decision=='return' else 'Rejected'
                    cx.execute('UPDATE claims SET stage=?,status=?,updated_at=?,version=version+1 WHERE id=?',
                               (next_stage,newstatus,now,cid))
                    cx.execute('INSERT INTO events(claim_id,actor_id,action,detail,happened_at) VALUES(?,?,?,?,?)',
                               (cid,user['id'],label,reason,now))
                elif action=='resubmit':
                    if user['role']!='student' or claim['student_id']!=user['id'] or claim['status']!='returned':
                        return self.send_page('Forbidden',notice('Only the submitting student can correct a returned claim.','error'),user,403)
                    purpose=str(data.get('purpose','')).strip()[:160]
                    if not purpose: raise ValueError('Purpose is required.')
                    receipt=receipt_upload(data.get('receipt'))
                    if receipt:
                        cx.execute('UPDATE claims SET purpose=?,receipt_file=?,receipt_name=?,status=?,updated_at=?,version=version+1 WHERE id=?',
                                   (purpose,receipt[0],receipt[1],'pending',now,cid))
                    else:
                        cx.execute('UPDATE claims SET purpose=?,status=?,updated_at=?,version=version+1 WHERE id=?',
                                   (purpose,'pending',now,cid))
                    cx.execute('INSERT INTO events(claim_id,actor_id,action,detail,happened_at) VALUES(?,?,?,?,?)',
                               (cid,user['id'],'Resubmitted','Student corrected the claim and resubmitted it to the same stage.',now))
                else:
                    if user['role']!='accounts' or claim['stage']!='payment' or claim['status']!='pending':
                        return self.send_page('Forbidden',notice('Accounts can record payment only after all approvals.','error'),user,403)
                    ref=str(data.get('payment_ref','')).strip()[:80]
                    cx.execute('UPDATE claims SET status=?,paid_at=?,payment_ref=?,updated_at=?,version=version+1 WHERE id=?',
                               ('paid',now,ref,now,cid))
                    cx.execute('INSERT INTO events(claim_id,actor_id,action,detail,happened_at) VALUES(?,?,?,?,?)',
                               (cid,user['id'],'Marked Paid','Fictional payment recorded. '+ref,now))
                cx.commit()
                if action=='decide' and decision=='approve' and user['role']=='faculty':
                    return self.redirect(f'/approved/{cid}')
                return self.redirect(f'/claim/{cid}')
            return self.send_page('Not found',notice('Action not found.','error'),user,404)


def main():
    init_database()
    server=ThreadingHTTPServer(('0.0.0.0',PORT),Handler)
    print(f'Reimbursement demo running at http://127.0.0.1:{PORT}',flush=True)
    print('All data is fictional. Press Ctrl+C to stop.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt: pass
    finally:server.server_close()

if __name__=='__main__':main()
