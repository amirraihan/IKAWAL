"""Interactive local setup and repeatable build/import/deploy commands. No shell interpolation."""
import argparse
import base64
import csv
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / '.local'
INTERNAL = 'http://litellm.litellm.svc.cluster.local:4000/v1'
VPN = 'https://litellm.htp-ai-ai-application.awanheitech.local/v1'
MODELS = ('deepseek-ai/deepseek-v4.1-flash', 'qwen2.5:32b', 'gpt-oss:20b', 'llama3.2:3b')


def private_directory():
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    if os.name == 'nt':
        info = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], check=True, capture_output=True, text=True)
        sid = next(csv.reader(info.stdout.strip().splitlines()))[1]
        subprocess.run(['icacls', str(PRIVATE), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F'], check=True, capture_output=True)
    else:
        PRIVATE.chmod(0o700)


def save_private(path, data):
    private_directory()
    payload = json.dumps(data, indent=2) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') == payload:
        return
    fd, temporary = tempfile.mkstemp(prefix='pcai-', dir=PRIVATE)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_private(name):
    path = PRIVATE / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def ask(label, default='', validator=None):
    while True:
        value = input(label + (f' [{default}]' if default else '') + ': ').strip() or default
        if value and (validator is None or validator(value)):
            return value
        print('Enter a valid value for this field.')


def key(label, existing=''):
    print('Type or paste the value; characters will appear as * marks.')
    while True:
        prompt = label + (' (Enter keeps the saved key)' if existing else '')
        value = masked_input(prompt).strip()
        if not value and existing:
            print('Saved key kept; the key remains hidden.')
            return existing
        if not value:
            print('No key was received. Paste your LiteLLM key and press Enter.')
            continue
        if any(c.isspace() for c in value):
            print("The pasted value contains spaces. Paste only the secret, without a 'Bearer ' prefix, then press Enter.")
            continue
        print(f'Secret received ({len(value)} characters, hidden).')
        return value


def masked_input(prompt):
    if not sys.stdin.isatty():
        raise ValueError('Run this CMD file in a normal console window so secret input stays hidden.')
    if os.name != 'nt':
        return getpass.getpass(prompt + ': ')
    import msvcrt

    print(prompt + ': ', end='', flush=True)
    characters = []
    while True:
        character = msvcrt.getwch()
        if character in ('\r', '\n'):
            print()
            return ''.join(characters)
        if character == '\x03':
            raise KeyboardInterrupt
        if character in ('\x00', '\xe0'):
            msvcrt.getwch()
            continue
        if character in ('\b', '\x7f'):
            if characters:
                characters.pop()
                print('\b \b', end='', flush=True)
            continue
        if character.isprintable():
            characters.append(character)
            print('*', end='', flush=True)


def choose_chat_model(existing=''):
    default = existing if existing in MODELS else MODELS[0]
    default_number = MODELS.index(default) + 1
    print('Choose the chat model by number:')
    for index, model in enumerate(MODELS, 1):
        marker = ' (default)' if index == default_number else ''
        print(f'  {index}. {model}{marker}')
    while True:
        choice = input(f'Model number [{default_number}]: ').strip()
        if not choice:
            return default
        if choice.isdecimal() and 1 <= int(choice) <= len(MODELS):
            return MODELS[int(choice) - 1]
        print(f'Enter a number from 1 to {len(MODELS)}, or press Enter for the default.')


def https_url(value):
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and bool(parsed.hostname) and not any((parsed.username, parsed.password, parsed.query, parsed.fragment))


def hostname(value):
    return len(value) <= 253 and '.' in value and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in value.split('.'))


def dns_name(value):
    return bool(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,51}[a-z0-9])?', value))


def setup():
    old = read_private('app.json')
    print('Connect to PCAI VPN. In LiteLLM, create your virtual key without selecting a team, or make sure the key allows your chosen model.')
    model = choose_chat_model(old.get('model', MODELS[0]))
    values = {'base_url': VPN, 'api_key': key('LiteLLM virtual key', old.get('api_key', '')), 'model': model, 'auth_mode': 'local'}
    save_private(PRIVATE / 'app.json', values)
    print('SETUP COMPLETE. Your key is saved privately on this computer. Next, run Run App.cmd.')


