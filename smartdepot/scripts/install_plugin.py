"""Install this local bundle in OpenCode v2's global plugin discovery directory."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.package import source_files, scan, write_manifest


def install(destination):
    if destination.exists():
        marker = destination / '.pcai-plugin-installed.json'
        if not marker.exists() or json.loads(marker.read_text()).get('name') != 'opencode-pcai':
            raise ValueError('The destination is not an installation managed by this pack. Existing files were preserved.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_manifest()
    stage = Path(tempfile.mkdtemp(prefix='.pcai-stage-', dir=destination.parent.parent))
    backup = None
    try:
        for source, relative in source_files():
            data = source.read_bytes()
            scan(data, relative)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (stage / '.pcai-plugin-installed.json').write_text(json.dumps({'name': 'opencode-pcai', 'version': '0.1.2'}))
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix='.pcai-backup-', dir=destination.parent.parent))
            backup.rmdir()
            destination.rename(backup)
        try:
            stage.rename(destination)
        except OSError:
            if backup is not None:
                backup.rename(destination)
                backup = None
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
    print('PCAI PLUGIN INSTALLED: ' + str(destination))
    print('OpenCode v2.3.2+ is required. Fully quit and reopen OpenCode PCAI, then use /pcai-help.')
    print('Existing model/provider settings were not edited. No API key was copied.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, help='Optional alternate plugin directory, mainly for isolated validation')
    args = parser.parse_args()
    config = Path(os.getenv('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'opencode'
    install((args.target or config / 'plugins/pcai').resolve())


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        print('Plugin installation did not finish: ' + str(exc), file=sys.stderr)
        sys.exit(1)
