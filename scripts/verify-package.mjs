import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';

const exec = promisify(execFile);
const root = resolve(import.meta.dirname, '..');
const artifacts = resolve(root, 'artifacts');
await mkdir(artifacts, { recursive: true });
const packedResult = JSON.parse((await exec('npm', ['pack', '--json', '--pack-destination', artifacts], { cwd: root })).stdout);
const packed = Array.isArray(packedResult) ? packedResult[0] :
  packedResult.files ? packedResult : Object.values(packedResult).find((item) => item?.files);
assert(packed?.files, `Unexpected npm pack metadata: ${JSON.stringify(packedResult)}`);
const names = packed.files.map((f) => f.path);
for (const required of ['dist/index.js', 'openclaw.plugin.json', 'server/server.py', 'server/task_optimizer.py', 'server/memory_store.py', 'server/.env.template', 'dist/control-ui/index.js', 'dist/control-ui/index.css']) assert(names.includes(required), `${required} missing`);
assert(!names.some((p) => /(^|\/)\.env$|(^|\/)(venv|\.venv|scope_data|__pycache__)\//.test(p)), 'private/runtime files packed');

const isolated = await mkdtemp(resolve(tmpdir(), 'evolveclaw-package-'));
const configPath = resolve(isolated, 'openclaw.json');
const stateDir = resolve(isolated, 'state');
// Port 1 cannot point at the user's normal Gateway. This config contains no real credentials.
const config = { gateway: { mode: 'local', port: 1, auth: { mode: 'token', token: 'package-smoke-only' } }, plugins: { allow: [] } };
await writeFile(configPath, JSON.stringify(config));
const env = { ...process.env, OPENCLAW_STATE_DIR: stateDir, OPENCLAW_CONFIG_PATH: configPath, OPENCLAW_GATEWAY_PORT: '1' };
const cli = resolve(root, 'node_modules/openclaw/openclaw.mjs');
const run = async (...args) => exec(process.execPath, [cli, ...args], { cwd: root, env, timeout: 120_000, maxBuffer: 4_000_000 });
const parse = (output) => JSON.parse(output.slice(output.search(/^\{/m)));
try {
  await run('plugins', 'install', `npm-pack:${resolve(artifacts, packed.filename)}`, '--force', '--accept-capabilities');
  const installed = JSON.parse(await readFile(configPath, 'utf8'));
  installed.plugins.entries.evolveclaw = {
    ...installed.plugins.entries.evolveclaw,
    enabled: true, hooks: { allowConversationAccess: true, allowPromptInjection: true },
    config: { autoStartServer: false, serverUrl: 'http://127.0.0.1:1' },
  };
  await writeFile(configPath, JSON.stringify(installed));
  const granted = parse((await run('plugins', 'inspect', 'evolveclaw', '--runtime', '--json')).stdout);
  const entry = granted.plugin ?? granted;
  assert.equal(entry.status, 'loaded');
  assert.equal(entry.hookCount, 7);
  assert(entry.services.includes('evolveclaw-sidecar'));
  assert(entry.commands.includes('evolveclaw') && entry.commands.includes('evolveclaw-change'));
  assert.equal(entry.controlUi.entry, 'dist/control-ui/index.js');
  assert(entry.uiCapabilities.includes('page') && entry.uiCapabilities.includes('panel'));
  installed.plugins.entries.evolveclaw.hooks.allowConversationAccess = false;
  await writeFile(configPath, JSON.stringify(installed));
  const denied = parse((await run('plugins', 'inspect', 'evolveclaw', '--runtime', '--json')).stdout);
  const deniedEntry = denied.plugin ?? denied;
  assert.equal(deniedEntry.hookCount, 3);
  const report = { hostVersion: '2026.10.2', package: packed.filename, packageIntegrity: packed.integrity,
    packagedFiles: names, granted, denied, liveConfigurationChanged: false, paidModelCalls: 0 };
  await writeFile(resolve(artifacts, 'package-verification.json'), JSON.stringify(report, null, 2));
  console.log('Packed plugin installed and registered in isolated OpenClaw: 7 hooks + sidecar service; permission denial leaves 3 hooks.');
} finally {
  await rm(isolated, { recursive: true, force: true });
}
