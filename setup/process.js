import { spawnSync } from 'node:child_process';

// No shell: paths, names and subprocess output must never become shell code.
export function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf8', timeout: 45000, maxBuffer: 4 * 1024 * 1024,
    cwd: options.cwd, env: options.env ?? process.env,
    stdio: ['ignore', 'pipe', 'pipe'], shell: false,
  });
  if (result.error || result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')}: ${result.error?.message ?? result.stderr?.trim() ?? 'failed'}`);
  }
  return result.stdout.trim();
}

export function jsonOutput(text) {
  try { return JSON.parse(text); } catch {
    // Some native commands print progress followed by a JSON result line.
    const last = text.trim().split('\n').at(-1);
    try { return JSON.parse(last); } catch { throw new Error('Host returned unrecognized JSON; upgrade the host or use manual setup.'); }
  }
}
