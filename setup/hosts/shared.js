import { readFile, realpath, access } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { jsonOutput } from '../process.js';

export const SOURCE = '0-BSCode/sage';
export const PLUGIN = 'sage@sage';

export function officialSource(source) {
  return typeof source === 'string' && /^(?:https:\/\/github\.com\/|git@github\.com:)?0-bscode\/sage(?:\.git)?\/?$/i.test(source);
}

export function list(value, key) {
  const result = Array.isArray(value) ? value : value?.[key];
  if (!Array.isArray(result)) throw new Error(`Unrecognized host inventory (${key}); upgrade or use manual setup.`);
  return result;
}

export async function standaloneConflicts(host, home, cwd) {
  const dirs = host === 'claude-code' ? ['.claude/skills', '.agents/skills'] : ['.codex/skills', '.agents/skills'];
  const found = [];
  // Walk ancestors because project skills may come from a parent workspace.
  const roots = new Set([resolve(home)]);
  for (let root = resolve(cwd); ; root = resolve(root, '..')) {
    roots.add(root);
    if (root === resolve(root, '..')) break;
  }
  for (const root of roots) for (const dir of dirs) {
    const path = join(root, dir, 'sage', 'SKILL.md');
    try {
      await access(path);
      found.push(path);
    } catch (error) {
      if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error;
    }
  }
  return [...new Set(found)];
}

export async function compatiblePlugin(path, host, installedVersion) {
  if (!path) return false;
  try {
    const root = await realpath(path);
    const manifest = JSON.parse(await readFile(join(root, host === 'codex' ? '.codex-plugin/plugin.json' : '.claude-plugin/plugin.json'), 'utf8'));
    const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(manifest.version ?? '');
    if (manifest.name !== 'sage' || !match || manifest.version !== installedVersion || Number(match[1]) !== 1 || Number(match[2]) < 3) return false;
    const expected = `./hooks/${host === 'codex' ? 'codex' : 'claude'}-hooks.json`;
    if (manifest.hooks !== expected) return false;
    for (const file of ['skills/sage/SKILL.md', 'tools/plugin_root.py', 'tools/session_context.py',
      'tools/host_hooks.py', 'agents/artifact-clerk.md', expected]) await access(join(root, file));
    return true;
  } catch { return false; }
}

export function makeAdapter({ id, command, pluginKey, marketKey, normalize, marketSource, installArgs }) {
  return {
    id, command,
    detect(run) { try { return run(command, ['--version']); } catch { return null; } },
    preflight(run) {
      const checks = [
        [['plugin', 'list', '--help'], ['--json']],
        [['plugin', 'marketplace', 'list', '--help'], ['--json']],
        [['plugin', 'marketplace', 'add', '--help'], ['--json']],
        [['plugin', id === 'codex' ? 'add' : 'install', '--help'], ['--json', ...(id === 'claude-code' ? ['--scope'] : [])]],
      ];
      for (const [args, flags] of checks) {
        const help = run(command, args);
        for (const flag of flags) if (!help.includes(flag)) throw new Error(`${command} lacks ${flag} for ${args.slice(0, -1).join(' ')}; upgrade it or use manual setup.`);
      }
    },
    inventory(run, context) {
      const plugins = list(jsonOutput(run(command, ['plugin', 'list', '--json'])), pluginKey).map(x => normalize(x, context));
      const marketplaces = list(jsonOutput(run(command, ['plugin', 'marketplace', 'list', '--json'])), marketKey);
      return { plugins, marketplaces };
    },
    async inspect(run, { home, cwd }) {
      const conflicts = await standaloneConflicts(id, home, cwd);
      if (conflicts.length) throw new Error(`Conflicting standalone Sage skill: ${conflicts.join(', ')}. Remove or relocate the conflicting registration manually before retrying; no files were deleted.`);
      const inventory = this.inventory(run, { home, cwd });
      const markets = inventory.marketplaces.filter(x => x.name === 'sage');
      if (markets.length > 1 || markets.some(x => !officialSource(marketSource(x)))) throw new Error('Marketplace sage points to a different or unverifiable source; reconcile it manually.');
      const candidates = inventory.plugins.filter(x => x.id === PLUGIN || x.name === 'sage');
      if (candidates.length > 1) throw new Error('Multiple Sage plugin registrations found; reconcile their scopes manually.');
      const plugin = candidates[0];
      if (plugin) {
        if (plugin.id !== PLUGIN || plugin.enabled !== true || plugin.scope !== 'user' || !markets.length ||
            !await compatiblePlugin(plugin.path, id, plugin.version)) {
          throw new Error(`Existing Sage plugin is disabled, outdated, non-user-scoped, or unverifiable. Review it with ${command} plugin list --json and update/enable it through native host management before retrying.`);
        }
        return { installed: true, marketplace: true };
      }
      return { installed: false, marketplace: markets.length === 1 };
    },
    install(run, state) {
      if (!state.marketplace) run(command, ['plugin', 'marketplace', 'add', SOURCE, '--json', ...(id === 'claude-code' ? ['--scope', 'user'] : [])]);
      run(command, installArgs);
    },
    guidance: id === 'codex'
      ? 'Start a new Codex thread. Review and trust Sage hooks in /hooks; grant learning-directory access if needed. Then invoke $sage:sage learn <topic>.'
      : 'Start a new Claude Code session. Review Sage hooks with native host controls and grant learning-directory access if needed. Then invoke /sage learn <topic>.',
  };
}
