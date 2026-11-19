import { homedir } from 'node:os';
import { run as nativeRun } from './process.js';
import claude from './hosts/claude.js';
import codex from './hosts/codex.js';

export const adapters = [claude, codex];

export function detectHosts(run = nativeRun) {
  return adapters.map(adapter => ({ id: adapter.id, version: adapter.detect(run) }));
}

export async function initialize(selected, { run = nativeRun, home = homedir(), cwd = process.cwd() } = {}) {
  if (!Array.isArray(selected) || !selected.length || new Set(selected).size !== selected.length ||
      selected.some(id => !adapters.some(a => a.id === id))) throw new Error('Select Claude Code, Codex, or both.');
  const hosts = adapters.filter(a => selected.includes(a.id));
  const states = new Map();
  const results = [];
  try {
    run('python3', ['-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else "Sage requires Python 3.8+")']);
    run('git', ['--version']);
  } catch (error) {
    return hosts.map(a => ({ host: a.id, status: 'failed', message: `Prerequisite unavailable: ${error.message}. Install the prerequisite and retry.` }));
  }
  // Complete all preflight checks before any host registration.
  for (const adapter of hosts) {
    try {
      adapter.preflight(run);
      states.set(adapter.id, await adapter.inspect(run, { home, cwd }));
    } catch (error) {
      results.push({ host: adapter.id, status: 'requires-user-action', message: error.message });
    }
  }
  if (results.length) {
    return hosts.map(a => results.find(x => x.host === a.id) ?? ({ host: a.id,
      status: states.get(a.id)?.installed ? 'already-configured' : 'requires-user-action',
      message: 'No installation attempted because another selected host failed preflight. Resolve the reported issue and retry. ' + a.guidance }));
  }
  for (const adapter of hosts) {
    try {
      const state = states.get(adapter.id);
      if (!state.installed) {
        adapter.install(run, state);
        const after = await adapter.inspect(run, { home, cwd });
        if (!after.installed) throw new Error('Native host did not report a compatible installed Sage plugin.');
      }
      results.push({ host: adapter.id, status: state.installed ? 'already-configured' : 'configured',
        message: adapter.guidance + ' Registration is confirmed; runtime safeguards require host review/access. Your learning configuration and records were preserved. If no learning directory is configured, Sage will ask during your first learning session.' });
    } catch (error) {
      results.push({ host: adapter.id, status: 'failed', message: `${error.message}. Other successful host registrations are retained. Retry init after resolving this host's issue.` });
    }
  }
  return results;
}
