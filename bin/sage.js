#!/usr/bin/env node
import { createInterface } from 'node:readline/promises';
import { stdin, stdout } from 'node:process';
import { detectHosts, initialize } from '../setup/init.js';

export function parseSelection(answer) {
  const names = { '1': 'claude-code', '2': 'codex' };
  const values = answer.trim().split(/[\s,]+/).filter(Boolean);
  if (!values.length || values.some(x => !names[x])) throw new Error('Choose 1, 2, or 1,2. No installation was attempted.');
  return [...new Set(values.map(x => names[x]))];
}

export async function askSelection(prompt) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  prompt.once('SIGINT', cancel);
  try {
    return parseSelection(await prompt.question('Enter 1, 2, or 1,2 (Ctrl+C to cancel): ', { signal: controller.signal }));
  } catch (error) {
    if (error.name === 'AbortError') return null;
    throw error;
  } finally { prompt.removeListener('SIGINT', cancel); }
}

export async function main(args = process.argv.slice(2)) {
  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    console.log('Usage: sage init\nSelect Claude Code, Codex, or both for user-wide native plugin setup.\nRequires Node 22+, Python 3.8+, Git and the selected host CLIs.\nLearning-directory selection remains in the first Sage learning session.');
    return 0;
  }
  if (args.length !== 1 || args[0] !== 'init') throw new Error('Usage: sage init');
  if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Sage setup requires Node 22+.');
  if (!stdin.isTTY || !stdout.isTTY) throw new Error('Run sage init in an interactive terminal to select coding agents. No installation was attempted.');
  console.log('Which coding agents do you use? Select one or both.');
  detectHosts().forEach((x, i) => console.log(`${i + 1}. ${x.id}: ${x.version ?? 'not found; install this CLI before selecting it'}`));
  const prompt = createInterface({ input: stdin, output: stdout });
  let selected;
  try { selected = await askSelection(prompt); }
  finally { prompt.close(); }
  if (!selected) { console.log('Cancelled. No installation was attempted.'); return 0; }
  const results = await initialize(selected);
  for (const result of results) console.log(`\n${result.host}: ${result.status}\n${result.message}`);
  return results.every(x => ['configured', 'already-configured'].includes(x.status)) ? 0 : 1;
}

// Importable for tests, executable from source or an npm tarball.
import { pathToFileURL } from 'node:url';
import { realpathSync } from 'node:fs';
if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main().then(code => { process.exitCode = code; }).catch(error => {
    console.error(error.message); process.exitCode = 1;
  });
}
