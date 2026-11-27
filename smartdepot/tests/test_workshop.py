import json
from pathlib import Path
import zipfile
from types import SimpleNamespace

import pytest

from scripts import package, workshop
from scripts import install_plugin


def test_configuration_wizard_keeps_secrets_out_of_values_and_preserves_cookie(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, 'PRIVATE', tmp_path / '.local')
    supplied = {'Full image repository': 'registry.example.invalid/team/app', 'App hostname': 'app.pcai.example.invalid', 'Keycloak realm issuer': 'https://keycloak.example.invalid/realms/test', 'Keycloak client ID': 'workshop-client', 'Allowed Keycloak group': '/workshop', 'kubectl context': 'workshop-context'}

    def ask(label, default='', validator=None):
        value = next((value for key, value in supplied.items() if label.startswith(key)), default)
        assert value and (validator is None or validator(value))
        return value

    monkeypatch.setattr(workshop, 'ask', ask)
    monkeypatch.setattr('builtins.input', lambda _: '')
    monkeypatch.setattr(workshop.getpass, 'getpass', lambda _: 'dummy-test-credential')
    workshop.configure()
    before = workshop.read_private('secrets.json')
    workshop.configure()
    after = workshop.read_private('secrets.json')
    assert before['cookie-secret'] == after['cookie-secret']
    values = workshop.read_private('values.json')
    assert values['auth']['allowedGroups'] == ['/workshop']
    assert 'dummy-test-credential' not in json.dumps(values)
    assert values['auth']['existingSecret'] == 'pcai-app-oidc'


def test_packaging_excludes_working_credentials_and_verifies_manifest(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'README.md').write_text('share this source')
    (source / '.local').mkdir()
    (source / '.local' / 'app.json').write_text(json.dumps({'api_key': 'sk-' + 'A' * 24}))
    (source / '.venv').mkdir()
    (source / '.venv' / 'binary').write_bytes(b'not source')
    monkeypatch.setattr(package, 'ROOT', source)
    archive = package.build(tmp_path / 'sharing.zip')
    with zipfile.ZipFile(archive) as sharing:
        assert set(sharing.namelist()) == {'HPE-PCAI/README.md', 'HPE-PCAI/bundle-manifest.json', 'HPE-PCAI/MANIFEST.sha256.json'}
        manifest = json.loads(sharing.read('HPE-PCAI/MANIFEST.sha256.json'))
        assert 'README.md' in manifest


def test_packaging_rejects_a_key_accidentally_added_to_source(tmp_path, monkeypatch):
    (tmp_path / 'README.md').write_text('mistake: ' + 'sk-' + 'B' * 24)
    monkeypatch.setattr(package, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='Potential credential'):
        package.build(tmp_path / 'dist' / 'sharing.zip')


def test_secret_apply_uses_stdin_data_and_never_credential_arguments(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(workshop, 'PRIVATE', tmp_path / '.local')
    values = json.loads((workshop.ROOT / 'deploy/values.validation.json').read_text())
    workshop.save_private(workshop.PRIVATE / 'values.json', values)
    workshop.save_private(workshop.PRIVATE / 'deployment.json', {'release': 'test-app', 'namespace': 'project-workshop', 'context': 'test-only'})
    workshop.save_private(workshop.PRIVATE / 'secrets.json', {'api-key': 'private-dummy-value', 'client-secret': 'oidc-dummy-value', 'cookie-secret': 'cookie-dummy-value'})
    monkeypatch.setattr(workshop, 'executable', lambda _: 'kubectl-test-only')
    monkeypatch.setattr('builtins.input', lambda _: 'project-workshop')
    applied = []

    def apply(args, **kwargs):
        assert 'private-dummy-value' not in str(args)
        assert '--server-side' in args and args[-1] == '-'
        resource = json.loads(kwargs['input'])
        assert resource['kind'] == 'Secret' and 'data' in resource and 'stringData' not in resource
        applied.append(resource)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(workshop.subprocess, 'run', apply)
    workshop.prepare_secrets()
    assert len(applied) == 2
    assert 'private-dummy-value' not in capsys.readouterr().out


def test_plugin_installer_repeats_safely_and_preserves_unmanaged_folders(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'README.md').write_text('plugin source')
    (source / '.local').mkdir()
    (source / '.local/app.json').write_text('private working state')
    monkeypatch.setattr(package, 'ROOT', source)
    destination = tmp_path / 'config/plugins/pcai'
    install_plugin.install(destination)
    install_plugin.install(destination)
    assert (destination / 'README.md').read_text() == 'plugin source'
    assert not (destination / '.local').exists()
    unmanaged = tmp_path / 'config/plugins/unmanaged'
    unmanaged.mkdir()
    (unmanaged / 'keep.txt').write_text('existing work')
    with pytest.raises(ValueError, match='preserved'):
        install_plugin.install(unmanaged)
    assert (unmanaged / 'keep.txt').read_text() == 'existing work'
