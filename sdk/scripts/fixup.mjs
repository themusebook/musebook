import { renameSync, writeFileSync } from 'node:fs';

// Keep module-local declarations so NodeNext resolves ESM and CJS independently.
renameSync(new URL('../dist-cjs', import.meta.url), new URL('../dist/cjs', import.meta.url));
writeFileSync(new URL('../dist/cjs/package.json', import.meta.url), '{"type":"commonjs"}\n');
writeFileSync(new URL('../dist/index.cjs', import.meta.url), 'module.exports = require("./cjs/index.js");\n');
console.log('fixup: ESM, CJS, browser entry point and declarations ready');
