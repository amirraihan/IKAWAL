import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import plugin, { scaffold } from '../index.mjs';

function host(workspace, version = '2.3.2') {
  const skills = new Map(), commands = new Map(), tools = new Map(), storage = new Map(), prompts = [];
  const context = {app: {version}, location: {directory: workspace}, storage: {set: async (key, value) => storage.set(key, value)}, skill: {transform: async fn => fn({get: id => skills.get(id), add: item => skills.set(item.id, item)})}, command: {transform: async fn => fn({add: item => commands.set(item.name, item)})}, tool: {transform: async fn => fn({add: item => tools.set(item.name, item)})}, session: {prompt: async input => prompts.push(input)}, permission: {assert: async () => {}}};
  return {context, skills, commands, tools, storage, prompts};
}

test('native v2 definition registers seven skills, six commands and three tools', async () => {
  const state = host(os.tmpdir());
  await plugin.setup(state.context);
  assert.equal(state.skills.size, 7);
  assert.equal(state.commands.size, 6);
  assert.equal(state.tools.size, 3);
  assert.equal(state.storage.get('version'), '0.1.0');
  const guide = await state.tools.get('pcai_guide').execute({topic: 'keycloak'});
  assert.match(guide.content, /Audience/);
  await assert.rejects(() => state.tools.get('pcai_guide').execute({topic: '../../.local/app.json'}));
});

test('commands preserve prompt attachments and queue delivery', async () => {
  const state = host(os.tmpdir());
  await plugin.setup(state.context);
  await state.commands.get('pcai-build').execute({sessionID: 'test-session', delivery: 'queue', prompt: {text: 'Add a filter', files: [{path: 'feature.md'}]}});
  assert.equal(state.prompts[0].delivery, 'queue');
  assert.deepEqual(state.prompts[0].files, [{path: 'feature.md'}]);
  assert.match(state.prompts[0].text, /Add a filter/);
});

test('status reports presence without exposing saved credentials', async () => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'pcai-status-'));
  try {
    await mkdir(path.join(workspace, '.local'));
    await writeFile(path.join(workspace, '.local/app.json'), '{"api_key":"do-not-return-this-value"}');
    const state = host(workspace);
    await plugin.setup(state.context);
    const result = await state.tools.get('pcai_status').execute({});
    assert.equal(JSON.parse(result.content).setupFilePresent, true);
    assert.doesNotMatch(result.content, /do-not-return-this-value/);
  } finally { await rm(workspace, {recursive: true, force: true}); }
});

test('scaffold copies working assets and refuses an existing or escaped destination', async () => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'pcai-scaffold-'));
  try {
    const destination = await scaffold(workspace, 'team-app');
    assert.match(await readFile(path.join(destination, 'app/main.py'), 'utf8'), /create_app/);
    assert.match(await readFile(path.join(destination, 'deploy/chart/Chart.yaml'), 'utf8'), /pcai-app/);
    assert.ok(!(await readdir(destination)).includes('.local'));
    await writeFile(path.join(destination, 'keep.txt'), 'my work');
    await assert.rejects(() => scaffold(workspace, 'team-app'), /already exists/);
    assert.equal(await readFile(path.join(destination, 'keep.txt'), 'utf8'), 'my work');
    await assert.rejects(() => scaffold(workspace, '../escape'));
  } finally { await rm(workspace, {recursive: true, force: true}); }
});

test('denied permission never creates an app folder', async () => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'pcai-denied-'));
  try {
    const state = host(workspace);
    state.context.permission.assert = async () => { throw new Error('Denied'); };
    await plugin.setup(state.context);
    await assert.rejects(() => state.tools.get('pcai_scaffold').execute({folder: 'blocked'}, {sessionID: 'test', agent: 'test', messageID: 'test', id: 'test', signal: new AbortController().signal}), /Denied/);
    assert.deepEqual(await readdir(workspace), []);
  } finally { await rm(workspace, {recursive: true, force: true}); }
});

test('unsupported OpenCode versions fail before registration', async () => {
  await assert.rejects(() => plugin.setup(host(os.tmpdir(), '1.19.6').context), /v2.3.2/);
  await assert.rejects(() => plugin.setup(host(os.tmpdir(), '2.2.7').context), /v2.3.2/);
});
