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
      if (property.type !== 'ObjectProperty' || property.computed) continue;
      const key = nodeName(property.key);
      if (key !== null) value[key] = configValue(property.value);
    }
    return value;
  }
  return undefined;
}

function sourceString(node) {
  return node && node.type === 'StringLiteral' ? node.value : null;
}

function collectDeclarationExports(declaration, out) {
  if (!declaration) return;
  if (declaration.type === 'VariableDeclaration') {
    for (const item of declaration.declarations) {
      const names = namesFromPattern(item.id, '*').map((binding) => binding.local);
      for (const name of names) out.push({ name, source_name: name, kind: 'export', line: lineOf(declaration) });
    }
  } else if (declaration.id && declaration.id.name) {
    out.push({ name: declaration.id.name, source_name: declaration.id.name, kind: 'export', line: lineOf(declaration) });
  }
}

function functionName(node, parent) {
  if (node.type === 'FunctionDeclaration' && node.id) return node.id.name;
  if (["ClassMethod", "ClassPrivateMethod", "ObjectMethod"].includes(node.type)) return nodeName(node.key) || '<method>';
  if (["FunctionExpression", "ArrowFunctionExpression"].includes(node.type)) {
    if (parent && parent.type === 'VariableDeclarator') return nodeName(parent.id) || '<anonymous>';
    if (parent && parent.type === 'AssignmentExpression') return nodeName(parent.left) || '<anonymous>';
    if (parent && parent.type === 'ObjectProperty') return nodeName(parent.key) || '<anonymous>';
  }
  return null;
}

function parseSource(file) {
  const lower = file.path.toLowerCase();
  const isTypeScript = /\.(?:ts|tsx|mts|cts)$/.test(lower);
  const isTsx = lower.endsWith('.tsx');
  const plugins = ['decorators-legacy', 'importAttributes'];
  if (isTypeScript) plugins.push(['typescript', { isTSX: isTsx }]);
  if (isTsx || lower.endsWith('.jsx')) plugins.push('jsx');
  const edges = [];
  const bindings = [];
  const exports = [];
  const calls = [];
  let ast;

  try {
    ast = babelParser.parse(file.content, {
      sourceType: 'unambiguous',
      sourceFilename: file.path,
      errorRecovery: true,
      plugins,
    });
  } catch (error) {
    return {
      path: file.path,
      parse_errors: [{ line: error.loc && error.loc.line ? error.loc.line : 1, message: error.message }],
      edges,
      bindings,
      exports,
      calls,
    };
  }

  function addEdge(kind, specifier, node, importBindings = []) {
    if (typeof specifier !== 'string') return;
    const edgeIndex = edges.length;
    edges.push({ kind, specifier, line: lineOf(node) });
    for (const binding of importBindings) bindings.push({ ...binding, edge_index: edgeIndex, kind });
  }

  for (const statement of ast.program.body) {
    if (statement.type === 'ImportDeclaration') {
      const foundBindings = [];
      for (const specifier of statement.specifiers) {
        if (specifier.type === 'ImportDefaultSpecifier') foundBindings.push({ local: specifier.local.name, imported: 'default' });
        else if (specifier.type === 'ImportNamespaceSpecifier') foundBindings.push({ local: specifier.local.name, imported: '*' });
        else foundBindings.push({ local: specifier.local.name, imported: nodeName(specifier.imported) || specifier.imported.value });
      }
      addEdge(statement.importKind === 'type' ? 'type_import' : 'import', sourceString(statement.source), statement, foundBindings);
    } else if (statement.type === 'ExportNamedDeclaration') {
      if (statement.source) addEdge('reexport', sourceString(statement.source), statement);
      if (statement.specifiers.length) {
        for (const specifier of statement.specifiers) {
          exports.push({
            name: nodeName(specifier.exported),
            source_name: nodeName(specifier.local),
            kind: statement.source ? 'reexport' : 'export',
            line: lineOf(statement),
          });
        }
      } else {
        collectDeclarationExports(statement.declaration, exports);
      }
    } else if (statement.type === 'ExportAllDeclaration') {
      addEdge('reexport', sourceString(statement.source), statement);
      exports.push({ name: nodeName(statement.exported) || '*', kind: 'reexport_all', line: lineOf(statement) });
    } else if (statement.type === 'ExportDefaultDeclaration') {
      exports.push({ name: 'default', source_name: 'default', kind: 'default_export', line: lineOf(statement) });
    } else if (statement.type === 'TSExportAssignment') {
      exports.push({ name: 'default', source_name: 'default', kind: 'export_assignment', line: lineOf(statement) });
    } else if (statement.type === 'TSImportEqualsDeclaration') {
      const reference = statement.moduleReference;
      if (reference && reference.expression) addEdge('require', sourceString(reference.expression), statement, [{ local: statement.id.name, imported: '*' }]);
    }
  }

  function visit(node, parent = null, currentCaller = '<module>') {
    if (!node || typeof node !== 'object') return;
    const namedFunction = functionName(node, parent);
    const caller = namedFunction || currentCaller;

    if (node.type === 'CallExpression') {
      const callee = node.callee;
      const isRequire = callee && callee.type === 'Identifier' && callee.name === 'require';
      const isDynamicImport = (callee && callee.type === 'Import') || node.type === 'ImportExpression';
      if (isRequire && node.arguments.length && node.arguments[0].type === 'StringLiteral') {
        const foundBindings = parent && parent.type === 'VariableDeclarator'
          ? namesFromPattern(parent.id, '*')
          : [];
        addEdge('require', sourceString(node.arguments[0]), node, foundBindings);
      } else if (isDynamicImport && node.arguments.length && node.arguments[0].type === 'StringLiteral') {
        addEdge('dynamic_import', sourceString(node.arguments[0]), node);
      }
      calls.push({
        callee: file.content.slice(callee.start, callee.end).slice(0, 160),
        caller,
        line: lineOf(node),
      });
    } else if (node.type === 'ImportExpression' && node.source && node.source.type === 'StringLiteral') {
      addEdge('dynamic_import', sourceString(node.source), node);
    } else if (node.type === 'TSImportType' && node.argument && node.argument.type === 'TSLiteralType') {
      addEdge('type_import', sourceString(node.argument.literal), node);
    }

    if (node.type === 'AssignmentExpression' && node.operator === '=') {
      const left = node.left;
      if (left && left.type === 'MemberExpression') {
        const objectName = nodeName(left.object);
        const member = left.computed ? nodeName(left.property) : nodeName(left.property);
        if (objectName === 'exports' && member) {
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

  const parseErrors = (ast.errors || []).map((error) => ({
    line: error.loc && error.loc.line ? error.loc.line : 1,
    message: error.message,
  }));
  return { path: file.path, parse_errors: parseErrors, edges, bindings, exports, calls };
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
