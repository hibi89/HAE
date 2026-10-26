'use strict';

let babelParser;
try {
  babelParser = require('@babel/parser');
} catch (error) {
  process.stderr.write(
    'REA_APP parser unavailable: install the pinned @babel/parser dependency with npm install.\n',
  );
  process.exit(3);
}

function lineOf(node) {
  return node && node.loc && node.loc.start ? node.loc.start.line : 1;
}

function nodeName(node) {
  if (!node) return null;
  if (node.type === 'Identifier') return node.name;
  if (node.type === 'StringLiteral') return node.value;
  if (node.type === 'PrivateName') return node.id && node.id.name;
  return null;
}

function namesFromPattern(pattern, importedName) {
  if (!pattern) return [];
  if (pattern.type === 'Identifier') return [{ local: pattern.name, imported: importedName }];
  if (pattern.type === 'ObjectPattern') {
    return pattern.properties
      .filter((property) => property.type === 'ObjectProperty')
      .map((property) => ({
        local: nodeName(property.value) || property.value.name || null,
        imported: nodeName(property.key),
      }))
      .filter((binding) => binding.local && binding.imported);
  }
  return [];
}

function configValue(node) {
  if (!node) return undefined;
  if (node.type === 'StringLiteral' || node.type === 'BooleanLiteral' || node.type === 'NumericLiteral') return node.value;
  if (node.type === 'NullLiteral') return null;
  if (node.type === 'ArrayExpression') return node.elements.map(configValue);
  if (node.type === 'ObjectExpression') {
    const value = {};
    for (const property of node.properties) {
      if (property.type !== 'ObjectProperty' }¸Ó[h‘éì¶»§q«^uember) {
          exports.push({ name: member, source_name: member, kind: 'commonjs_export', line: lineOf(node) });
        } else if (objectName === 'module' && member === 'exports') {
          exports.push({ name: 'default', source_name: 'default', kind: 'commonjs_export', line: lineOf(node) });
        } else if (
          left.object && left.object.type === 'MemberExpression' &&
          nodeName(left.object.object) === 'module' && nodeName(left.object.property) === 'exports' && member
        ) {
          exports.push({ name: member, source_name: member, kind: 'commonjs_export', line: lineOf(node) });
        }
      }
    }

    for (const key of Object.keys(node)) {
      if (["loc", "start", "end", "extra", "comments", "tokens", "errors", "leadingComments", "trailingComments", "innerComments"].includes(key)) continue;
      const value = node[key];
      if (Array.isArray(value)) {
        for (const child of value) if (child && typeof child.type === 'string') visit(child, node, caller);
      } else if (value && typeof value.type === 'string') {
        visit(value, node, caller);
      }
    }
  }
  visit(ast.program);

  function collectValueFlows(scopeRoot, scopeParent, isModule = false) {
    const declarations = [];
    const aliases = [];
    const callResults = [];
    const callArguments = [];
    const returns = [];
    const writes = new Set();
    const nestedFunctions = [];
    const scope = isModule ? '<module>' : functionName(scopeRoot, scopeParent) || '<anonymous>';
    const body = isModule ? scopeRoot : scopeRoot.body;

    if (!isModule) {
      for (const parameter of scopeRoot.params || []) {
        if (parameter && parameter.type === 'Identifier') {
          declarations.push({ name: parameter.name, kind: 'parameter', line: lineOf(parameter) });
        }
      }
    }

    function walk(node, parent = null) {
      if (!node || typeof node.type !== 'string') return;
      if (node !== body && FUNCTION_TYPES.has(node.type)) {
        nestedFunctions.push({ node, parent });
        return;
      }

      if (node.type === 'VariableDeclarator' && node.id && node.id.type === 'Identifier') {
        declarations.push({ name: node.id.name, kind: 'local', line: lineOf(node.id), init: node.init });
        if (node.init && node.init.type === 'Identifier') {
          aliases.push({ from: node.init.name, to: node.id.name, line: lineOf(node.init) });
        } else if (node.init && node.init.type === 'CallExpression') {
          const callee = simpleCalleeName(node.init.callee);
          if (callee) callResults.push({ callee, to: node.id.name, line: lineOf(node.init) });
        }
      } else if (node.type === 'AssignmentExpression' && node.left && node.left.type === 'Identifier') {
        writes.add(node.left.name);
      } else if (node.type === 'UpdateExpression' && node.argument && node.argument.type === 'Identifier') {
        writes.add(node.argument.name);
      }

      if (node.type === 'CallExpression') {
        const callee = simpleCalleeName(node.callee);
        node.arguments.forEach((argument, argumentIndex) => {
          if (argument && argument.type === 'Identifier') {
            callArguments.push({ from: argument.name, callee, argument_index: argumentIndex, line: lineOf(argument), call_line: lineOf(node) });
          }
        });
      } else if (node.type === 'ReturnStatement' && node.argument && node.argument.type === 'Identifier') {
        returns.push({ from: node.argument.name, line: lineOf(node.argument), return_line: lineOf(node) });
      }

      for (const key of Object.keys(node)) {
        if (["loc", "start", "end", "extra", "comments", "tokens", "errors", "leadingComments", "trailingComments", "innerComments"].includes(key)) continue;
        const value = node[key];
        if (Array.isArray(value)) {
          for (const child of value) if (child && typeof child.type === 'string') walk(child, node);
        } else if (value && typeof value.type === 'string') {
          walk(value, node);
        }
      }
    }

    walk(body);
    const declarationCounts = new Map();
    for (const declaration of declarations) {
      declarationCounts.set(declaration.name, (declarationCounts.get(declaration.name) || 0) + 1);
    }
    const eligible = new Map(
      declarations
        .filter((declaration) => declarationCounts.get(declaration.name) === 1 && !writes.has(declaration.name))
        .map((declaration) => [declaration.name, declaration]),
    );
    const evidence = (line) => ({ path: file.path, line });

    for (const alias of aliases) {
      const source = eligible.get(alias.from);
      const target = eligible.get(alias.to);
      if (!source || !target) continue;
      valueFlows.push({
        scope,
        kind: 'alias',
        from_symbol: alias.from,
        to_symbol: alias.to,
        evidence: {
          source_binding: evidence(source.line),
          source_reference: evidence(alias.line),
          target_binding: evidence(target.line),
        },
      });
    }
    for (const callResult of callResults) {
      const target = eligible.get(callResult.to);
      if (!target) continue;
      valueFlows.push({
        scope,
        kind: 'call_result',
        from_callee: callResult.callee,
        to_symbol: callResult.to,
        evidence: { producer: evidence(callResult.line), target_binding: evidence(target.line) },
      });
    }
    for (const callArgument of callArguments) {
      const source = eligible.get(callArgument.from);
      if (!source) continue;
      valueFlows.push({
        scope,
        kind: 'call_argument',
        from_symbol: callArgument.from,
        to_callee: callArgument.callee,
        argument_index: callArgument.argument_index,
        evidence: {
          source_binding: evidence(source.line),
          source_use: evidence(callArgument.line),
          call_site: evidence(callArgument.call_line),
        },
      });
    }
    for (const returned of returns) {
      const source = eligible.get(returned.from);
      if (!source) continue;
      valueFlows.push({
        scope,
        kind: 'return',
        from_symbol: returned.from,
        evidence: {
          source_binding: evidence(source.line),
          source_use: evidence(returned.line),
          return_site: evidence(returned.return_line),
        },
      });
    }
    return nestedFunctions;
  }

  const pendingScopes = [{ node: ast.program, parent: null, isModule: true }];
  while (pendingScopes.length) {
    const current = pendingScopes.pop();
    const nested = collectValueFlows(current.node, current.parent, current.isModule);
    for (const child of nested) pendingScopes.push({ ...child, isModule: false });
  }

  const parseErrors = (ast.errors || []).map((error) => ({
    line: error.loc && error.loc.line ? error.loc.line : 1,
    message: error.message,
  }));
  return { path: file.path, parse_errors: parseErrors, edges, bindings, exports, calls, value_flows: valueFlows };
}

