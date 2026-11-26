"""Bootstrap the private virtual environment; invoked by the Windows CMD files."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 11):
        raise SystemExit('Install Python 3.11 or newer from python.org, then try again.')
    os.chdir(ROOT)
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('Preparing your workshop Python environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    lock = ROOT / 'requirements.lock.txt'
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    marker = environment / 'pcai-requirements.sha256'
    if not marker.exists() or marker.read_text() != digest:
        subprocess.run([str(python), '-m', 'pip', 'install', '--require-hashes', '-r', str(lock)], check=True)
        marker.write_text(digest)
    subprocess.run([str(python), '-m', 'scripts.workshop', *sys.argv[1:]], check=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as exc:
        code = getattr(exc, 'returncode', 'unknown')
        print(f'The setup or app command did not finish (exit code {code}). Read the error above, fix that step, and run the CMD file again.', file=sys.stderr)
        sys.exit(1)