def configure():
    values = read_private('values.json') or json.loads((ROOT / 'deploy/chart/values.yaml').read_text())
    old = read_private('deployment.json')
    release = ask('Release name', old.get('release', 'pcai-app'), dns_name)
    namespace = ask('PCAI project namespace', old.get('namespace', 'project-genai-platform'), dns_name)
    context = ask('kubectl context name supplied by IT', old.get('context', ''))
    repository = ask('Full image repository, without tag (registry/team/app)', values['image']['repository'], lambda value: bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:-]*/[A-Za-z0-9_./-]+', value)) and '@' not in value)
    tag = ask('Image tag', values['image']['tag'], lambda value: bool(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', value)))
    endpoint = ask('App hostname supplied by IT', values['ezua']['virtualService']['endpoint'], hostname)
    issuer = ask('Keycloak realm issuer URL (https://.../realms/...)', values['auth']['issuerURL'], https_url).rstrip('/')
    client = ask('Keycloak client ID supplied by IT', values['auth']['clientID'])
    group = ask('Allowed Keycloak group claim (for example /pcai-workshop)', (values['auth']['allowedGroups'] or [''])[0])
    mode = ask('Routing mode: istio or ingress', values['routing']['mode'], lambda value: value in ('istio', 'ingress'))
    values['routing']['mode'] = mode
    if mode == 'istio':
        values['ezua']['virtualService']['istioGateway'] = ask('PCAI Istio gateway', values['ezua']['virtualService']['istioGateway'])
        values['networkPolicy']['gatewayNamespace'] = ask('Gateway namespace', 'istio-system', dns_name)
    else:
        values['ingress']['className'] = ask('Ingress class', values['ingress']['className'] or 'nginx')
        values['ingress']['tlsSecretName'] = ask('Existing TLS Secret', values['ingress']['tlsSecretName'], dns_name)
        values['networkPolicy']['gatewayNamespace'] = ask('Ingress controller namespace', 'ingress-nginx', dns_name)
    pull_secret = input('Existing image-pull Secret name (Enter for none): ').strip()
    values['imagePullSecrets'] = [{'name': pull_secret}] if pull_secret else []
    values['image'].update(repository=repository, tag=tag)
    values['ezua']['virtualService']['endpoint'] = endpoint
    values['auth'].update(issuerURL=issuer, clientID=client, allowedGroups=[group], existingSecret=release + '-oidc')
    values['litellm']['existingSecret'] = release + '-litellm'
    values['litellm']['baseURL'] = ask('Cluster LiteLLM base URL', values['litellm']['baseURL'] or INTERNAL, lambda value: value == INTERNAL or https_url(value))
    values['litellm']['model'] = ask('Deployment model', values['litellm']['model'], lambda value: value in MODELS)
    saved = read_private('secrets.json')
    local_key = read_private('app.json').get('api_key', '')
    saved['api-key'] = key('Deployment LiteLLM key', saved.get('api-key', local_key))
    saved['client-secret'] = key('Keycloak client secret', saved.get('client-secret', ''))
    saved.setdefault('cookie-secret', base64.b64encode(secrets.token_bytes(32)).decode())
    save_private(PRIVATE / 'values.json', values)
    save_private(PRIVATE / 'deployment.json', {'release': release, 'namespace': namespace, 'context': context})
    save_private(PRIVATE / 'secrets.json', saved)
    print('CONFIGURATION SAVED. Callback URL: https://' + endpoint + '/oauth2/callback')
    print('IT must register this exact callback and the audience/groups mappers in Keycloak.')


def deployment():
    values, target = read_private('values.json'), read_private('deployment.json')
    if not values or not target:
        raise ValueError('Run Configure PCAI.cmd first.')
    return values, target


def executable(name):
    value = shutil.which(name)
    if not value:
        raise ValueError(f'Install {name} or ask IT to run this deployment step.')
    return value


def run(command, **kwargs):
    return subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def render():
    _, target = deployment()
    private_directory()
    with (PRIVATE / 'rendered.yaml').open('w', encoding='utf-8') as output:
        run([executable('helm'), 'template', target['release'], str(ROOT / 'deploy/chart'), '--namespace', target['namespace'], '-f', str(PRIVATE / 'values.json')], stdout=output)
    print('Rendered .local/rendered.yaml. It contains Secret references, never credential values.')


def prepare_import():
    values, _ = deployment()
    render()
    archive = PRIVATE / 'pcai-app-0.1.0.tgz'
    with tempfile.TemporaryDirectory(dir=PRIVATE) as directory:
        chart = Path(directory) / 'pcai-app'
        shutil.copytree(ROOT / 'deploy/chart', chart)
        (chart / 'values.yaml').write_text(json.dumps(values, indent=2), encoding='utf-8')
        with tarfile.open(archive, 'w:gz') as package:
            package.add(chart, arcname='pcai-app')
    print('IMPORT CHART READY: ' + str(archive))
    print('Run Prepare PCAI Secrets.cmd before importing. Select assets/app-icon.png in the PCAI wizard.')


def kube(target):
    return [executable('kubectl'), '--context', target['context'], '--namespace', target['namespace']]


def prepare_secrets():
    values, target = deployment()
    saved = read_private('secrets.json')
    if not saved:
        raise ValueError('Run Configure PCAI.cmd first.')
    print(f"Target: {target['context']} / {target['namespace']}. This updates the app's two Secrets.")
    if input('Type the namespace to apply: ').strip() != target['namespace']:
        raise ValueError('Secret update cancelled.')
    for name, data in [(values['litellm']['existingSecret'], {'api-key': saved['api-key']}), (values['auth']['existingSecret'], {k: saved[k] for k in ('client-secret', 'cookie-secret')})]:
        resource = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': target['namespace']}, 'type': 'Opaque', 'data': {field: base64.b64encode(value.encode()).decode() for field, value in data.items()}}
        completed = subprocess.run([*kube(target), 'apply', '--server-side', '--field-manager=pcai-app-pack', '-f', '-'], input=json.dumps(resource), text=True, capture_output=True)
        if completed.returncode:
            raise ValueError('Secret update failed. Ask IT to check the context, namespace, ownership and RBAC. No credential output was printed.')
        print(name + ': applied')


def build():
    values, _ = deployment()
    image = values['image']['repository'] + ':' + values['image']['tag']
    run([executable('docker'), 'build', '--platform', 'linux/amd64', '-t', image, '.'])
    print('Image built: ' + image)
    if input('Push this image to the registry? [y/N]: ').strip().lower() == 'y':
        run([executable('docker'), 'push', image])


def deploy():
    _, target = deployment()
    render()
    print(f"Target: {target['context']} / {target['namespace']} / {target['release']}")
    if input('Type the release name to install or upgrade: ').strip() != target['release']:
        raise ValueError('Deployment cancelled.')
    run([executable('helm'), 'upgrade', '--install', target['release'], str(ROOT / 'deploy/chart'), '--kube-context', target['context'], '--namespace', target['namespace'], '-f', str(PRIVATE / 'values.json'), '--atomic', '--wait', '--timeout', '5m'])
    print('Rollout complete. Check browser login and a real model answer before accepting deployment.')


def doctor():
    print('Python:', sys.version.split()[0])
    for name in ('git', 'node', 'docker', 'helm', 'kubectl'):
        print(name + ':', shutil.which(name) or 'not installed (deployment tools are needed only for platform operators)')
    print('Public CA SHA256:', hashlib.sha256((ROOT / 'certs/pcai-ca.crt').read_bytes()).hexdigest())
    print('App key:', 'saved' if read_private('app.json').get('api_key') else 'not configured')


def tools():
    config_path = ROOT / 'opencode.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    servers = config['mcp']['servers']
    if ask('Enable Playwright browser MCP? y/n', 'y', lambda value: value in ('y', 'n')) == 'y':
        if not shutil.which('node') or not shutil.which('npx'):
            raise ValueError('Install an approved Node.js LTS release, close this console and rerun Enable Workshop Tools.cmd.')
        servers['playwright']['command'] = (['cmd.exe', '/d', '/c'] if os.name == 'nt' else []) + ['npx', '-y', '@playwright/mcp@0.0.86', '--isolated']
        servers['playwright']['disabled'] = False
    else:
        servers['playwright']['disabled'] = True
    servers['context7']['disabled'] = ask('Enable external Context7 documentation MCP? y/n', 'n', lambda value: value in ('y', 'n')) == 'n'
    fd, temporary = tempfile.mkstemp(prefix='opencode-', suffix='.json', dir=ROOT)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(config, output, indent=2)
            output.write('\n')
        Path(temporary).replace(config_path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print('MCP settings saved. Reopen this project in OpenCode and check /mcps. Complete any service login there.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'run', 'configure', 'render', 'prepare-import', 'secrets', 'build', 'deploy', 'doctor', 'tools'])
    args = parser.parse_args()
    if args.command == 'run':
        if not read_private('app.json').get('api_key'):
            setup()
        print('Open http://127.0.0.1:8000 . Press Ctrl+C to stop.')
        import uvicorn
        uvicorn.run('app.main:app', host='127.0.0.1', port=8000, proxy_headers=False)
    else:
        {'setup': setup, 'configure': configure, 'render': render, 'prepare-import': prepare_import, 'secrets': prepare_secrets, 'build': build, 'deploy': deploy, 'doctor': doctor, 'tools': tools}[args.command]()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
        print(str(exc) if isinstance(exc, ValueError) else 'The command stopped. Check prerequisites and the preceding output.', file=sys.stderr)
        sys.exit(1)
