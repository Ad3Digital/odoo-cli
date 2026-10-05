# Odoo CLI

A small read-only CLI for Odoo projects and tasks, built with Python's standard library. No package installation or private AD3 dependencies required.

## Usage

Requires Python 3.10+. Clone this repository and run:

```sh
python odoo_cli.py --url https://odoo.example.com version
python odoo_cli.py --url https://odoo.example.com --db example --login user@example.com tasks
```

You can also set `ODOO_URL`, `ODOO_DB`, and `ODOO_LOGIN` in your environment. Passwords are requested with a hidden console prompt on each authenticated invocation. Passwords and session cookies are kept in memory only; they are never saved or accepted as command-line arguments. Use an interactive terminal.

Commands: `version`, `auth`, `doctor`, `projects`, `tasks`, `task ID`, `fields MODEL`, and `call MODEL METHOD --params-file FILE`.

`tasks` defaults to the current user's open tasks. Options: `--project ID`, `--all-users`, `--include-closed`. Output is JSON.

`call` accepts a JSON file such as `{"args": [[]], "kwargs": {"fields": ["id", "name"], "limit": 20}}`. Only project.project, project.task, project.task.type and mail.activity are allowed, with search_read, read, search, search_count or fields_get. Mutations are rejected before a network call.

HTTPS is required by default. For a trusted private network, explicitly add `--allow-http` before the command. Redirects are refused, responses capped at 2 MiB, and remote error details suppressed.

## Compatibility and limitations

Uses Odoo's web session JSON-RPC endpoints, not the external JSON-2 API. Live version detection was checked against Odoo 19; authenticated project/task queries have not yet been verified against a live deployment. Task fields and state filters target Odoo 19 and may require adjustment for other versions. Your user's Odoo permissions still apply. This is an independent AD3 tool, not an official Odoo client.

## Tests

```sh
python -m unittest discover
```

MIT licensed.
