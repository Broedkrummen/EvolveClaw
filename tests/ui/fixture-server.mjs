import http from 'node:http';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, readFile, writeFile, mkdir, copyFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { register } from '../../dist/index.js';
const exec = promisify(execFile), root = resolve(import.meta.dirname, '../..');
const directory = await mkdtemp(resolve(tmpdir(), 'evolveclaw-ui-'));
const python = process.env.EVOLVECLAW_TEST_PYTHON || 'python3';
const source = resolve(directory, 'server'), data = resolve(directory, 'memory');
await mkdir(source); await mkdir(data);
for (const name of ['server.py', 'config.py', 'task_optimizer.py', 'prompts.py', 'memory_store.py']) await copyFile(resolve(root, 'server', name), resolve(source, name));
const env = { ...process.env, EVOLVECLAW_SCOPE_DATA: data, PYTHONPATH: source };
for (const key of ['EVOLVECLAW_SCOPE_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'EVOLVECLAW_TOKEN', 'EVOLVECLAW_SIDECAR_TOKEN']) delete env[key];
const seed = `
import json,sys
from memory_store import MemoryStore
s=MemoryStore(sys.argv[1])
scope={'audience_key':json.dumps(['owner-private','main'],separators=(',',':')),'project_key':json.dumps(['project-test'],separators=(',',':'))}
e=s.record_evidence('openclaw-agent',scope,'fixture',{'task':'Create an appointment','error':'Calendar rejected the request'})
r=s.add_rule('openclaw-agent',scope,'Verify calendar confirmation before reporting an appointment as created',evidence_id=e['id'],expected_revision=0)
print(json.dumps({'scope':scope,'rule_id':r['id']}))
`;
const seeded = JSON.parse((await exec(python, ['-c', seed, data], { cwd: source, env })).stdout);
const portSocket = http.createServer(); await new Promise(r => portSocket.listen(0, '127.0.0.1', r));
const port = portSocket.address().port; await new Promise(r => portSocket.close(r));
const sidecar = spawn(python, ['-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', String(port)], { cwd: source, env, stdio: 'ignore' });
let alive = false;
for (let i = 0; i < 100; i++) { try { alive = (await fetch(`http://127.0.0.1:${port}/health`)).ok; } catch {} if (alive) break; await new Promise(r => setTimeout(r, 100)); }
if (!alive) { sidecar.kill(); throw new Error('Isolated UI sidecar failed to start'); }
const actions = new Map(), hooks = new Map(), services = [];
register({ id: 'evolveclaw', rootDir: root, config: {}, pluginConfig: { autoStartServer: false, serverUrl: `http://127.0.0.1:${port}` },
  runtime: {}, logger: { info() {}, warn() {}, error() {}, debug() {} },
  on(name, fn) { hooks.set(name, fn); }, registerService(service) { services.push(service); },
  registerSessionAction(action) { actions.set(action.id, action); }, registerCommand() {} });
await services[0].start({ stateDir: directory });
hooks.get('before_prompt_build')({ prompt: 'Fixture task', currentUserMessage: 'Fixture task', messages: [] }, {
  agentId: 'main', sessionId: 'ui-fixture', sessionKey: 'agent:main:ui-fixture', runId: 'ui-run', trigger: 'user',
  memoryAudience: { kind: 'owner-private', agentId: 'main' }, activeProjectKeys: ['project-test'], assertMemoryAudienceCurrent() {},
});
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EvolveClaw isolated UI fixture</title><link rel="stylesheet" href="/dist/control-ui/index.css"></head><body><main id="app"></main><script type="module">
import plugin from '/dist/control-ui/index.js';
const flags=new URLSearchParams(location.search); const controller=new AbortController();
const host={apiVersion:1,pluginId:'evolveclaw',signal:controller.signal,basePath:'/',locale:'en-GB',redact:t=>t,
connection:{connected:true,canRead:true,canWrite:!flags.has('readonly'),canAdmin:!flags.has('readonly')},
agents:{selectedId:'main',defaultId:'main'}, subscribe:()=>()=>{}, onEvent:()=>()=>{},
request:async(method,params)=>{ const res=await fetch('/rpc',{method:'POST',headers:{'Content-Type':'application/json','X-Test-Access':flags.has('readonly')?'read':'admin','X-Test-Empty':flags.has('empty')?'yes':'no','X-Test-Offline':flags.has('offline')?'yes':'no'},body:JSON.stringify({method,params})});return await res.json(); },
components:{mountSelectPicker:(container,props)=>{const select=document.createElement('select');container.append(select);let current;const update=p=>{current=p;select.replaceChildren(...p.options.map(o=>{const el=document.createElement('option');el.value=o.value;el.textContent=o.label;return el;}));select.value=p.value;select.disabled=p.disabled;select.setAttribute('aria-label',p.accessibleLabel);};select.onchange=()=>current.onSelect(select.value);update(props);return{update,dispose:()=>select.remove()};}},
ui:{registerPage:p=>{p.mount(document.getElementById('app'),{host,signal:controller.signal,props:{},presented:true,mountDefault:()=>()=>{}});return()=>{};},registerNavigation:()=>()=>{},registerPanel:()=>()=>{}}};plugin.activate(host);window.fixtureHost=host;
</script></body></html>`;
const server = http.createServer(async (req, res) => {
  try {
    if (req.url === '/rpc') {
      let raw = ''; for await (const c of req) raw += c;
      const { method, params } = JSON.parse(raw);
      if (method !== 'plugins.sessionAction' || params.pluginId !== 'evolveclaw') throw new Error('Unknown fixture operation');
      if (req.headers['x-test-offline'] === 'yes') return json(res, { ok: false, error: 'Memory service is unavailable. Try refreshing.' });
      const action = actions.get(params.actionId);
      const scopes = req.headers['x-test-access'] === 'read' ? ['operator.read'] : ['operator.read', 'operator.write', 'operator.admin'];
      if (!action || action.requiredScopes.some(s => !scopes.includes(s))) return json(res, { ok: false, error: 'Memory permission is unavailable.' });
      if (params.payload.operation === 'scopes' && req.headers['x-test-empty'] === 'yes') return json(res, { ok: true, result: { data: JSON.stringify({ scopes: [] }) } });
      return json(res, await action.handler({ pluginId: 'evolveclaw', actionId: params.actionId, agentId: 'main', sessionKey: 'agent:main:ui-fixture', payload: params.payload, client: { scopes } }));
    }
    if (req.url === '/external-change') {
      const snap = await (await fetch(`http://127.0.0.1:${port}/memory/query`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ agent_name: 'openclaw-agent', scope: seeded.scope, operation: 'status' }) })).json();
      await fetch(`http://127.0.0.1:${port}/memory/mutate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ agent_name: 'openclaw-agent', scope: seeded.scope, operation: snap.paused ? 'resume' : 'pause', expected_revision: snap.revision }) });
      return json(res, { ok: true });
    }
    if (req.url?.startsWith('/dist/control-ui/')) {
      const path = new URL(req.url, 'http://fixture').pathname;
      if (!['/dist/control-ui/index.js', '/dist/control-ui/index.css'].includes(path)) throw new Error('Unknown fixture asset');
      res.setHeader('Content-Type', path.endsWith('.css') ? 'text/css' : 'text/javascript'); return res.end(await readFile(resolve(root, path.slice(1))));
    }
    res.setHeader('Content-Type', 'text/html'); res.end(html);
  } catch (error) { json(res, { ok: false, error: error.message }); }
});
function json(res, value) { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(value)); }
server.listen(18791, '127.0.0.1');
let closing = false;
async function close() { if (closing) return; closing = true; server.close(); await services[0].stop(); sidecar.kill('SIGTERM'); await new Promise(r => sidecar.exitCode !== null ? r() : sidecar.once('exit', r)); await rm(directory, { recursive: true, force: true }); process.exit(0); }
process.on('SIGTERM', close); process.on('SIGINT', close);
