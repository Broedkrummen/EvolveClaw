import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import plugin, { register, capGuidelines } from '../dist/index.js';

const context = (sessionId = 'A', runId = `run-${sessionId}`) => ({ agentId: 'main', sessionId, sessionKey: `agent:main:${sessionId}`, runId, trigger: 'user' });
const endEvent = (text = 'answer') => ({ success: true, messages: [{ role: 'user', content: 'request' }, { role: 'assistant', content: text }] });

async function harness(t, config = {}, options = {}) {
  const calls = [];
  const rules = new Map();
  const hooks = new Map();
  const services = [];
  const log = [];
  let configured = options.configured ?? true;
  const server = http.createServer(async (req, res) => {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const body = raw ? JSON.parse(raw) : undefined;
    calls.push({ path: req.url, body });
    if (options.respond) {
      const override = await options.respond(req.url, body);
      if (override !== undefined) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(override)); return; }
    }
    let output;
    if (req.url === '/health') output = { status: 'ok', version: 'test', configured, protocol_version: 2 };
    else if (req.url === '/configure') { configured = true; output = { status: 'ok' }; }
    else if (req.url.startsWith('/rules/')) {
      const guidelines = rules.get(decodeURIComponent(req.url.slice(7))) ?? [];
      output = { rules: guidelines.join('\n'), guidelines, rule_count: guidelines.length, configured };
    } else if (req.url === '/step') output = { guideline: `temporary ${body.task_id}`, guideline_type: 'tactical', skipped: false };
    else output = { status: 'ok' };
    res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(output));
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  t.after(() => { server.closeAllConnections(); return new Promise((r) => server.close(r)); });
  const api = {
    rootDir: resolve(import.meta.dirname, '..'), registrationMode: 'full',
    config: options.hostConfig ?? {},
    pluginConfig: { serverUrl: `http://127.0.0.1:${server.address().port}`, autoStartServer: false, ...config },
    runtime: { modelAuth: { resolveApiKeyForProvider: options.auth ?? (async () => ({ apiKey: 'mock-key', mode: 'api-key' })) } },
    logger: Object.fromEntries(['info', 'warn', 'error', 'debug'].map((name) => [name, (s) => log.push(s)])),
    on(name, fn) { hooks.set(name, fn); }, registerService(service) { services.push(service); },
  };
  register(api);
  const call = (hook, event, ctx = context()) => hooks.get(hook)(event, ctx);
  let started = false;
  const drain = async () => { await new Promise((r) => setTimeout(r, 30)); };
  const begin = async (ctx = context(), prompt = 'current request') => {
    if (!started) { started = true; await services[0].start({ stateDir: tmpdir() }); }
    return call('before_prompt_build', { prompt: 'projected request', currentUserMessage: prompt, messages: [] }, ctx);
  };
  return { api, calls, rules, hooks, services, log, call, begin, drain };
}

test('entry metadata is inert and disabled registration has no side effects', async (t) => {
  assert.equal(plugin.id, 'evolveclaw'); assert.equal(typeof plugin.register, 'function');
  const h = await harness(t);
  assert.equal(h.calls.length, 0); assert.equal(h.services.length, 1); assert.equal(h.hooks.size, 7);
  const disabled = await harness(t, { enabled: false });
  assert.equal(disabled.hooks.size, 0); assert.equal(disabled.services.length, 0);
});

test('current OpenClaw payloads retain true model input, assistant text, tools and errors', async (t) => {
  const h = await harness(t);
  await h.begin();
  h.call('llm_input', { runId: 'run-A', sessionId: 'A', systemPrompt: 'actual system instructions' });
  h.call('llm_output', { runId: 'run-A', sessionId: 'A', assistantTexts: ['first', 'second'] });
  h.call('before_tool_call', { toolName: 'search', params: { query: 'evidence' } });
  h.call('after_tool_call', { toolName: 'search', params: {}, result: { found: 2 }, error: 'tool error' });
  await h.call('agent_end', { ...endEvent(), error: 'run error' });
  const body = h.calls.find((c) => c.path === '/step').body;
  assert.equal(body.current_system_prompt, 'actual system instructions');
  assert.equal(body.task, 'current request'); assert.equal(body.model_output, 'first\nsecond');
  assert.match(body.tool_calls, /search.*evidence/); assert.equal(body.observations, '{"found":2}');
  assert.equal(body.error, 'run error'); assert.equal(body.task_id, 'A');
});

