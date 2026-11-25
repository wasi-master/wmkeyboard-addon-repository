# Tests for Syntax Pack, run by tools/test_plugins.py under wm-python-cli.
# The grammars are data the keyboard runs, so this checks their shape;
# tools/build_plugins.py compiles every expression with ICU, Android's engine.

import json

KINDS = ["comment", "string", "number", "keyword", "type", "function", "operator", "tag", "attribute",
         "heading", "link", "emphasis", "constant", "punctuation"]

manifest = json.loads(plugin_test.read("plugin.json"))
assert "permissions" not in manifest, "grammars need no permission"
ids = []
claimed = {}
for entry in manifest["syntax"]:
    ids.append(entry["id"])
    assert entry["grammar"] == "assets/" + entry["id"] + ".json", entry["id"]
    for ext in entry.get("extensions", []):
        assert ext not in claimed, ext + " is in " + claimed.get(ext, "") + " and " + entry["id"]
        claimed[ext] = entry["id"]
    grammar = json.loads(plugin_test.read(entry["grammar"]))
    for i, rule in enumerate(grammar.get("rules", [])):
        assert rule["kind"] in KINDS, entry["id"] + " rule " + str(i + 1) + ": " + rule["kind"]
        assert rule["match"], entry["id"] + " rule " + str(i + 1) + " is empty"
        for flag in rule.get("flags", ""):
            assert flag in "ims", entry["id"] + " rule " + str(i + 1) + " flag " + flag
    words = grammar.get("keywords", []) + grammar.get("types", []) + grammar.get("constants", [])
    assert grammar.get("rules") or words or grammar.get("lineComment"), entry["id"] + " colours nothing"
assert len(ids) == 16 and len(set(ids)) == 16, ids
