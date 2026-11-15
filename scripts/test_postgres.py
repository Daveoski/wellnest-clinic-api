"""Run the five gates in order against a pre-submission PostgreSQL database.

WARNING: tests intentionally call /reset and replace all application data.
"""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / '.env')
os.environ['TEST_DATABASE_URL'] = os.environ['DATABASE_URL']
for level in range(1, 6):
    print(f'Level {level}: PostgreSQL verification', flush=True)
    result = subprocess.run([sys.executable, '-m', 'pytest', f'tests/test_level{level}.py', '-q', '-p', 'no:cacheprovider', f'--basetemp=.test-tmp-pg-{level}'], cwd=root)
    if result.returncode:
        raise SystemExit(result.returncode)
