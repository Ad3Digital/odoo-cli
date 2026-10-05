"""Read-only Odoo project/task CLI using the web session JSON-RPC API."""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from urllib.request import Request

from urllib.request import HTTPRedirectHandler, build_opener
from urllib.parse import urlsplit

BASE = DB = LOGIN = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_no_redirect(request, timeout):
    return build_opener(NoRedirect).open(request, timeout=timeout)


def read_limited(response):
    data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise OdooError('Response exceeds 2 MiB.')
    return data


MODELS = {'project.project', 'project.task', 'project.task.type', 'mail.activity'}
METHODS = {'search_read', 'read', 'search', 'search_count', 'fields_get'}


class OdooError(Exception):
    pass


def rpc(path, params, session=None):
    headers = {'Content-Type': 'application/json'}
    if session:
        headers['Cookie'] = 'session_id=' + session['session_id']
    data = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params, 'id': 1}).encode()
    try:
        with open_no_redirect(Request(BASE + path, data=data, headers=headers), 20) as response:
            result = json.loads(read_limited(response))
            cookie = response.headers.get('Set-Cookie', '')
    except Exception:
        raise OdooError('Odoo indisponivel ou resposta invalida; nenhuma repeticao automatica.') from None
    if not isinstance(result, dict):
        raise OdooError('Invalid JSON-RPC response.')
    if 'error' in result:
        raise OdooError('Odoo recusou a consulta. Confira autenticacao e permissoes.')
    return result.get('result'), cookie


def auth(password):
    from http.cookies import SimpleCookie
    result, cookie = rpc('/web/session/authenticate', {'db': DB, 'login': LOGIN, 'password': password})
    if not isinstance(result, dict) or not result.get('uid') or result.get('username') != LOGIN:
        raise OdooError('Identidade autenticada nao confere.')
    jar = SimpleCookie()
    jar.load(cookie)
    if 'session_id' not in jar:
        raise OdooError('Servidor nao forneceu sessao.')
    session = dict(base=BASE, db=DB, login=LOGIN, uid=result['uid'], session_id=jar['session_id'].value)
    return session


def call(model, method, args, kwargs, session):
    if model not in MODELS or method not in METHODS:
        raise OdooError('Modelo/metodo nao permitido. Esta CLI e somente leitura.')
    return rpc('/web/dataset/call_kw/' + model + '/' + method,
               dict(model=model, method=method, args=args, kwargs=kwargs), session)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.environ.get('ODOO_URL'))
    parser.add_argument('--db', default=os.environ.get('ODOO_DB'))
    parser.add_argument('--login', default=os.environ.get('ODOO_LOGIN'))
    parser.add_argument('--allow-http', action='store_true', help='Allow HTTP on a trusted private network.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('version')
    sub.add_parser('doctor')
    sub.add_parser('auth', help='Prompt for password and verify authentication; no credentials are saved.')
    sub.add_parser('projects')
    tasks = sub.add_parser('tasks')
    tasks.add_argument('--project', type=int)
    tasks.add_argument('--all-users', action='store_true')
    tasks.add_argument('--include-closed', action='store_true')
    task = sub.add_parser('task')
    task.add_argument('id', type=int)
    fields = sub.add_parser('fields')
    fields.add_argument('model', choices=sorted(MODELS))
    read = sub.add_parser('call')
    read.add_argument('model', choices=sorted(MODELS))
    read.add_argument('method', choices=sorted(METHODS))
    read.add_argument('--params-file', required=True, help='JSON com args e kwargs; sem credenciais.')
    a = parser.parse_args()
    global BASE, DB, LOGIN
    BASE, DB, LOGIN = (a.url or '').rstrip('/'), a.db, a.login
    parsed = urlsplit(BASE)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise OdooError('Provide an origin URL, e.g. https://odoo.example.com.')
    if parsed.scheme == 'http' and not a.allow_http:
        raise OdooError('Use HTTPS or explicitly pass --allow-http on a trusted private network.')
    if a.command != 'version' and (not DB or not LOGIN):
        raise OdooError('Provide --db and --login or ODOO_DB and ODOO_LOGIN.')
    if a.command != 'version' and not sys.stdin.isatty():
        raise OdooError('Authentication requires an interactive terminal.')
    if a.command == 'version':
        output = rpc('/web/webclient/version_info', {})[0]
    elif a.command == 'auth':
        session = auth(getpass.getpass('Odoo password (not saved): '))
        output = dict(authenticated=True, uid=session['uid'], login=LOGIN)
    else:
        session = auth(getpass.getpass('Odoo password (not saved): '))
        info = rpc('/web/session/get_session_info', {}, session)[0]
        if not info or info.get('uid') != session['uid'] or info.get('username') != LOGIN:
            raise OdooError('Session identity does not match.')
        if a.command == 'doctor':
            output = dict(authenticated=True, uid=info['uid'], login=LOGIN, database=DB, base=BASE)
        elif a.command == 'projects':
            output = call('project.project', 'search_read', [[]], dict(fields=['id', 'name', 'user_id'], limit=100), session)
        elif a.command in ('tasks', 'task'):
            domain = []
            if a.command == 'task':
                domain.append(['id', '=', a.id])
            else:
                if a.project:
                    domain.append(['project_id', '=', a.project])
                if not a.all_users:
                    domain.append(['user_ids', 'in', [session['uid']]])
                if not a.include_closed:
                    domain.append(['state', 'not in', ['1_done', '1_canceled']])
            output = call('project.task', 'search_read', [domain], dict(fields=['id', 'name', 'project_id', 'user_ids', 'stage_id', 'state', 'date_deadline', 'priority', 'description'], limit=200, order='priority desc,date_deadline asc,id asc'), session)
        elif a.command == 'fields':
            output = call(a.model, 'fields_get', [], dict(attributes=['string', 'type', 'relation', 'selection']), session)
        else:
            params = json.loads(Path(a.params_file).read_text(encoding='utf-8-sig'))
            if not isinstance(params, dict) or not isinstance(params.get('args', []), list) or not isinstance(params.get('kwargs', {}), dict):
                raise OdooError('Parameters must be an object with args (list) and kwargs (object).')
            output = call(a.model, a.method, params.get('args', []), params.get('kwargs', {}), session)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OdooError, ValueError, OSError) as error:
        print(json.dumps({'ok': False, 'error': str(error) if isinstance(error, OdooError) else 'Arquivo ou parametro invalido.'}, ensure_ascii=False))
        sys.exit(1)
