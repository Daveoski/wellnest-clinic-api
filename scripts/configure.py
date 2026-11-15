"""Generate private keys and upload them through stdin, never command arguments."""
import secrets
import subprocess
from pathlib import Path
from dotenv import dotenv_values, set_key

root = Path(__file__).resolve().parents[1]
env = root / '.env'
values = dotenv_values(env)
for name in ('API_KEY', 'CURSOR_SECRET'):
    value = values.get(name) or secrets.token_urlsafe(32)
    set_key(env, name, value)
    result = subprocess.run(['vercel.cmd', 'env', 'add', name, 'production', '--sensitive'], input=value, text=True, cwd=root, capture_output=True)
    print(name + ': ' + ('configured' if result.returncode == 0 else 'FAILED'))
    if result.returncode:
        raise SystemExit(result.stderr)
print('Private values saved only in ignored .env')
