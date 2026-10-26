'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const adapter = path.join(__dirname, '..', 'babel_parser_adapter.cjs');
const input = {
  files: [
    { path: 'src/main.ts', content: 'import { value as localValue } from "./value";\nexport const run = () => localValue();\n' },
    { path: 'src/value.ts', content: 'export function value() { return 1; }\n' },
    { path: 'src/flow.ts', content: 'export function relay(input: string) {\n  const copy = input;\n  const cleaned = sanitize(copy);\n  deliver(\n    cleaned,\n  );\n  return (\n    cleaned\n  );\n}\n' },
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
const flow = parsed.files.find((file) => file.path === 'src/flow.ts');
assert.ok(flow.value_flows.some((item) => item.kind === 'alias' && item.from_symbol === 'input' && item.to_symbol === 'copy'));
assert.ok(flow.value_flows.some((item) => item.kind === 'call_result' && item.from_callee === 'sanitize' && item.to_symbol === 'cleaned'));
const delivered = flow.value_flows.find((item) => item.kind === 'call_argument' && item.from_symbol === 'cleaned' && item.to_callee === 'deliver');
assert.deepEqual(delivered.evidence.source_use, { path: 'src/flow.ts', line: 5 });
assert.deepEqual(delivered.evidence.call_site, { path: 'src/flow.ts', line: 4 });
const returned = flow.value_flows.find((item) => item.kind === 'return' && item.from_symbol === 'cleaned');
assert.deepEqual(returned.evidence.source_use, { path: 'src/flow.ts', line: 8 });
assert.deepEqual(returned.evidence.return_site, { path: 'src/flow.ts', line: 7 });
process.stdout.write('parser adapter assertions passed\n');
