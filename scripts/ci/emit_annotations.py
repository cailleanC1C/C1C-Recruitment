*** /dev/null
--- a/scripts/ci/emit_annotations.py
@@
+import os, re, sys, pathlib
+
+# Usage:
+#   python scripts/ci/emit_annotations.py --kind docs --input path/to/output.log
+#   python scripts/ci/emit_annotations.py --kind guardrails --input path/to/output.log
+#
+# Emits GitHub Annotations and writes a short checklist to $GITHUB_STEP_SUMMARY.
+
+DOCS_PATTERNS = [
+    # e.g. "docs/README.md: footer missing or malformed."
+    re.compile(r'^(?P<file>[\w\-/\.]+):\s*(?P<msg>footer missing or malformed)\.?$', re.I),
+    # e.g. "docs/README.md: missing links for -> Architecture.md, _meta/DocStyle.md"
+    re.compile(r'^(?P<file>[\w\-/\.]+):\s*missing links for\s*->\s*(?P<msg>.+)$', re.I),
+]
+
+# Guardrails lines should be printed by the check script like:
+# "VIOLATION: GR-001 No new labels without contract approval file: .github/labels.yml line: 14"
+GR_PATTERNS = [
+    re.compile(
+        r'^VIOLATION:\s*(?P<rule>[A-Z0-9\-_.]+)\s+(?P<msg>.+?)\s+file:\s*(?P<file>[\w\-/\.]+)(?:\s+line:\s*(?P<line>\d+))?\s*$',
+        re.I
+    )
+]
+
+def emit_error(file, line, title, msg):
+    line = int(line) if (line and str(line).isdigit()) else 1
+    print(f"::error file={file},line={line},title={title}::{msg}")
+
+def append_summary(lines):
+    summ = os.getenv("GITHUB_STEP_SUMMARY")
+    if not summ:
+        return
+    with open(summ, "a", encoding="utf-8") as fh:
+        fh.write("### Check results\n\n")
+        if not lines:
+            fh.write("All clear.\n")
+            return
+        for l in lines:
+            fh.write(f"- {l}\n")
+
+def parse(kind, text):
+    out = []
+    if kind == "docs":
+        for raw in text.splitlines():
+            for rx in DOCS_PATTERNS:
+                m = rx.match(raw.strip())
+                if m:
+                    d = m.groupdict()
+                    emit_error(d["file"], 1, "Docs check", d["msg"])
+                    out.append(f"{d['file']}: {d['msg']}")
+                    break
+    elif kind == "guardrails":
+        for raw in text.splitlines():
+            for rx in GR_PATTERNS:
+                m = rx.match(raw.strip())
+                if m:
+                    d = m.groupdict()
+                    title = f"Guardrail {d['rule']}"
+                    msg = d["msg"]
+                    emit_error(d["file"], d.get("line") or 1, title, msg)
+                    out.append(f"{d['rule']}: {msg} ({d['file']}{':' + d['line'] if d.get('line') else ''})")
+                    break
+    return out
+
+def main():
+    kind = None
+    inp = None
+    args = sys.argv[1:]
+    while args:
+        a = args.pop(0)
+        if a == "--kind":
+            kind = args.pop(0)
+        elif a == "--input":
+            inp = args.pop(0)
+    if not (kind and inp):
+        print("usage: emit_annotations.py --kind <docs|guardrails> --input <file>", file=sys.stderr)
+        sys.exit(2)
+    text = pathlib.Path(inp).read_text(encoding="utf-8", errors="ignore")
+    lines = parse(kind, text)
+    append_summary(lines)
+    # do not change exit code here; upstream step should determine success/failure
+
+if __name__ == "__main__":
+    main()
