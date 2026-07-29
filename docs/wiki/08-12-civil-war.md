# Layout Uniformity (Indentation Consistency)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Indentation Polarization (Tabs vs. Spaces)
>
> **Summary:** Measures the structural formatting consistency of a file by calculating the ratio of space-indented lines to tab-indented lines. 
> 
> **Disclaimer:** *While GitGalaxy is designed for rigorous architectural and security analysis, this specific metric is included as a lighthearted Easter egg metric for engineering teams. It does not factor into risk exposure vectors.*
>
> **Effect:** Uses a Diverging Visual Spectrum from 0 to 100:
> * 🟩 **PURE TABS (Score 0 - 19):** 100% Tab Indentation.
> * 🟦 **MIXED FORMATTING (Score 20 - 79):** Mixed Tabs and Spaces (50.0 represents maximum conflict).
> * 🟨 **PURE SPACES (Score 80 - 100):** 100% Space Indentation.

## Architectural Overview

By mapping pure tab indentation to 0.0 and pure space indentation to 100.0, files with mixed indentation naturally center around 50.0.

This metric surfaces files where conflicting editor settings or multiple contributors have introduced inconsistent indentation standards within the same file. A score near 0 or 100 indicates unified formatting, whereas a score near 50 indicates mixed layout formatting.

## Metric Inputs (Indentation Scanning)

The scanner counts leading indentation tokens per line:

| Input Variable | Data Source | Description |
| :--- | :--- | :--- |
| `indent_tabs` | Static Line Parser | Count of lines beginning with one or more tab characters (`\t`). |
| `indent_spaces` | Static Line Parser | Count of lines beginning with one or more space characters (` `). |

## Mathematical Formulation

### Step 1: Count Indented Lines
The engine sums all lines containing measurable indentation:

$$\text{TotalIndentedLines} = \text{TabLines} + \text{SpaceLines}$$

### Step 2: Calculate Space Ratio
The ratio of space-indented lines to total indented lines is computed:

$$\text{SpaceRatio} = \frac{\text{SpaceLines}}{\max(\text{TotalIndentedLines}, 1)}$$

* If $\text{TotalIndentedLines} == 0$ (unindented or empty file), the metric defaults to neutral $50.0$.

### Step 3: Map Final Score
The ratio is scaled onto a 0–100 range:

$$\text{FinalScore} = \text{SpaceRatio} \times 100.0$$

## Python Implementation Reference

```python
from typing import Dict

def _calc_civil_war(self, raw_signals: Dict[str, int]) -> float:
    """
    Calculates Layout Uniformity (Tabs vs Spaces). 
    0 = Pure Tabs, 100 = Pure Spaces, 50 = Mixed Indentation.
    NOTE: Easter egg metric, excluded from risk calculations.
    """
    tab_lines = raw_signals.get("indent_tabs", 0)
    space_lines = raw_signals.get("indent_spaces", 0)
    
    total_indented = tab_lines + space_lines
    
    # Handle files with zero indentation
    if total_indented == 0:
        return 50.0  # Default to neutral midpoint
        
    # Calculate Space Ratio
    space_ratio = space_lines / float(total_indented)
    
    # Final Score Mapping (0 - 100)
    return space_ratio * 100.0
```

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**
