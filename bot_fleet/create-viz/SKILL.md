---
name: Create viz
description: >-
  Use when turning query results or a DataFrame into a chart, picking a chart
  type for a trend or comparison, generating a plot for a report or
  presentation, or needing an interactive chart with hover and zoom
  (matplotlib/seaborn/plotly).
---
# Create viz — publication-quality charts

If a data warehouse connector is available, use it; otherwise work from pasted/CSV data or prior analysis.

Create publication-quality data visualizations using Python. Generates charts from data with best practices for clarity, accuracy, and design.

## Usage

```
/create-viz <data source> [chart type] [additional instructions]
```

## Workflow

### 1. Understand the Request

Determine:

- **Data source**: Query results, pasted data, CSV/Excel file, or data to be queried
- **Chart type**: Explicitly requested or needs to be recommended
- **Purpose**: Exploration, presentation, report, dashboard component
- **Audience**: Technical team, executives, external stakeholders

### 2. Get the Data

**If data warehouse is connected and data needs querying:**
1. Write and execute the query
2. Load results into a pandas DataFrame

**If data is pasted or uploaded:**
1. Parse the data into a pandas DataFrame
2. Clean and prepare as needed (type conversions, null handling)

**If data is from a previous analysis in the conversation:**
1. Reference the existing data

### 3. Select Chart Type

If the user didn't specify a chart type, recommend one based on the data and question:

| Data Relationship | Recommended Chart |
|---|---|
| Trend over time | Line chart |
| Comparison across categories | Bar chart (horizontal if many categories) |
| Part-to-whole composition | Stacked bar or area chart (avoid pie charts unless <6 categories) |
| Distribution of values | Histogram or box plot |
| Correlation between two variables | Scatter plot |
| Two-variable comparison over time | Dual-axis line or grouped bar |
| Geographic data | Choropleth map |
| Ranking | Horizontal bar chart |
| Flow or process | Sankey diagram |
| Matrix of relationships | Heatmap |

Explain the recommendation briefly if the user didn't specify.

### 4. Generate the Visualization

Write Python code using one of these libraries based on the need:

- **matplotlib + seaborn**: Best for static, publication-quality charts. Default choice.
- **plotly**: Best for interactive charts or when the user requests interactivity.

**Code requirements:**

```python
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

fig, ax = plt.subplots(figsize=(10, 6))

# [chart-specific code]

ax.set_title('Clear, Descriptive Title', fontsize=14, fontweight='bold')
ax.set_xlabel('X-Axis Label', fontsize=11)
ax.set_ylabel('Y-Axis Label', fontsize=11)

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('chart_name.png', dpi=150, bbox_inches='tight')
plt.show()
```

Format numbers appropriately (percentages, currency, K/M). Prefer colorblind-friendly palettes; insight-style titles; bar Y-axis at zero.

### 5. Save and Present

1. Save the chart as a PNG with a descriptive name
2. Display the chart to the user
3. Provide the code used so they can modify it
4. Suggest variations

## Tips

- Say "interactive" to prefer plotly
- Say "presentation" for larger fonts and higher contrast
- Multiple charts in one ask are fine (e.g. 2x2 grid)

Source: https://github.com/anthropics/knowledge-work-plugins (data/skills/create-viz)
