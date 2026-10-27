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

function bindingNames(pattern, names = []) {
  if (!pattern) return names;
  if (pattern.type === 'Identifier') names.push(pattern.name);
  else if (pattern.type === 'RestElement') bindingNames(pattern.argument, names);
  else if (pattern.type === 'AssignmentPattern') bindingNames(pattern.left, names);
  else if (pattern.type === 'TSParameterProperty') bindingNames(pattern.parameter, names);
  else if (pattern.type === 'ObjectPattern') {
    for (const property of pattern.properties) {
      if (property.type === 'RestElement') bindingNames(property.argument, names);
      else bindingNames(property.value, names);
    }
  } else if (pattern.type === 'ArrayPattern') {
    for (const element of pattern.elements) bindingNames(element, names);
  }
  return names;
}

function collectFileAccessConflicts(root) {
  const conflicts = new Set();
  function walk(node) {
    if (!node || typeof node.type !== 'string') return;
    if (node.type === 'VariableDeclarator') {
      const isRequire = node.init && node.init.type === 'CallExpression' &&
        node.init.callee && node.init.callee.type === 'Identifier' && node.init.callee.name === 'require';
      if (!isRequire) for (const name of bindingNames(node.id)) conflicts.add(name);
    } else if (FUNCTION_TYPES.has(node.type)) {
      for (const parameter of node.params || []) {
        for (const name of bindingNames(parameter)) conflicts.add(name);
      }
      if (node.id && node.id.name) conflicts.add(node.id.name);
    } else if ((node.type === 'ClassDeclaration' || node.type === 'ClassExpression') && node.id) {
      conflicts.add(node.id.name);
    } else if (node.type === 'CatchClause' && node.param) {
      for (const name of bindingNames(node.param)) conflicts.add(name);
    }

    if (node.type === 'AssignmentExpression' && node.left && node.left.type === 'Identifier') {
      conflicts.add(node.left.name);
    } else if (node.type === 'UpdateExpression' && node.argument && node.argument.type === 'Identifier') {
      conflicts.add(node.argument.name);
    }

    for (const key of Object.keys(node)) {
      if (["loc", "start", "end", "extra", "comments", "tokens", "errors", "leadingComments", "trailingComments", "innerComments"].includes(key)) continue;
      const value = node[key];
      if (Array.isArray(value)) {
        for (const child of value) if (child && typeof child.type === 'string') walk(child);
      } else if (value && typeof value.type === 'string') {
        walk(value);
      }
    }
  }
  walk(root);
  return conflicts;
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

function staticModuleSpecifier(node) {
  if (node && node.type === 'StringLiteral') return node.value;
  if (node && node.type === 'TemplateLiteral' && node.expressions.length === 0) {
    return node.quasis[0] && node.quasis[0].value.cooked;
  }
  return null;
}

const FILE_ACCESS_OPERATIONS = new Map([
  ['readFile', 'read'], ['readFileSync', 'read'],
  ['createReadStream', 'read_stream'],
  ['writeFile', 'write'], ['writeFileSync', 'write'],
  ['createWriteStream', 'write_stream'],
  ['appendFile', 'append'], ['appendFileSync', 'append'],
  ['unlink', 'delete'], ['unlinkSync', 'delete'],
  ['rm', 'delete'], ['rmSync', 'delete'],
  ['mkdir', 'create_directory'], ['mkdirSync', 'create_directory'],
  ['readdir', 'list_directory'], ['readdirSync', 'list_directory'],
]);

function fileSystemBinding(localName, bindings, edges, conflicts) {
  if (conflicts.has(localName)) return null;
  const matches = bindings.filter((binding) => binding.local === localName);
  if (matches.length !== 1) return null;
  const binding = matches[0];
  if (binding.kind === 'type_import') return null;
  const edge = edges[binding.edge_index];
  const specifier = edge && edge.specifier;
  if (!['fs', 'node:fs', 'fs/promises', 'node:fs/promises'].includes(specifier)) return null;
  return {
    module: specifier.endsWith('fs/promises') ? 'fs/promises' : 'fs',
    imported: binding.imported,
    namespace: ['*', 'default'].includes(binding.imported),
  };
}

function fileSystemModuleObject(node, bindings, edges, conflicts) {
  if (!node) return null;
  if (node.type === 'Identifier') return fileSystemBinding(node.name, bindings, edges, conflicts);
  if (
    node.type === 'CallExpression' && node.callee && node.callee.type === 'Identifier' &&
    node.callee.name === 'require' && node.arguments.length && node.arguments[0].type === 'StringLiteral'
  ) {
    const specifier = sourceString(node.arguments[0]);
    if (!['fs', 'node:fs', 'fs/promises', 'node:fs/promises'].includes(specifier)) return null;
    return {
      module: specifier.endsWith('fs/promises') ? 'fs/promises' : 'fs',
      imported: '*',
      namespace: true,
    };
  }
  return null;
}

function fileSystemOperation(method, moduleName) {
  if (!FILE_ACCESS_OPERATIONS.has(method)) return null;
  if (moduleName === 'fs/promises' && (method.endsWith('Sync') || method.startsWith('create'))) return null;
  return FILE_ACCESS_OPERATIONS.get(method);
}

function fileAccessOperation(callee, bindings, edges, conflicts) {
  if (!callee) return null;
  if (callee.type === 'Identifier') {
    const binding = fileSystemBinding(callee.name, bindings, edges, conflicts);
    if (!binding || binding.namespace) return null;
    return fileSystemOperation(binding.imported, binding.module);
  }
  if (callee.type !== 'MemberExpression') return null;
  const method = nodeName(callee.property);
  if (!FILE_ACCESS_OPERATIONS.has(method)) return null;

  let moduleObject = fileSystemModuleObject(callee.object, bindings, edges, conflicts);
  if (callee.object && callee.object.type === 'MemberExpression' && nodeName(callee.object.property) === 'promises') {
    moduleObject = fileSystemModuleObject(callee.object.object, bindings, edges, conflicts);
    if (!moduleObject || moduleObject.module !== 'fs' || !moduleObject.namespace) return null;
    return fileSystemOperation(method, 'fs/promises');
  }
  if (!moduleObject) return null;
  if (moduleObject.module === 'fs/promises' && moduleObject.namespace) return fileSystemOperation(method, 'fs/promises');
  if (moduleObject.module === 'fs' && (moduleObject.namespace || moduleObject.imported === 'promises')) {
    return fileSystemOperation(method, moduleObject.imported === 'promises' ? 'fs/promises' : 'fs');
  }
  return null;
}

function filePathArgument(argument) {
  if (!argument || argument.type !== 'StringLiteral') return { path: null, path_kind: 'dynamic' };
  const raw = sourceString(argument);
  if (!raw || /[\u0000-\u001f\u007f]/.test(raw)) return { path: null, path_kind: 'unsafe_literal' };
  const normalized = raw.replace(/\\/g, '/');
  if (normalized.startsWith('/') || /^[A-Za-z]:($|\/)/.test(normalized) || /^[A-Za-z][A-Za-z0-9+.-]*:\/\//.test(normalized)) {
    return { path: null, path_kind: 'absolute_or_nonlocal_redacted' };
  }
  const segments = normalized.split('/').filter((segment) => segment && segment !== '.');
  const reduced = [];
  for (const segment of segments) {
    if (segment === '..') {
      if (!reduced.length) return { path: null, path_kind: 'parent_relative_redacted' };
      reduced.pop();
      continue;
    }
    const lowered = segment.toLowerCase();
    if (
      lowered === '.env' || lowered.startsWith('.env.') ||
      ['.pem', '.key', '.p12', '.pfx', '.keystore'].some((extension) => lowered.endsWith(extension)) ||
      ['secret', 'credential', 'private_key', 'token', 'password', 'api_key'].some((name) => lowered.includes(name))
    ) {
      return { path: null, path_kind: 'sensitive_path_redacted' };
    }
    reduced.push(segment);
  }
  const path = reduced.join('/') || '.';
  if (!/^[\p{L}\p{N} _./-]+$/u.test(path)) return { path: null, path_kind: 'unsafe_literal' };
  return { path, path_kind: 'relative_literal' };
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
  if (node.type === 'FunctionExpression' && node.id) return node.id.name;
  if (["ClassMethod", "ClassPrivateMethod", "ObjectMethod"].includes(node.type)) return nodeName(node.key) || '<method>';
  if (["FunctionExpression", "ArrowFunctionExpression"].includes(node.type)) {
    if (parent && parent.type === 'VariableDeclarator') return nodeName(parent.id) || '<anonymous>';
    if (parent && parent.type === 'AssignmentExpression') {
      return nodeName(parent.left) || (parent.left.type === 'MemberExpression' && !parent.left.computed
        ? nodeName(parent.left.property)
        : null) || '<anonymous>';
    }
    if (parent && parent.type === 'ObjectProperty') return nodeName(parent.key) || '<anonymous>';
  }
  return null;
}

const FUNCTION_TYPES = new Set([
  'FunctionDeclaration',
  'FunctionExpression',
  'ArrowFunctionExpression',
  'ObjectMethod',
  'ClassMethod',
  'ClassPrivateMethod',
]);

function simpleCalleeName(node) {
  if (!node) return null;
  if (node.type === 'Identifier') return node.name;
  if (node.type === 'MemberExpression' && !node.computed && node.property.type === 'Identifier') {
    return node.property.name;
  }
  return null;
}

function typeText(annotation, content) {
  if (!annotation || typeof annotation.start !== 'number' || typeof annotation.end !== 'number') return null;
  const text = content.slice(annotation.start, annotation.end).replace(/^\s*:\s*/, '').trim();
  return text && text.length <= 240 ? text : null;
}

function parameterContract(parameter, content) {
  let item = parameter;
  if (item && item.type === 'TSParameterProperty') item = item.parameter;
  let rest = false;
  let hasDefault = false;
  if (item && item.type === 'RestElement') {
    rest = true;
    item = item.argument;
  }
  if (item && item.type === 'AssignmentPattern') {
    hasDefault = true;
    item = item.left;
  }
  return {
    name: item && item.type === 'Identifier' ? item.name : null,
    pattern: item && item.type !== 'Identifier' ? item.type : null,
    optional: Boolean(item && item.optional),
    rest,
    has_default: hasDefault,
    type_annotation: typeText(item && item.typeAnnotation, content)
      || typeText(parameter && parameter.typeAnnotation, content),
  };
}

function exportedAssignmentName(left) {
  if (!left || left.type !== 'MemberExpression') return null;
  const objectName = nodeName(left.object);
  const member = nodeName(left.property);
  if (objectName === 'exports' && member) return member;
  if (objectName === 'module' && member === 'exports') return 'default';
  if (
    left.object && left.object.type === 'MemberExpression' &&
    nodeName(left.object.object) === 'module' &&
    nodeName(left.object.property) === 'exports' && member
  ) return member;
  return null;
}

function functionDefinition(node, parent) {
  if (parent && parent.type === 'ExportDefaultDeclaration') {
    return { symbol: node.id && node.id.name ? node.id.name : 'default', direct_export: 'default' };
  }
  if (node.type === 'FunctionDeclaration' && node.id) return { symbol: node.id.name };
  if (parent && parent.type === 'VariableDeclarator' && parent.id && parent.id.type === 'Identifier') {
    return { symbol: parent.id.name };
  }
  if (parent && parent.type === 'AssignmentExpression' && parent.right === node) {
    const symbol = exportedAssignmentName(parent.left);
    if (symbol) return { symbol, direct_export: symbol };
  }
  if (node.type === 'FunctionExpression' && node.id) return { symbol: node.id.name };
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
  const fileAccesses = [];
  const valueFlows = [];
  const functionNodes = [];
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
      file_accesses: fileAccesses,
      value_flows: valueFlows,
      function_contracts: [],
    };
  }

  const fileAccessConflicts = collectFileAccessConflicts(ast.program);

  function addEdge(kind, specifier, node, importBindings = []) {
    if (typeof specifier !== 'string' && kind !== 'dynamic_import') return;
    const edgeIndex = edges.length;
    edges.push({ kind, specifier: typeof specifier === 'string' ? specifier : null, line: lineOf(node) });
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
      const declaration = statement.declaration;
      const sourceName = declaration && declaration.id && declaration.id.name
        ? declaration.id.name
        : declaration && declaration.type === 'Identifier' ? declaration.name : 'default';
      exports.push({ name: 'default', source_name: sourceName, kind: 'default_export', line: lineOf(statement) });
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
    if (FUNCTION_TYPES.has(node.type) && !['ObjectMethod', 'ClassMethod', 'ClassPrivateMethod'].includes(node.type)) {
      const definition = functionDefinition(node, parent);
      if (definition) functionNodes.push({ node, ...definition });
    }

    if (node.type === 'CallExpression') {
      const callee = node.callee;
      const isRequire = callee && callee.type === 'Identifier' && callee.name === 'require';
      const isDynamicImport = (callee && callee.type === 'Import') || node.type === 'ImportExpression';
      if (isRequire && node.arguments.length && node.arguments[0].type === 'StringLiteral') {
        const foundBindings = parent && parent.type === 'VariableDeclarator'
          ? namesFromPattern(parent.id, '*')
          : [];
        addEdge('require', sourceString(node.arguments[0]), node, foundBindings);
      } else if (isDynamicImport && node.arguments.length) {
        addEdge('dynamic_import', staticModuleSpecifier(node.arguments[0]), node);
      }
      calls.push({
        callee: file.content.slice(callee.start, callee.end).slice(0, 160),
        caller,
        line: lineOf(node),
      });
      const operation = fileAccessOperation(callee, bindings, edges, fileAccessConflicts);
      if (operation) {
        const pathInfo = filePathArgument(node.arguments[0]);
        fileAccesses.push({
          operation,
          path: pathInfo.path,
          path_kind: pathInfo.path_kind,
          argument_index: 0,
          line: lineOf(node),
        });
      }
    } else if (node.type === 'ImportExpression' && node.source) {
      addEdge('dynamic_import', staticModuleSpecifier(node.source), node);
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

  const functionContracts = [];
  for (const exported of exports) {
    if (!['export', 'default_export', 'commonjs_export'].includes(exported.kind)) continue;
    const sourceName = exported.source_name || exported.name;
    const candidates = functionNodes.filter((item) =>
      item.symbol === sourceName || item.symbol === exported.name || item.direct_export === exported.name,
    );
    if (candidates.length !== 1) continue;
    const item = candidates[0];
    const node = item.node;
    functionContracts.push({
      symbol: item.symbol,
      exported_as: exported.name,
      kind: node.type,
      async: Boolean(node.async),
      generator: Boolean(node.generator),
      parameters: (node.params || []).map((parameter) => parameterContract(parameter, file.content)),
      return_type_annotation: typeText(node.returnType, file.content),
      evidence: {
        definition: { path: file.path, line: lineOf(node) },
        export: { path: file.path, line: exported.line, name: exported.name },
      },
    });
  }

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
  return {
    path: file.path,
    parse_errors: parseErrors,
    edges,
    bindings,
    exports,
    calls,
    file_accesses: fileAccesses,
    value_flows: valueFlows,
    function_contracts: functionContracts,
  };
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

