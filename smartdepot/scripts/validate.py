"""Validate app behavior, skill discovery and deployment invariants without cluster access."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent


def command(args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def chart(helm):
    path = ROOT / 'deploy/chart'
    example = json.loads((ROOT / 'deploy/values.validation.json').read_text())
    command([helm, 'lint', str(path), '--strict', '-f', str(ROOT / 'deploy/values.validation.json')])
    for mode in ('istio', 'ingress'):
        values = copy.deepcopy(example)
        values['routing']['mode'] = mode
        if mode == 'ingress':
            values['ingress']['tlsSecretName'] = 'workshop-tls'
            values['networkPolicy']['gatewayNamespace'] = 'ingress-nginx'
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'values.json'
            file.write_text(json.dumps(values))
            output = command([helm, 'template', 'test-app', str(path), '--namespace', 'project-workshop', '-f', str(file)])
            resources = [item for item in yaml.safe_load_all(output) if item]
            assert not any(item['kind'] in ('Secret', 'ClusterRole', 'ClusterRoleBinding', 'ClusterPolicy') for item in resources)
            deployments = [item for item in resources if item['kind'] == 'Deployment']
            assert len(deployments) == 2
            for item in deployments:
                spec = item['spec']['template']['spec']
                assert spec['automountServiceAccountToken'] is False
                assert item['spec']['template']['metadata']['labels']['hpe-ezua/type'] == 'vendor-service'
                container = spec['containers'][0]
                assert container['securityContext']['readOnlyRootFilesystem'] is True
                assert container['securityContext']['allowPrivilegeEscalation'] is False
            proxy = next(item for item in deployments if item['metadata']['name'].endswith('-auth'))
            args = proxy['spec']['template']['spec']['containers'][0]['args']
            assert '--provider=keycloak-oidc' in args
            assert '--cookie-secure=true' in args
            assert '--code-challenge-method=S256' in args
            assert '--allowed-group=/pcai-workshop' in args
            assert '--use-system-trust-store=true' in args
            assert not any('insecure' in arg or 'skip-jwt' in arg for arg in args)
            if mode == 'istio':
                route = next(item for item in resources if item['kind'] == 'VirtualService')
                assert route['spec']['http'][0]['route'][0]['destination']['host'] == 'test-app-auth.project-workshop.svc.cluster.local'
                assert not any(item['kind'] == 'Ingress' for item in resources)
            else:
                route = next(item for item in resources if item['kind'] == 'Ingress')
                assert route['spec']['rules'][0]['http']['paths'][0]['backend']['service']['name'] == 'test-app-auth'
                assert route['spec']['tls'][0]['secretName'] == 'workshop-tls'
                assert not any(item['kind'] == 'VirtualService' for item in resources)
            policies = [item for item in resources if item['kind'] == 'NetworkPolicy']
            app_policy = next(item for item in policies if item['metadata']['name'].endswith('-app'))
            sources = app_policy['spec']['ingress'][0]['from']
            assert len(sources) == 1 and sources[0]['podSelector']['matchLabels']['app.kubernetes.io/component'] == 'auth'
            assert sources[0]['podSelector']['matchLabels']['app.kubernetes.io/instance'] == 'test-app'
            print('Rendered ' + mode + ' route, auth and network invariants: PASS')
    schema = json.loads((path / 'values.schema.json').read_text())
    forbidden = copy.deepcopy(example)
    forbidden['litellm']['apiKey'] = 'not-a-real-credential'
    try:
        jsonschema.validate(forbidden, schema)
    except jsonschema.ValidationError:
        print('Chart values reject inline API-key fields: PASS')
    else:
        raise AssertionError('Chart values accepted inline API keys')
    missing_group = copy.deepcopy(example)
    missing_group['auth']['allowedGroups'] = []
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / 'values.json'
        file.write_text(json.dumps(missing_group))
        result = subprocess.run([helm, 'template', 'test-app', str(path), '-f', str(file)], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode != 0 and 'allowedGroups' in result.stderr
    print('Chart refuses empty allowed-group policy: PASS')


def skills():
    for skill in sorted((ROOT / '.opencode/skills').glob('*/SKILL.md')):
        data = skill.read_text()
        frontmatter = yaml.safe_load(data.split('---', 2)[1])
        assert frontmatter['name'] == skill.parent.name and frontmatter['description']
        for target in re.findall(r'\]\(([^)]+)\)', data):
            if not target.startswith('http'):
                assert (skill.parent / target).exists(), target
    print('Seven project skills, frontmatter and local references: PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helm', default=shutil.which('helm'))
    parser.add_argument('--opencode-schema', help='Optional official OpenCode v2 config JSON schema file')
    args = parser.parse_args()
    if not args.helm:
        parser.error('Install Helm 3 or supply --helm PATH. No chart checks were run.')
    result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q'], cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)
    skills()
    ca = (ROOT / 'certs/pcai-ca.crt').read_bytes()
    assert hashlib.sha256(ca).hexdigest() == '431955c40fbb33012ff7fe8babab41ffc60807531b7de68486f2621f62234e5e'
    assert ca == (ROOT / 'deploy/chart/files/pcai-ca.crt').read_bytes()
    config = json.loads((ROOT / 'opencode.json').read_text())
    assert {'playwright', 'context7'}.issubset(config['mcp']['servers'])
    if args.opencode_schema:
        jsonschema.Draft202012Validator(json.loads(Path(args.opencode_schema).read_text())).validate(config)
        print('Official OpenCode v2 config schema: PASS')
    chart(str(Path(args.helm).resolve()) if Path(args.helm).exists() else args.helm)
    print('Validation complete. This did not exercise a real model, browser login, container build or PCAI cluster.')


if __name__ == '__main__':
    main()
