'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const adapter = path.join(__dirname, '..', 'babel_parser_adapter.cjs');
const input = {
  files: [
    { path: 'src/main.ts', content: 'import { value as localValue } from "./value";\nexport const run = () => localValue();\n' },
    { path: 'src/value.ts', content: 'export function value() { return 1; }\n' },
    { path: 'tsconfig.json', content: '{\n  "compilerOptions": { "paths": { "@/*": ["src/*"] } }\n}\n' },
  ],
};
const result = spawnSync(process.execPath, [adapter], { input: JSON.stringify(input), encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);
const parsed = JSON.parse(result.stdout);
assert.match(parsed.parser, /^@babel\/parser@\d+\.\d+\.\d+$/);
const main = parsed.files.find((file) => file.path === 'src/main.ts');
assert.equal(main.edges[0].specifier, './value');
assert.equal(main.edges[0].line, 1);
assert.equal(main.bindings[0].local, 'localValue');
assert.equal(main.bindings[0].imported, 'value');
assert.equal(main.calls[0].callee, 'localValue');
const value = parsed.files.find((file) => file.path === 'src/value.ts');
assert.equal(value.exports[0].name, 'value');
process.stdout.write('parser adapter assertions passed\n');
