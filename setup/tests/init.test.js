import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm, readFile, cp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { initialize } from '../init.js';
import { parseSelection, askSelection } from '../../bin/sage.js';
import { EventEmitter } from 'node:events';
import { jsonOutput } from '../process.js';
import { officialSource } from '../hosts/shared.js';
import { installedPath } from '../hosts/codex.js';

async function fixture(t, settings = {}) {
  const home = await mkdtemp(join(tmpdir(), 'sage-setup-'));
  t.after(() => rm(home, { recursive: true, force: true }));
  const cwd = join(home, 'project'); await mkdir(cwd);
  const root = join(home, 'native-cache'); await mkdir(root);
  const files = ['skills/sage/SKILL.md', 'tools/plugin_root.py', 'tools/session_context.py',
    'tools/host_hooks.py', 'agents/artifact-clerk.md', 'hooks/claude-hooks.json', 'hooks/codex-hooks.json'];
  for (const file of files) { await mkdir(resolve(root, file, '..'), { recursive: true }); await writeFile(join(root, file), '{}'); }
  for (const stem of ['claude', 'codex']) {
    await mkdir(join(root, `.${stem}-plugin`));
    await writeFile(join(root, `.${stem}-plugin/plugin.json`), JSON.stringify({ name: 'sage', version: '1.3.0', hooks: `./hooks/${stem}-hooks.json` }));
  }
  const calls = []; const installed = { claude: false, codex: false, ...settings.installed };
  const markets = { claude: false, codex: false, ...settings.markets };
  const run = (command, args) => {
    calls.push([command, ...args]);
    if (command === settings.missing) throw new Error('not found');
    if (args.includes('--help')) return settings.unsupported ? 'old CLI' : '--json --scope';
    if (command === 'python3' || command === 'git') return 'ok';
    if (args.includes('--version')) return 'host version';
    if (args.join(' ') === 'plugin marketplace list --json') {
      const values = markets[command] ? [{ name: 'sage', source: 'github', repo: settings.collision ? 'other/repo' : '0-BSCode/sage', marketplaceSource: { source: settings.collision ? 'other/repo' : 'https://github.com/0-BSCode/sage.git', sourceType: 'git' } }] : [];
      return JSON.stringify(command === 'claude' ? values : { marketplaces: values });
    }
    if (args.join(' ') === 'plugin list --json') {
      if (settings.badJSON) return 'not JSON';
      const values = installed[command] ? [{ id: 'sage@sage', pluginId: 'sage@sage', name: 'sage', marketplaceName: 'sage',
        scope: settings.scope ?? 'user', enabled: !settings.disabled,
        ...(settings.nativeCodex && command === 'codex' ? {} : { installPath: root }),
        version: settings.version ?? '1.3.0', source: { source: 'local', path: root } }] : [];
      return JSON.stringify(command === 'claude' ? values : { installed: values, available: [] });
    }
    if (args[1] === 'marketplace' && args[2] === 'add') { markets[command] = true; return '{}'; }
    if (args[1] === 'install' || args[1] === 'add') {
      if (settings.failInstall === command) throw new Error('install failed');
      installed[command] = !settings.noPostInstall; return '{}';
    }
    throw new Error(`Unexpected command: ${command} ${args}`);
  };
  return { home, cwd, root, calls, run, installed, markets };
}

test('selection is explicit, supports both and rejects blank/invalid input', () => {
  assert.deepEqual(parseSelection('1,2,1'), ['claude-code', 'codex']);
  assert.deepEqual(parseSelection('2'), ['codex']);
  for (const value of ['', '3', 'claude', '1;echo']) assert.throws(() => parseSelection(value));
});

test('Ctrl+C cancels selection before registration', async () => {
  const prompt = new EventEmitter();
  prompt.question = (_text, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(Object.assign(new Error('cancelled'), { name: 'AbortError' })));
  });
  const selection = askSelection(prompt);
  prompt.emit('SIGINT');
  assert.equal(await selection, null);
  assert.equal(prompt.listenerCount('SIGINT'), 0);
});

test('both native adapters install user-wide, preserve records and reconcile reruns', async t => {
  const f = await fixture(t);
  await mkdir(join(f.home, '.config/sage'), { recursive: true });
  const config = join(f.home, '.config/sage/config.json'); await writeFile(config, '{"learning_root":"/keep"}');
  const results = await initialize(['claude-code', 'codex'], f);
  assert.deepEqual(results.map(x => x.status), ['configured', 'configured']);
  assert.ok(f.calls.some(x => x.join(' ') === 'claude plugin install sage@sage --scope user --json'));
  assert.ok(f.calls.some(x => x.join(' ') === 'codex plugin add sage@sage --json'));
  assert.ok(f.calls.every(x => !x.includes('-y') && !x.includes('--yes')));
  assert.equal(await readFile(config, 'utf8'), '{"learning_root":"/keep"}');
  f.calls.length = 0;
  assert.deepEqual((await initialize(['claude-code', 'codex'], f)).map(x => x.status), ['already-configured', 'already-configured']);
  assert.ok(!f.calls.some(x => !x.includes('--help') && (x.includes('install') || x.includes('add') || x.includes('update'))));
  assert.match(results[1].message, /trust Sage hooks/);
  assert.match(results[0].message, /first learning session/);
});

