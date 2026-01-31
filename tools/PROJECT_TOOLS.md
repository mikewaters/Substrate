# Project Maintenance Tools Instructions

This document describes the maintenance script standards for this project. **All maintenance scripts** should follow this pattern.

## Maintenance Tools Location

Maintenance Tools should be placed in the project's top-leve `tools/` directory.

## Utility Script Requirements
Utility scripts can be written in Python or Bash.

For Python scripts:
1. Uses Python's "inline script metadata" standard to define the dependencies in the script itself, with a specific shebang line provided in the following example:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "DEPENDENCY_NAME",
# ]
# ///
```

2. Use `uv run` to execute the maintenancew script:

`uv run tools/my-script-name.py`

For bash scripts:
1. Use the following shebang:

```bash
#!/usr/bin/env bash
```

## Integrating maintenance scripts with your code

Maintenance scripts should never invoke any of the project source code. These types of script instead belong in the project root `scripts/` folder.
