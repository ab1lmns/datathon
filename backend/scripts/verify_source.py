"""Verify original inference source against captured production hashes."""
import hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'deploy/server-source-sha256.json').read_text())
checked = []
for name, expected in manifest.items():
    if name.startswith(('cashguard/', 'service/')) or name in {'models/safe_clf.joblib', 'models/money_clf.joblib'}:
        actual = hashlib.sha256((root/name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Mismatch: {name}')
        checked.append(name)
print(f'PASS: {len(checked)} production source/model files unchanged')
