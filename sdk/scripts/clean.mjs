import { rmSync } from 'node:fs';

for (const directory of ['../dist', '../dist-cjs']) {
  rmSync(new URL(directory, import.meta.url), { recursive: true, force: true });
}
