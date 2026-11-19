#!/usr/bin/env node
// Build and exercise the shipped initializer without network or real host writes.
import { mkdtempSync, mkdirSync, writeFileSync, chmodSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const temp = mkdtempSync(join(tmpdir(), 'sage-pack-'));
function exec(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', timeout: 45000, ...options });
  assert.equal(result.status, 0, result.stderr || result.error?.message || result.stdout);
  return result.stdout;
}
try {
  const packed = JSON.parse(exec('npm', ['pack', '--json', '--ignore-scripts', '--pack-destination', temp], {
    cwd: root, env: { ...process.env, npm_config_cache: join(temp, 'npm-cache') },
  }))[0];
  const names = packed.files.map(x => x.path);
  for (const required of ['bin/sage.js', 'setup/init.js', 'setup/hosts/claude.js', 'setup/hosts/codex.js']) assert.ok(names.includes(required), required);
  assert.ok(names.every(x => !x.includes('tests/') && !x.startsWith('openspec/') && !x.startsWith('tools/')));
  exec('tar', ['-xzf', join(temp, packed.filename), '-C', temp]);
  const home = join(temp, 'home'); const cwd = join(temp, 'launch'); const bin = join(temp, 'fake-bin');
  for (const path of [home, cwd, bin]) mkdirSync(path);
  // Model native host caches, independently of the packed initializer.
  const plugin = join(home, 'host-managed-plugin');
  for (const file of ['skills/sage/SKILL.md', 'agents/artifact-clerk.md', 'tools/plugin_root.py',
    'tools/session_context.py', 'tools/host_hooks.py', 'hooks/claude-hooks.json', 'hooks/codex-hooks.json']) {
    mkdirSync(dirname(join(plugin, file)), { recursive: true }); writeFileSync(join(plugin, file), '{}');
  }
  for (const stem of ['claude', 'codex']) {
    mkdirSync(join(plugin, `.${stem}-plugin`));
    writeFileSync(join(plugin, `.${stem}-plugin/plugin.json`), JSON.stringify({name:'sage',version:'1.3.0',hooks:`./hooks/${stem}-hooks.json`}));
  }
  const fake = `#!${process.execPath}
import{existsSync,writeFileSync}from'node:fs';import{basename,join}from'node:path';
const command=basename(process.argv[1]),a=process.argv.slice(2),h=process.env.HOME;
const marker=join(h,command+'-installed'),market=join(h,command+'-marketplace'),root=join(h,'host-managed-plugin');
if(a.includes('--help'))console.log('--json --scope');
else if(command==='python3'||command==='git')console.log('ok');
else if(a[1]==='marketplace'&&a[2]==='list'){
 const entries=existsSync(market)?[{name:'sage',source:'github',repo:'0-BSCode/sage',marketplaceSource:{sourceType:'git',source:'0-BSCode/sage'}}]:[];
 console.log(JSON.stringify(command==='claude'?entries:{marketplaces:entries}));
}else if(a[1]==='marketplace'&&a[2]==='add'){writeFileSync(market,'1');console.log('{}');}
else if(a[1]==='list'){
 const entries=existsSync(marker)?[{id:'sage@sage',pluginId:'sage@sage',name:'sage',marketplaceName:'sage',scope:'user',enabled:true,installPath:root,version:'1.3.0'}]:[];
 console.log(JSON.stringify(command==='claude'?entries:{installed:entries,available:[]}));
}else if(a[1]==='install'||a[1]==='add'){writeFileSync(marker,'1');console.log('{}');}
else {console.error('Unexpected command');process.exit(1);}
`;
  for (const name of ['claude', 'codex', 'python3', 'git']) {
    // .mjs suffix on the shared script ensures ESM outside any package scope.
    writeFileSync(join(bin, name + '.mjs'), fake); chmodSync(join(bin, name + '.mjs'), 0o755);
    writeFileSync(join(bin, name), `#!/bin/sh\nexec '${process.execPath}' '${join(bin, name + '.mjs')}' "$@"\n`);
    chmodSync(join(bin, name), 0o755);
  }
  // Fake executables normalize their .mjs names to native command names.
  for (const name of ['claude','codex','python3','git']) writeFileSync(join(bin,name+'.mjs'),fake.replace('basename(process.argv[1])',"basename(process.argv[1]).replace(/\\.mjs$/, '')"));
  const env = { ...process.env, HOME: home, PATH: bin + ':' + process.env.PATH };
  const uri = new URL('file://' + join(temp, 'package/setup/init.js')).href;
  const script = `import {initialize} from ${JSON.stringify(uri)}; for(let i=0;i<2;i++){const r=await initialize(['claude-code','codex']); if(r.some(x=>!['configured','already-configured'].includes(x.status)))throw Error(JSON.stringify(r)); console.log(r.map(x=>x.status).join(','));}`;
  const result = exec(process.execPath, ['--input-type=module', '-e', script], { cwd, env });
  assert.match(result, /configured,configured/); assert.match(result, /already-configured,already-configured/);
  assert.deepEqual(readdirSync(cwd), []);
  exec(process.execPath, [join(temp, 'package/bin/sage.js'), '--help'], { cwd, env });
  assert.equal(readFileSync(join(home,'claude-installed'),'utf8'),'1');
  console.log('Packed initializer passed isolated native-adapter setup and repeat-run checks.');
} finally { rmSync(temp, { recursive: true, force: true }); }
