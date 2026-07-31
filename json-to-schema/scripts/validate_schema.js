#!/usr/bin/env node
/**
 * validate_schema.js
 *
 * Usage:
 *   node validate_schema.js <schema.json>
 *   node validate_schema.js <schema.json> <sample.json>
 *
 * 1. Verifies the schema file parses as JSON and has the expected draft-07
 *    top-level shape ($schema, type, properties).
 * 2. If a sample path is also given, validates the sample against the schema
 *    using Ajv (when available) or a lightweight built-in walker as fallback.
 *
 * Exits 0 on success, 1 on any failure. Prints a one-line OK summary on success
 * and a focused error on failure — no noisy traces.
 */

'use strict';

const fs = require('fs');
const path = require('path');

function die(msg) {
  console.error(`validate_schema: ${msg}`);
  process.exit(1);
}

function readJson(p) {
  let raw;
  try {
    raw = fs.readFileSync(p, 'utf8');
  } catch (e) {
    die(`cannot read ${p}: ${e.message}`);
  }
  // Strip BOM if present.
  if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);
  try {
    return JSON.parse(raw);
  } catch (e) {
    die(`${p} is not valid JSON: ${e.message}`);
  }
}

function checkSchemaShape(schema, p) {
  if (typeof schema !== 'object' || schema === null || Array.isArray(schema)) {
    die(`${p} top-level must be a JSON object`);
  }
  if (schema.$schema && !String(schema.$schema).includes('draft-07')) {
    console.warn(`validate_schema: note — $schema is "${schema.$schema}", this helper targets draft-07`);
  }
  if (!schema.type && !schema.$ref && !schema.oneOf && !schema.anyOf) {
    die(`${p} is missing a top-level "type" (or $ref/oneOf/anyOf)`);
  }
}

// Minimal fallback validator: walks the sample and checks each value's JS
// runtime type against the matching schema node's "type". Resolves $ref against
// the schema's own definitions. Good enough to catch walker bugs like "wrote
// integer where the sample has a string". Not a conformant draft-07 validator.
function jsTypeOf(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  const t = typeof v;
  if (t === 'number') return Number.isInteger(v) ? 'integer' : 'number';
  return t; // string | boolean | object
}

function resolveRef(schema, ref) {
  if (!ref.startsWith('#/')) return null;
  const parts = ref.slice(2).split('/');
  let node = schema;
  for (const part of parts) {
    if (node == null) return null;
    node = node[part];
  }
  return node;
}

function fallbackValidate(rootSchema, node, sample, pathStr, errors) {
  if (!node) return;
  if (node.$ref) {
    const resolved = resolveRef(rootSchema, node.$ref);
    if (!resolved) {
      errors.push(`${pathStr}: unresolved $ref ${node.$ref}`);
      return;
    }
    return fallbackValidate(rootSchema, resolved, sample, pathStr, errors);
  }
  const expected = node.type;
  if (expected) {
    const actual = jsTypeOf(sample);
    const ok =
      expected === actual ||
      (expected === 'number' && actual === 'integer') ||
      (Array.isArray(expected) && expected.includes(actual));
    if (!ok) {
      errors.push(`${pathStr}: expected ${JSON.stringify(expected)}, got ${actual}`);
      return;
    }
  }
  if (node.type === 'object' && sample && typeof sample === 'object' && !Array.isArray(sample)) {
    const props = node.properties || {};
    for (const [k, childSchema] of Object.entries(props)) {
      if (k in sample) {
        fallbackValidate(rootSchema, childSchema, sample[k], `${pathStr}.${k}`, errors);
      }
    }
  } else if (node.type === 'array' && Array.isArray(sample) && node.items) {
    sample.forEach((el, i) => {
      fallbackValidate(rootSchema, node.items, el, `${pathStr}[${i}]`, errors);
    });
  }
}

function main() {
  const [, , schemaPath, samplePath] = process.argv;
  if (!schemaPath) {
    die('usage: node validate_schema.js <schema.json> [sample.json]');
  }

  const schema = readJson(schemaPath);
  checkSchemaShape(schema, schemaPath);
  console.log(`OK: ${path.basename(schemaPath)} parses and looks like a JSON Schema`);

  if (!samplePath) return;

  const sample = readJson(samplePath);

  // Prefer Ajv if available — it's the real deal. Otherwise fall back.
  let ajv = null;
  try {
    // eslint-disable-next-line global-require
    const Ajv = require('ajv');
    ajv = new Ajv({ strict: false, allErrors: true });
  } catch (_) {
    // Ajv not installed — fall through to built-in walker.
  }

  if (ajv) {
    const validate = ajv.compile(schema);
    if (validate(sample)) {
      console.log(`OK: ${path.basename(samplePath)} validates against the schema (ajv)`);
      return;
    }
    console.error(`FAIL: ${path.basename(samplePath)} does not validate against the schema:`);
    for (const err of validate.errors || []) {
      console.error(`  ${err.instancePath || '/'} ${err.message}`);
    }
    process.exit(1);
  } else {
    const errors = [];
    fallbackValidate(schema, schema, sample, '$', errors);
    if (errors.length === 0) {
      console.log(`OK: ${path.basename(samplePath)} matches the schema shape (built-in walker; install ajv for full validation)`);
      return;
    }
    console.error(`FAIL: schema/sample mismatch (built-in walker):`);
    for (const e of errors) console.error(`  ${e}`);
    process.exit(1);
  }
}

main();
