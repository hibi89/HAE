'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const adapter = path.join(__dirname, '..', 'babel_parser_adapter.cjs');
const input = {
  files: [
    { path: 'src/main.ts', content: 'import { value as localValue } from "./value";\nexport const run = () => localValue();\n' },
    { path: 'src/value.ts', content: 'export function value() { return 1; }\n' },
    {
      path: 'src/dynamic.ts',
      content: 'export async function load(name: string) {\n'
        + '  const known = await import("./parts/known");\n'
        + '  const templated = await import(`./parts/known`);\n'
        + '  const computed = await import(name);\n'
        + '  return [known, templated, computed];\n}\n',
    },
    {
      path: 'src/contracts.ts',
      content: 'export async function load(id: string, options?: { cache: boolean }): Promise<Result> { return await source("body-only"); }\n'
        + 'export const transform = (value: string, count = 9137): string => value;\n'
        + 'function helper(input: Payload): void {}\nexport { helper as publicHelper };\n'
        + 'export default function (input: Payload): Promise<Response> { return route(input); }\n'
        + 'export function combine(...parts: string[]): string { return parts.join("hidden-default"); }\n',
    },
    {
      path: 'src/contracts.cjs',
      content: 'exports.named = function named(input) {};\n'
        + 'module.exports.convert = (value) => value;\n'
        + 'module.exports = function (payload) {};\n',
    },
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
const dynamicEdges = parsed.files.find((file) => file.path === 'src/dynamic.ts').edges
  .filter((edge) => edge.kind === 'dynamic_import');
assert.deepEqual(dynamicEdges.map((edge) => [edge.specifier, edge.line]), [
  ['./parts/known', 2], ['./parts/known', 3], [null, 4],
]);
const value = parsed.files.find((file) => file.path === 'src/value.ts');
assert.equal(value.exports[0].name, 'value');
const contracts = parsed.files.find((file) => file.path === 'src/contracts.ts').function_contracts;
const loadContract = contracts.find((item) => item.exported_as === 'load');
assert.equal(loadContract.kind, 'FunctionDeclaration');
assert.equal(loadContract.async, true);
assert.deepEqual(loadContract.parameters.map((item) => [item.name, item.optional, item.type_annotation]), [
  ['id', false, 'string'], ['options', true, '{ cache: boolean }'],
]);
assert.equal(loadContract.return_type_annotation, 'Promise<Result>');
const transformContract = contracts.find((item) => item.exported_as === 'transform');
assert.equal(transformContract.parameters[1].has_default, true);
assert.equal(transformContract.parameters[1].type_annotation, null);
assert.equal(transformContract.return_type_annotation, 'string');
const helperContract = contracts.find((item) => item.exported_as === 'publicHelper');
assert.equal(helperContract.symbol, 'helper');
assert.equal(helperContract.parameters[0].type_annotation, 'Payload');
const defaultContract = contracts.find((item) => item.exported_as === 'default');
assert.equal(defaultContract.symbol, 'default');
assert.equal(defaultContract.return_type_annotation, 'Promise<Response>');
const combineContract = contracts.find((item) => item.exported_as === 'combine');
assert.equal(combineContract.parameters[0].rest, true);
assert.equal(combineContract.parameters[0].type_annotation, 'string[]');
assert.ok(contracts.every((item) => item.evidence.definition.path === 'src/contracts.ts' && item.evidence.export.path === 'src/contracts.ts'));
assert.doesNotMatch(JSON.stringify(contracts), /body-only|9137|hidden-default/);
const commonjsContracts = parsed.files.find((file) => file.path === 'src/contracts.cjs').function_contracts;
assert.deepEqual(commonjsContracts.map((item) => item.exported_as).sort(), ['convert', 'default', 'named']);
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
