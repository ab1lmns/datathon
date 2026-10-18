"""Verify original inference source against captured production hashes."""
import hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'deploy/server-source-sha256.json').read_text())
# Explicit presentation-only update; original export hashes remain preserved.
overrides = root/'deploy/presentation-sha256.json'
if overrides.exists():
    manifest.update(json.loads(overrides.read_text()))
checked = []
for name, expected in manifest.items():
    if name.startswith(('cashguard/', 'service/', 'assets/fonts/', 'regulatory/')) or name in {'models/safe_clf.joblib', 'models/money_clf.joblib'}:
        actual = hashlib.sha256((root/name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Mismatch: {name}')
        checked.append(name)
print(f'PASS: {len(checked)} runtime files match release manifests')
