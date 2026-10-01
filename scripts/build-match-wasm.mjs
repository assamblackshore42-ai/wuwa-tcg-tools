import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const local = path.join(
    root,
    '.tools/wasm-pack/bin',
    process.platform === 'win32' ? 'wasm-pack.exe' : 'wasm-pack',
);
const executable = existsSync(local) ? local : 'wasm-pack';
const version = spawnSync(executable, ['--version'], { encoding: 'utf8' });
if (version.status !== 0 || version.stdout.trim() !== 'wasm-pack 0.15.0') {
    throw new Error('wasm-pack 0.15.0 is required. See apps/match-manager-web/README.md.');
}
const result = spawnSync(
    executable,
    ['build', 'crates/match-core-wasm', '--target', 'web', '--release', '--', '--locked'],
    { cwd: root, stdio: 'inherit' },
);
if (result.error) throw result.error;
process.exit(result.status ?? 1);
