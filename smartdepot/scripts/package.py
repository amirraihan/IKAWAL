"""Build a sharing ZIP from an explicit source allowlist, excluding all working state."""
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = {'.opencode', 'app', 'scripts', 'tests', 'docs', 'artifacts', 'certs', 'deploy', 'assets', 'third-party'}
FILES = {'README.md', 'START HERE.html', 'PCAI-Plugin-Explained.html', 'AGENTS.md', 'LICENSE', '.gitignore', '.dockerignore', 'Dockerfile', 'launcher.py', 'opencode.json', 'requirements.txt', 'requirements.lock.txt', 'requirements-dev.txt', 'index.mjs', 'package.json', 'bundle-manifest.json'}
BLOCKED = {'.local', '.venv', 'dist', '.git', '__pycache__', '.pytest_cache', 'node_modules'}
SECRET = [rb'sk-[A-Za-z0-9_-]{16,}', rb'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----', rb'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}']


def scan(data, name):
    if any(re.search(pattern, data) for pattern in SECRET):
        raise ValueError('Potential credential/private key in ' + str(name))
    if str(name).endswith(('.tgz', '.tar.gz')):
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for item in archive.getmembers():
                if item.isfile():
                    scan(archive.extractfile(item).read(), item.name)


def source_files():
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if any(part in BLOCKED for part in relative.parts):
            continue
        if relative.parts[0] not in DIRECTORIES and str(relative) not in FILES and not (len(relative.parts) == 1 and path.suffix == '.cmd'):
            continue
        if path.is_symlink():
            raise ValueError('Do not package symlinks: ' + str(relative))
        if path.is_file():
            if path.suffix in ('.log', '.pyc') or path.name.startswith('.env'):
                continue
            yield path, relative


def write_manifest():
    files = {}
    for path, relative in source_files():
        if relative.as_posix() == 'bundle-manifest.json':
            continue
        data = path.read_bytes()
        scan(data, relative)
        files[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    (ROOT / 'bundle-manifest.json').write_text(json.dumps({'plugin': 'pcai', 'version': '0.1.2', 'files': files}, indent=2) + '\n', encoding='utf-8')


def build(output=None):
    output = Path(output or ROOT / 'dist/PCAI_OpenCode_Plugin_Windows.zip').resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_manifest()
    manifest = {}
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, relative in source_files():
            data = path.read_bytes()
            scan(data, relative)
            name = relative.as_posix()
            manifest[name] = hashlib.sha256(data).hexdigest()
            archive.writestr('HPE-PCAI/' + name, data)
        archive.writestr('HPE-PCAI/MANIFEST.sha256.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity check failed.')
        for name in archive.namelist():
            if any(part in BLOCKED for part in Path(name).parts):
                raise ValueError('Working state was included in the ZIP.')
    print(json.dumps({'path': str(output), 'files': len(manifest), 'size': output.stat().st_size, 'md5': hashlib.md5(output.read_bytes()).hexdigest()}, indent=2))
    return output


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else None)
