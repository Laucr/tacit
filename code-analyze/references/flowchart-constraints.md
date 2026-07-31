# Flowchart Constraints

## 1. Syntax & Naming
* **Node IDs:** Use descriptive, camelCase IDs (e.g., `checkAuth` not `A`).
* **Direction:** Use `TD` (Top-Down) unless the flow is strictly sequential.

## 2. Shape Conventions
Use the following Mermaid syntax for specific logic types:
* **Terminal:** `([Start / End])` (Rounded)
* **Process:** `[Action / Assignment]` (Rectangle)
* **Decision:** `{Condition?}` (Diamond) — *Use for if/else and switches.*
* **Input/Output:** `[/Data I/O/]` (Parallelogram)

## 3. Content Escaping
To prevent rendering errors, strictly adhere to these rules:
* **Quotes:** Always enclose node labels in double quotes. `id["Label Content"]`.
* **Entities:** Convert special chars inside the label:
    * `<` $\rightarrow$ `&lt;`
    * `>` $\rightarrow$ `&gt;`
    * `"` $\rightarrow$ `#quot;`

## 4. Typography & Styling
Apply formatting based on the code element type:

### Text Formatting
* **Variables/Constants:** `<b>variable_name</b>`
* **Functions/Methods:** `<i>func_name()</i>`
* **Logical/Abstract Nodes:** `&lt;ConceptName&gt;`

### Node Coloring (External Calls)
For any node involving an External Service (API, DB, RPC), you must apply a highlight style.
* **Method:** Append a style line at the end of the chart or use a class.
* **Code Example:** `style nodeID fill:#f96,stroke:#333,stroke-width:2px`

## 5. Example Structure
```mermaid
graph TD
    start([Start]) --> check{Check Config}
    check -- Yes --> run[Run <i>process()</i>]
    check -- No --> err[Log <b>ERROR_CONST</b>]
    run --> db[Query DB]
    style db fill:#f96
```