test('a preflight failure makes no host registration changes', async t => {
  for (const settings of [{ missing: 'python3' }, { missing: 'codex' }, { unsupported: true }, { badJSON: true }]) {
    const f = await fixture(t, settings);
    const result = await initialize(['claude-code', 'codex'], f);
    assert.ok(result.some(x => !['configured', 'already-configured'].includes(x.status)));
    assert.ok(!f.calls.some(x => x.includes('add') && !x.includes('--help') || x.includes('install') && !x.includes('--help')));
  }
});

test('conflicting standalone skill is preserved and reported', async t => {
  const f = await fixture(t);
  const path = join(f.home, '.agents/skills/sage/SKILL.md');
  await mkdir(resolve(path, '..'), { recursive: true }); await writeFile(path, 'user content');
  const result = await initialize(['codex'], f);
  assert.equal(result[0].status, 'requires-user-action');
  assert.match(result[0].message, /Conflicting standalone/);
  assert.equal(await readFile(path, 'utf8'), 'user content');
});

test('marketplace collision and disabled/non-user installations require manual reconciliation', async t => {
  for (const settings of [
    { markets: { claude: true }, collision: true },
    { installed: { claude: true }, markets: { claude: true }, disabled: true },
    { installed: { claude: true }, markets: { claude: true }, scope: 'project' },
  ]) {
    const f = await fixture(t, settings);
    const result = await initialize(['claude-code'], f);
    assert.equal(result[0].status, 'requires-user-action');
  }
});

test('outdated resource layout is not silently upgraded', async t => {
  const f = await fixture(t, { installed: { codex: true }, markets: { codex: true } });
  await rm(join(f.root, 'tools/session_context.py'));
  const result = await initialize(['codex'], f);
  assert.equal(result[0].status, 'requires-user-action');
  assert.match(result[0].message, /outdated/);
});

test('new marketplace files do not conceal an older installed plugin', async t => {
  const f = await fixture(t, { installed: { codex: true }, markets: { codex: true }, version: '1.2.0' });
  assert.equal((await initialize(['codex'], f))[0].status, 'requires-user-action');
});

test('Codex verifies the installed cache rather than intact marketplace files', async t => {
  const f = await fixture(t, { nativeCodex: true, installed: { codex: true }, markets: { codex: true } });
  const previous = process.env.CODEX_HOME;
  process.env.CODEX_HOME = join(f.home, 'custom-codex');
  t.after(() => { if (previous === undefined) delete process.env.CODEX_HOME; else process.env.CODEX_HOME = previous; });
  const cache = installedPath({ name: 'sage', marketplaceName: 'sage', version: '1.3.0' }, f);
  await cp(f.root, cache, { recursive: true });
  assert.equal((await initialize(['codex'], f))[0].status, 'already-configured');
  await rm(join(cache, 'tools/session_context.py'));
  assert.equal((await initialize(['codex'], f))[0].status, 'requires-user-action');
  assert.equal(await readFile(join(f.root, 'tools/session_context.py'), 'utf8'), '{}');
  delete process.env.CODEX_HOME;
  assert.equal(installedPath({ name: 'sage', marketplaceName: 'sage', version: '1.3.0' }, f),
    join(f.home, '.codex/plugins/cache/sage/sage/1.3.0'));
  assert.equal(installedPath({ name: 'sage', marketplaceName: 'sage', version: '../source' }, f), null);
});

test('partial install success is retained and retry is safe', async t => {
  const settings = { failInstall: 'codex' }; const f = await fixture(t, settings);
  const result = await initialize(['claude-code', 'codex'], f);
  assert.deepEqual(result.map(x => x.status), ['configured', 'failed']);
  settings.failInstall = null; f.calls.length = 0;
  const retry = await initialize(['claude-code', 'codex'], f);
  assert.deepEqual(retry.map(x => x.status), ['already-configured', 'configured']);
  assert.ok(!f.calls.some(x => x[0] === 'claude' && x.includes('install') && !x.includes('--help')));
});

test('post-install inventory must confirm native registration', async t => {
  const f = await fixture(t, { noPostInstall: true });
  assert.equal((await initialize(['codex'], f))[0].status, 'failed');
});

test('source matching is exact and JSON failures are actionable', () => {
  assert.ok(officialSource('https://github.com/0-BSCode/sage.git'));
  assert.ok(!officialSource('https://evil.example/0-BSCode/sage'));
  assert.ok(!officialSource('0-BSCode/sage-malicious'));
  assert.deepEqual(jsonOutput('Progress\n{"ok":true}'), { ok: true });
  assert.throws(() => jsonOutput('bad data'), /unrecognized JSON/);
});

test('CLI help and noninteractive init do not mutate host configuration', () => {
  const cli = new URL('../../bin/sage.js', import.meta.url);
  assert.equal(spawnSync(process.execPath, [cli.pathname, '--help']).status, 0);
  const result = spawnSync(process.execPath, [cli.pathname, 'init'], { encoding: 'utf8' });
  assert.equal(result.status, 1); assert.match(result.stderr, /interactive terminal/);
});