test('overlapping completions cannot mix or erase another run and temporary advice stays scoped', async (t) => {
  let release;
  let seen;
  const received = new Promise((r) => { seen = r; });
  const h = await harness(t, {}, { respond: async (path, body) => {
    if (path === '/step' && body.task_id === 'A') { seen(); return new Promise((r) => { release = () => r({ guideline: 'A advice', guideline_type: 'tactical', skipped: false }); }); }
  } });
  await h.begin(context('A'));
  h.call('before_tool_call', { toolName: 'A-tool', params: {} }, context('A'));
  const endingA = h.call('agent_end', endEvent('A answer'), context('A'));
  await received;
  await h.begin(context('B'));
  h.call('before_tool_call', { toolName: 'B-tool', params: {} }, context('B'));
  release(); await endingA;
  await h.call('agent_end', endEvent('B answer'), context('B'));
  const payloads = h.calls.filter((c) => c.path === '/step').map((c) => c.body);
  assert.match(payloads[0].tool_calls, /A-tool/); assert.doesNotMatch(payloads[0].tool_calls, /B-tool/);
  assert.match(payloads[1].tool_calls, /B-tool/); assert.doesNotMatch(payloads[1].tool_calls, /A-tool/);
  const a = await h.begin(context('A', 'next-A'));
  const b = await h.begin(context('B', 'next-B'));
  assert.match(a.appendSystemContext, /A advice/); assert.doesNotMatch(b.appendSystemContext, /A advice/);
});

test('side-trigger and subagent exclusions use identity and do not change foreground state', async (t) => {
  const h = await harness(t);
  await h.begin();
  for (const ctx of [{ ...context('side'), trigger: 'heartbeat' }, { ...context('child'), sessionKey: 'agent:main:subagent:child' }]) {
    assert.deepEqual(await h.begin(ctx), {});
    h.call('before_tool_call', { toolName: 'ignored', params: {} }, ctx);
    await h.call('agent_end', endEvent(), ctx);
  }
  h.call('before_tool_call', { toolName: 'foreground', params: {} });
  await h.call('agent_end', endEvent());
  assert.equal(h.calls.filter((c) => c.path === '/step').length, 1);
  assert.match(h.calls.find((c) => c.path === '/step').body.tool_calls, /foreground/);
});

test('session end prevents a delayed response from reintroducing temporary guidance', async (t) => {
  let release;
  let seen;
  const received = new Promise((r) => { seen = r; });
  const h = await harness(t, {}, { respond: (path) => {
    if (path === '/step') { seen(); return new Promise((r) => { release = () => r({ guideline: 'stale', skipped: false }); }); }
  } });
  await h.begin();
  const ending = h.call('agent_end', endEvent()); await received;
  await h.call('session_end', { sessionId: 'A', sessionKey: 'agent:main:A' });
  release(); await ending;
  assert.deepEqual(await h.begin(context('A', 'new-run')), {});
  assert.deepEqual(h.calls.find((c) => c.path === '/reset').body, { agent_name: 'openclaw-agent', task_id: 'A' });
});

for (const [mode, field] of [['append_system', 'appendSystemContext'], ['prepend_context', 'prependContext']]) {
  test(`${mode} reloads persistent rules, respects consolidation and isolates agent stores`, async (t) => {
    const h = await harness(t, { injectMode: mode });
    h.rules.set('openclaw-agent', ['old guidance']);
    assert.match((await h.begin())[field], /old guidance/);
    h.rules.set('openclaw-agent', ['merged guidance']);
    await h.begin(context('B')); await h.drain();
    const next = (await h.begin(context('B')))[field];
    assert.match(next, /merged guidance/); assert.doesNotMatch(next, /old guidance/);
    assert.deepEqual(await h.begin({ ...context('C'), agentId: 'other' }), {});
    await h.drain();
    assert(h.calls.some((c) => c.path === '/rules/openclaw-agent%3Aother'));
  });
}

test('guideline cap really discards all tactical rules when strategic memory fills the budget', () => {
  const strategic = Array.from({ length: 6 }, (_, i) => ({ text: `${i}`, type: 'strategic' }));
  assert.equal(capGuidelines(strategic, [{ text: 'temporary', type: 'tactical' }], 5).length, 5);
  assert(capGuidelines(strategic, [{ text: 'temporary', type: 'tactical' }], 5).every((g) => g.type === 'strategic'));
});

test('a failure before any assistant message is still learned from', async (t) => {
  const h = await harness(t); await h.begin();
  await h.call('agent_end', { success: false, messages: [], error: 'failure before response' });
  assert.equal(h.calls.find((c) => c.path === '/step').body.error, 'failure before response');
});

test('an old detached sidecar is identified and cannot silently keep the old learning defects', async (t) => {
  const h = await harness(t, {}, { respond: (path) => path === '/health' ? { status: 'ok', version: '0.3.0', configured: true } : undefined });
  await h.begin(); await h.call('agent_end', endEvent()); await h.drain();
  assert(!h.calls.some((c) => c.path === '/step' || c.path === '/configure'));
  assert(h.log.some((s) => s.includes('protocol 2 required')));
});

test('prompt injection remains immediate while background memory retrieval is stalled', async (t) => {
  let stalled = false;
  let release;
  const h = await harness(t, {}, { respond: (path) => stalled && path.startsWith('/rules/') ? new Promise((r) => { release = () => r({ rules: '', guidelines: [], configured: true }); }) : undefined });
  await h.begin(); await h.drain(); stalled = true;
  assert.deepEqual(h.call('before_prompt_build', { prompt: 'request', messages: [] }, context('B')), {});
  await h.drain(); release?.();
});

