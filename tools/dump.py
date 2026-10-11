#!/usr/bin/env python3
"""dump.py file.json — print root view-model properties from a --data-dump."""
import json, sys
d = json.load(open(sys.argv[1]))
vm = d.get("viewModel", {})
print({p["path"]: p["value"] for p in vm.get("properties", [])})
