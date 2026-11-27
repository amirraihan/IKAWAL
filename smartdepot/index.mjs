import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { access, copyFile, mkdir, mkdtemp, readFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const version = '0.1.2';
const topics = {develop: 'docs/develop.md', deploy: 'docs/deploy.md', keycloak: 'docs/keycloak.md', litellm: 'docs/litellm.md', acceptance: 'docs/acceptance.md', mcp: 'docs/mcp.md', overview: 'README.md'};
const skillNames = ['agentic-app-dev', 'pcai-deploy', 'pstack-how', 'pstack-architect', 'pstack-blast-radius', 'pstack-debug', 'pstack-prove'];
const workflows = [
  ['pcai-help', 'Explain the PCAI plugin and its available workflows', 'Explain the installed PCAI plugin. Use pcai_status and pcai_guide with overview. Describe the available commands and the first local app exercise.'],
  ['pcai-start', 'Create a reusable PCAI app in a new project folder', 'Use agentic-app-dev. Ask for a short app folder name if it is missing, then use pcai_scaffold to create the starter inside this workspace. Do not overwrite an existing folder. Explain Setup App.cmd and Run App.cmd. The starter calls LiteLLM, includes report tools and can export Markdown.'],
  ['pcai-build', 'Build and verify an app feature', 'Use agentic-app-dev and the affected project source. Implement the requested user flow and verify the actual result. Read project AGENTS.md. Keep model credentials on the backend.'],
  ['pcai-review', 'Review design and effects beyond the current diff', 'Use pstack-blast-radius to review the affected API, UI, model/tool and deployment contracts. Inspect actual source and run the relevant checks.'],
  ['pcai-deploy', 'Prepare an image and Helm chart for PCAI import', 'Use pcai-deploy and pcai_guide with deploy and keycloak. Prepare the image, non-secret chart values and import archive in the selected app project. Check the target namespace, gateway, Keycloak client and allowed group. Stop at prepared artifacts unless the user explicitly requests registry or cluster changes.'],
  ['pcai-check', 'Inspect readiness, LiteLLM access and acceptance evidence', 'Use pstack-prove. Run pcai_status, inspect the selected project without printing or exposing any credential, and use pcai_guide with litellm and acceptance. Check the exact configured model alias and endpoint, explain that the LiteLLM virtual key should be created without selecting a team or explicitly allow this model, then distinguish config inspection from a real chat request. Separate local test evidence, prepared deployment artifacts and real platform acceptance.'],
];

async function exists(file) {
  try { await access(file); return true; } catch { return false; }
}

function safeAsset(relative) {
  if (typeof relative !== 'string' || path.isAbsolute(relative) || relative.split(/[\\/]/).includes('..')) throw new Error('Invalid bundled asset path.');
  const resolved = path.resolve(root, relative);
  if (!resolved.startsWith(root + path.sep)) throw new Error('Asset escaped the plugin folder.');
  return resolved;
}

export async function scaffold(workspace, folder, signal) {
  if (!/^[a-z0-9][a-z0-9-]{0,51}$/.test(folder)) throw new Error('Choose a folder name using lowercase letters, numbers and hyphens.');
  const destination = path.join(workspace, folder);
  if (await exists(destination)) throw new Error('That folder already exists. Choose another name; existing work was preserved.');
  const manifest = JSON.parse(await readFile(path.join(root, 'bundle-manifest.json'), 'utf8'));
  const stage = await mkdtemp(path.join(workspace, '.pcai-new-'));
  let reserved = false;
  try {
    for (const [relative, checksum] of Object.entries(manifest.files)) {
      signal?.throwIfAborted();
      const source = safeAsset(relative);
      const data = await readFile(source);
      if (createHash('sha256').update(data).digest('hex') !== checksum) throw new Error('A bundled source changed. Rebuild the plugin archive before scaffolding.');
      const output = path.join(stage, relative);
      await mkdir(path.dirname(output), {recursive: true});
      await copyFile(source, output);
    }
    await copyFile(path.join(root, 'bundle-manifest.json'), path.join(stage, 'bundle-manifest.json'));
    signal?.throwIfAborted();
    // Exclusive reservation also refuses a destination created concurrently.
    await mkdir(destination);
    reserved = true;
    for (const relative of [...Object.keys(manifest.files), 'bundle-manifest.json']) {
      signal?.throwIfAborted();
      const output = path.join(destination, relative);
      await mkdir(path.dirname(output), {recursive: true});
      await copyFile(path.join(stage, relative), output, constants.COPYFILE_EXCL);
    }
    return destination;
  } catch (error) {
    if (reserved) await rm(destination, {recursive: true, force: true});
    throw error;
  } finally {
    await rm(stage, {recursive: true, force: true});
  }
}

// OpenCode v2's Plugin.define returns this structural definition unchanged.
// Keeping the equivalent JavaScript shape avoids a separate SDK/npm installation.
export default {
  id: 'pcai',
  async setup(ctx) {
    const parsed = /(?:^|\s)v?(\d+)\.(\d+)\.(\d+)/.exec(ctx.app.version);
    if (!parsed || Number(parsed[1]) !== 2 || (Number(parsed[2]) < 3) || (Number(parsed[2]) === 3 && Number(parsed[3]) < 2)) throw new Error('PCAI plugin requires OpenCode v2.3.2 or newer in the v2 series.');
    const skills = await Promise.all(skillNames.map(async id => {
      const file = path.join(root, '.opencode', 'skills', id, 'SKILL.md');
      const text = await readFile(file, 'utf8');
      const description = JSON.parse(/^description: (.+)$/m.exec(text)[1]);
      return {id, name: id, description, path: file, content: text.split('---').slice(2).join('---').trim()};
    }));
    await ctx.skill.transform(editor => {
      for (const skill of skills) if (!editor.get(skill.id)) editor.add(skill);
    });
    await ctx.command.transform(editor => {
      for (const [name, description, instructions] of workflows) {
        editor.add({name, description, execute: async ({sessionID, prompt, delivery}) => {
          await ctx.session.prompt({...prompt, sessionID, text: instructions + '\n\nUser request:\n' + (prompt.text || ''), delivery});
        }});
      }
    });
    await ctx.tool.transform(editor => {
      editor.add({name: 'pcai_status', description: 'Inspect this workspace and the PCAI plugin without reading credential values or contacting a cluster.', input: {type: 'object', properties: {}, additionalProperties: false}, execute: async () => ({content: JSON.stringify({plugin: 'pcai', version, workspace: ctx.location.directory, starterPresent: await exists(path.join(ctx.location.directory, 'app/main.py')), setupFilePresent: await exists(path.join(ctx.location.directory, '.local/app.json')), deploymentFilePresent: await exists(path.join(ctx.location.directory, '.local/values.json')), commands: workflows.map(item => '/' + item[0]), note: 'File presence is not a live model or platform check.'}, null, 2)})});
      editor.add({name: 'pcai_guide', description: 'Read a bundled PCAI development, deployment, Keycloak, LiteLLM, MCP or acceptance guide.', input: {type: 'object', properties: {topic: {type: 'string', enum: Object.keys(topics)}}, required: ['topic'], additionalProperties: false}, execute: async input => {
        if (!Object.hasOwn(topics, input.topic)) throw new Error('Unknown PCAI guide topic.');
        return {content: await readFile(safeAsset(topics[input.topic]), 'utf8')};
      }});
      editor.add({name: 'pcai_scaffold', description: 'Create a reusable PCAI app in a new child folder of this workspace. Existing folders are never overwritten.', input: {type: 'object', properties: {folder: {type: 'string', pattern: '^[a-z0-9][a-z0-9-]{0,51}$'}}, required: ['folder'], additionalProperties: false}, execute: async (input, context) => {
        if (!/^[a-z0-9][a-z0-9-]{0,51}$/.test(input.folder)) throw new Error('Invalid app folder name.');
        const destination = path.join(ctx.location.directory, input.folder);
        await ctx.permission.assert({sessionID: context.sessionID, agent: context.agent, source: {type: 'tool', messageID: context.messageID, id: context.id}, action: 'edit', resources: [destination], save: [destination]});
        const created = await scaffold(ctx.location.directory, input.folder, context.signal);
        return {content: 'Created ' + created + '. Open it as your project. Run Setup App.cmd, enter your own LiteLLM key, then run Run App.cmd. Deployment artifacts are included; nothing was pushed or deployed.'};
      }});
    });
    await ctx.storage.set('version', version);
  },
};
