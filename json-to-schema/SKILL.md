---
name: json-to-schema
description: Convert a sample JSON file into a JSON Schema (draft-07) definition file. Use this skill whenever the user asks to "derive a schema", "generate a schema", "get the data schema of", "turn this JSON into a schema", or "save/write the schema of" a `.json` sample — even if they don't use the words "JSON Schema" explicitly. Also applies when the user shows a payload and asks "what's the shape of this" in a context where a reusable schema file would help (API contracts, validation, documentation).
---

# JSON → JSON Schema

Turn a sample `.json` file into a draft-07 JSON Schema file that another developer can use for validation, documentation, or code generation.

The user usually already has the sample file on disk and wants the schema written to a sibling path (commonly `<name>_schema.json`). They rarely want a verbose walkthrough — produce the schema, validate it parses, save it.

## Why draft-07 and why factored

- **Draft-07** is the most broadly supported JSON Schema dialect (Ajv, python-jsonschema, IntelliJ, VS Code all understand it without configuration). Unless the user specifies another dialect, default to draft-07.
- **Factor shared sub-structures into `definitions` + `$ref`.** If two sibling objects have identical shape (e.g. `static_info` and `badcase_info` with the same fields), duplicating them is a maintenance hazard — a change in one place is easy to miss in the other. One `$ref` also reads faster for humans skimming the schema.
- **Annotate, don't just type.** `"type": "string"` is almost never enough: is it HTML? A datetime? A signed URL? A map of option-letter → choice text? These hints live in `description` so consumers of the schema understand *what kind* of string they're looking at.

## Workflow

### 1. Read and parse the sample

Load the file and parse it. If it fails to parse, report the parse error location and stop — don't guess at broken JSON.

### 2. Walk the structure and infer types

Recurse through the object. At each leaf:

| JS runtime type | Schema `type` |
|-|-|
| `string` | `string` |
| `number` (integer) | `integer` |
| `number` (fractional) | `number` |
| `boolean` | `boolean` |
| `null` | `null` |
| array | `array` |
| plain object | `object` |

For arrays: if the array is non-empty and all elements share a shape, emit `"items": { ... }` describing that shape. If the array is empty, emit just `"type": "array"` — don't invent item types you can't confirm from the sample.

For objects: walk each key and emit a `properties` entry. Empty objects get `"type": "object"` with no properties.

### 3. Factor shared sub-object shapes

After the first walk, look for objects with identical key sets *and* identical child types. If two or more share the shape, lift it into `definitions` (under a meaningful name — `TaskInfo`, `UserSummary`, not `Shared1`) and replace both occurrences with `{ "$ref": "#/definitions/<Name>" }`.

Don't over-factor. Two fields that happen to both be strings are not "the same type" — only pull objects with non-trivial structural overlap (3+ fields, all matching).

### 4. Add semantic descriptions

For each field where the string content has a recognizable shape, add a `description`:

- Looks like `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS` → `"description": "datetime, format: YYYY-MM-DD HH:MM:SS"`
- Contains `<p>`, `<div>`, `<br>` etc. → `"description": "HTML"`
- Contains `q-sign-algorithm=`, signed query params, or is clearly a pre-signed URL → `"description": "signed URL to ..."`
- Object whose keys are a small enumerated set (e.g. single letters `A`/`B`/`C`/`D`) and values share a type → model as `"additionalProperties": { ... }` with `"description": "map of <key> -> <value>"` rather than enumerating each letter as a fixed property.

Don't invent descriptions for generic fields like `id`, `name`, `count` — those speak for themselves.

### 5. Assemble the schema document

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "<PascalCaseName>",
  "type": "object",
  "properties": { ... },
  "definitions": { ... }
}
```

- `title` = PascalCase of the filename (without `_schema`/`.json`), e.g. `bdtk_static_info.json` → `BdtkStaticInfo`.
- **Do not emit a `required` array from a single sample.** One sample cannot prove a field is required — emitting `required` based on one example is lying to downstream consumers. Only add `required` if the user explicitly asks, or if they provide multiple samples and every sample contains the field.
- Omit `definitions` entirely if you didn't factor anything.

### 6. Validate and save

Validate the schema document parses as JSON. Use the bundled helper:

```bash
node scripts/validate_schema.js <path-to-schema.json>
```

Optionally, also validate the original sample against the schema (catches logic errors in the walker). The same script does this if you pass the sample as a second arg:

```bash
node scripts/validate_schema.js <schema.json> <sample.json>
```

Save to the path the user specified (`save this over X` means overwrite X). If they didn't specify, default to `<sample_basename>_schema.json` alongside the sample.

## Example

**Input** (`bdtk_static_info.json`):
```json
{
  "item_id": "020c9e5e...",
  "assign_time": "2026-04-08 20:22:08",
  "question": "<p>刚体是理想化模型</p>",
  "static_info": {
    "task_id": 1775633820,
    "data_source": "spider"
  },
  "badcase_info": {
    "task_id": 1775633820,
    "data_source": "spider"
  },
  "choices": { "A": "<p>正确</p>", "B": "<p>错误</p>" }
}
```

**Output** (`bdtk_static_info_schema.json`):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "BdtkStaticInfo",
  "type": "object",
  "properties": {
    "item_id": { "type": "string" },
    "assign_time": {
      "type": "string",
      "description": "datetime, format: YYYY-MM-DD HH:MM:SS"
    },
    "question": { "type": "string", "description": "HTML" },
    "static_info": { "$ref": "#/definitions/TaskInfo" },
    "badcase_info": { "$ref": "#/definitions/TaskInfo" },
    "choices": {
      "type": "object",
      "description": "map of option letter -> HTML string",
      "additionalProperties": { "type": "string" }
    }
  },
  "definitions": {
    "TaskInfo": {
      "type": "object",
      "properties": {
        "task_id": { "type": "integer" },
        "data_source": { "type": "string" }
      }
    }
  }
}
```

Note how `static_info` and `badcase_info` share `TaskInfo`, `assign_time` is annotated as a datetime, `question` as HTML, and `choices` is modeled as a map rather than enumerating `A` and `B` as fixed properties.

## When the sample is ambiguous

If the sample contains many empty arrays or empty objects, their element/property types are genuinely unknown. Don't fabricate. State the limitation to the user in one line (e.g. "3 arrays were empty in the sample; their element types couldn't be inferred"). If they have a richer sample, run the skill again on that instead.
