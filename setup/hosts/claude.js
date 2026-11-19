import { makeAdapter } from './shared.js';

export default makeAdapter({
  id: 'claude-code', command: 'claude', pluginKey: 'plugins', marketKey: 'marketplaces',
  normalize: x => ({ id: x.id, name: x.id?.split('@')[0], enabled: x.enabled,
    scope: x.scope, path: x.installPath, version: x.version }),
  marketSource: x => x.source === 'github' ? x.repo : (x.url ?? x.source?.repo),
  installArgs: ['plugin', 'install', 'sage@sage', '--scope', 'user', '--json'],
});