test('a delayed rule refresh cannot overwrite a newer consolidated snapshot', async (t) => {
  let requests = 0;
  let release;
  let seen;
  const waiting = new Promise((r) => { seen = r; });
  const h = await harness(t, {}, { respond: (path) => {
    if (path.startsWith('/rules/') && ++requests === 2) {
      seen(); return new Promise((r) => { release = () => r({ rules: 'obsolete rule', guidelines: ['obsolete rule'], configured: true }); });
    }
    if (path === '/step') {
      h.rules.set('openclaw-agent', ['authoritative merged rule']);
      return { guideline: 'raw suggestion', guideline_type: 'strategic', skipped: false };
    }
  } });
  h.rules.set('openclaw-agent', ['obsolete rule']);
  await h.begin(); await waiting;
  await h.call('agent_end', endEvent());
  release(); await h.drain();
  const result = h.call('before_prompt_build', { prompt: 'request', messages: [] }, context('B'));
  assert.match(result.appendSystemContext, /authoritative merged rule/);
  assert.doesNotMatch(result.appendSystemContext, /obsolete rule|raw suggestion/);
});

test('auto-configuration retries after failure and supports string model refs and provider URLs', async (t) => {
  let attempts = 0;
  const h = await harness(t, {}, {
    configured: false,
    hostConfig: { agents: { defaults: { model: 'custom/model-name@profile' } }, models: { providers: { custom: { api: 'openai-completions', baseUrl: 'https://example.invalid/v1' } } } },
    respond: (path) => path === '/configure' && ++attempts === 1 ? { status: 'error' } : undefined,
  });
  await h.begin(); await h.drain(); await h.begin(context('B')); await h.drain();
  const requests = h.calls.filter((c) => c.path === '/configure');
  assert.equal(requests.length, 2);
  assert.deepEqual(requests[1].body, { provider: 'openai', model: 'model-name', api_key: 'mock-key', base_url: 'https://example.invalid/v1' });
});

test('OAuth credentials are not forwarded as sidecar API keys; explicit overrides still work', async (t) => {
  const opts = { configured: false, hostConfig: { agents: { defaults: { model: { primary: 'openai/model' } } } }, auth: async () => ({ apiKey: 'oauth-token', mode: 'oauth' }) };
  const h = await harness(t, {}, opts); await h.begin();
  assert(!h.calls.some((c) => c.path === '/configure'));
  const explicit = await harness(t, { scopeProvider: 'anthropic', scopeModel: 'claude-test', scopeApiKey: 'explicit-test-key' }, opts);
  await explicit.begin();
  assert.equal(explicit.calls.find((c) => c.path === '/configure').body.api_key, 'explicit-test-key');
});

test('changed explicit model overrides are forwarded to an already-configured sidecar on service start', async (t) => {
  const h = await harness(t, { scopeModel: 'changed-model', scopeProvider: 'openai', scopeApiKey: 'changed-fake-key', scopeBaseUrl: 'https://new.invalid/v1' });
  await h.begin();
  assert.deepEqual(h.calls.find((c) => c.path === '/configure').body, {
    provider: 'openai', model: 'changed-model', api_key: 'changed-fake-key', base_url: 'https://new.invalid/v1',
  });
});

test('an unavailable sidecar leaves normal prompts usable and recovers on a later turn', async (t) => {
  const h = await harness(t);
  h.api.pluginConfig.serverUrl = 'http://127.0.0.1:1';
  const hooks = new Map(); register({ ...h.api, on: (name, fn) => hooks.set(name, fn) });
  assert.deepEqual(await hooks.get('before_prompt_build')({ prompt: 'request', messages: [] }, context()), {});
  await hooks.get('agent_end')(endEvent(), context());
});

test('owned Python sidecar starts on the configured port and stops with the plugin', { skip: !process.env.EVOLVECLAW_TEST_PYTHON }, async (t) => {
  const placeholder = http.createServer(); await new Promise((r) => placeholder.listen(0, '127.0.0.1', r));
  const port = placeholder.address().port; await new Promise((r) => placeholder.close(r));
  const h = await harness(t, { serverUrl: `http://127.0.0.1:${port}`, autoStartServer: true, pythonPath: process.env.EVOLVECLAW_TEST_PYTHON });
  const stateDir = await mkdtemp(resolve(tmpdir(), 'evolveclaw-owned-'));
  t.after(() => rm(stateDir, { recursive: true, force: true }));
  t.after(() => h.services[0].stop());
  await h.services[0].start({ stateDir });
  const res = await fetch(`http://127.0.0.1:${port}/health`);
  assert.equal(res.status, 200);
  await h.services[0].stop();
  await assert.rejects(fetch(`http://127.0.0.1:${port}/health`));
});