function parseTsConfig(file) {
  try {
    const expression = babelParser.parseExpression(`(${file.content})`, {
      sourceType: 'script',
      plugins: ['typescript'],
    });
    const config = configValue(expression);
    const options = config && config.compilerOptions && typeof config.compilerOptions === 'object'
      ? config.compilerOptions
      : {};
    return {
      path: file.path,
      parse_error: null,
      base_url: typeof options.baseUrl === 'string' ? options.baseUrl : null,
      paths: options.paths && typeof options.paths === 'object' ? options.paths : {},
    };
  } catch (error) {
    return { path: file.path, parse_error: error.message, base_url: null, paths: {} };
  }
}

try {
  const request = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
  if (!request || !Array.isArray(request.files)) throw new Error('input must contain a files array');
  const sourceFiles = request.files.filter((file) => /\.(?:[cm]?[jt]sx?)$/i.test(file.path));
  const configFiles = request.files.filter((file) => /(?:^|\/)tsconfig(?:\.[^/]+)?\.json$/i.test(file.path));
  process.stdout.write(JSON.stringify({
    parser: `@babel/parser@${require('@babel/parser/package.json').version}`,
    files: sourceFiles.map(parseSource),
    tsconfigs: configFiles.map(parseTsConfig),
  }));
} catch (error) {
  process.stderr.write(`REA_APP parser failed: ${error && error.message ? error.message : String(error)}\n`);
  process.exitCode = 2;
}
