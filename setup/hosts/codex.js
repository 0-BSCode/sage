import { makeAdapter } from './shared.js';
import { join, resolve } from 'node:path';

// Codex 0.160 lists the marketplace source, not the installed path. Its native
// cache is versioned under CODEX_HOME; never validate the marketplace checkout.
export function installedPath(x, { home }) {
  if (x.installedPath ?? x.installPath) return x.installedPath ?? x.installPath;
  if (x.name !== 'sage' || x.marketplaceName !== 'sage' || !/^\d+\.\d+\.\d+$/.test(x.version ?? '')) return null;
  return join(resolve(process.env.CODEX_HOME || join(home, '.codex')), 'plugins/cache/sage/sage', x.version);
}

export default makeAdapter({
  id: 'codex', command: 'codex', pluginKey: 'installed', marketKey: 'marketplaces',
  normalize: (x, context) => ({ id: (x.name && x.marketplaceName ? `${x.name}@${x.marketplaceName}` : x.pluginId),
    name: x.name, enabled: x.enabled, scope: 'user', version: x.version,
    path: installedPath(x, context) }),
  marketSource: x => x.marketplaceSource?.source,
  installArgs: ['plugin', 'add', 'sage@sage', '--json'],
});
