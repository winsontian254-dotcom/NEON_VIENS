#!/usr/bin/env python3
"""Export the Neon Veins accounts database (users, friends, sessions, invites, cloud-save metadata) to JSON and CSV files.

    NV_ADMIN_TOKEN=... python3 server/export.py [--tables users,saves] [--full] [--redact] [--out DIR] [--api URL]

It talks to GET /api/admin/export on the deployed Worker, which only exists when the Worker has an ADMIN_TOKEN secret (see the "Accounts, friends &
cloud saves" section of README.md). The token is read from the NV_ADMIN_TOKEN environment variable, or typed at a hidden prompt: it is
never taken from the command line, so it does not end up in your shell history. Password hashes, salts and session token hashes are never
exported (the server does not send them). The files contain email addresses: keep them private and delete them when you are done.
Standard library only."""
import argparse, csv, datetime, getpass, json, os, sys, urllib.error, urllib.parse, urllib.request

DEFAULT_API = 'https://neon-veins-api.winsontian254.workers.dev'
TABLES = ['users', 'friends', 'sessions', 'invites', 'saves']
TIME_COLS = ('created', 'last_seen', 'updated', 'expires')   # epoch milliseconds in the database


def get(api, token, path, params):
    url = api.rstrip('/') + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token, 'User-Agent': 'neon-veins-export/1.0', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        why = {401: 'The admin token was refused.', 404: 'The export route is not there: set the ADMIN_TOKEN secret (at least 24 characters) and redeploy the Worker.',
               429: 'Too many wrong attempts from this address. Wait a few minutes.'}.get(e.code)
        try: detail = json.loads(e.read().decode('utf-8')).get('error', '')
        except Exception: detail = ''
        sys.exit('error %d: %s' % (e.code, why or detail or e.reason))
    except urllib.error.URLError as e:
        sys.exit('could not reach %s (%s)' % (api, e.reason))


def iso(ms):
    try: return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    except Exception: return ''


def cell(v):
    if isinstance(v, str) and v[:1] in ('=', '+', '-', '@', '\t', '\r'): return "'" + v   # a spreadsheet must not run it as a formula
    return v


def write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f: f.write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--api', default=os.environ.get('NV_API', DEFAULT_API), help='Worker URL (default: the deployed one, or NV_API)')
    ap.add_argument('--tables', default=','.join(TABLES), help='comma list of: ' + ', '.join(TABLES))
    ap.add_argument('--full', action='store_true', help='include the cloud-save data itself (JSON only, 20 saves per request)')
    ap.add_argument('--redact', action='store_true', help='leave email, bio and activity out of the users table')
    ap.add_argument('--out', help='output folder (default: neon-veins-export-<date>)')
    a = ap.parse_args()
    tables = [t.strip() for t in a.tables.split(',') if t.strip()]
    bad = [t for t in tables if t not in TABLES]
    if bad: sys.exit('unknown table(s): ' + ', '.join(bad))
    token = os.environ.get('NV_ADMIN_TOKEN', '').strip()
    if not token:
        if sys.stdin.isatty(): token = getpass.getpass('Admin token (hidden): ').strip()
        if not token: sys.exit('Set NV_ADMIN_TOKEN (or run this in a terminal to be asked for it).')
    summary = get(a.api, token, '/api/admin/export', {'table': 'summary'})   # first request: a wrong token or a missing route stops here, before anything is written
    out = a.out or 'neon-veins-export-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    os.makedirs(out, mode=0o700, exist_ok=True)
    write_private(os.path.join(out, 'summary.json'), json.dumps(summary, indent=2) + '\n')
    print('accounts: %d users (%d new this week, %d active today), %d friend links, %d cloud saves' % (summary['users'], summary['new_users_7d'], summary['active_users_24h'], summary['friends'], summary['saves']))
    for t in tables:
        rows, off = [], 0
        step = 20 if (a.full and t == 'saves') else 1000
        while True:
            q = {'table': t, 'limit': step, 'offset': off}
            if a.full and t == 'saves': q['full'] = 1
            if a.redact and t == 'users': q['redact'] = 1
            page = get(a.api, token, '/api/admin/export', q)
            rows += page['rows']; off += page['count']
            if page['count'] < step: break
        write_private(os.path.join(out, t + '.json'), json.dumps(rows, indent=2, ensure_ascii=False) + '\n')
        cols = [c for c in (rows[0].keys() if rows else []) if c != 'data']
        head = []
        for c in cols: head += [c] + ([c + '_iso'] if c in TIME_COLS else [])
        lines = []
        w = csv.writer(_Sink(lines)); w.writerow(head)
        for r in rows:
            row = []
            for c in cols: row += [cell(r[c])] + ([iso(r[c])] if c in TIME_COLS else [])
            w.writerow(row)
        write_private(os.path.join(out, t + '.csv'), ''.join(lines))
        print('  %-9s %6d rows -> %s/%s.json, .csv' % (t, len(rows), out, t))
    print('Done. These files hold personal data (emails): keep them private and delete them when you are finished.')


class _Sink:
    def __init__(self, lines): self.lines = lines
    def write(self, s): self.lines.append(s)


if __name__ == '__main__':
    main()
