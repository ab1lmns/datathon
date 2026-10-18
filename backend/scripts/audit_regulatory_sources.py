"""Fetch public official texts and check each supplied excerpt at its exact anchor."""
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'regulatory'

def plain(s):
    return ' '.join(unescape(re.sub('<[^>]+>', ' ', s)).split())

def main():
    data = json.loads((ROOT / 'regulatory_rules.json').read_text())
    dest = ROOT / 'source_evidence'
    dest.mkdir(exist_ok=True)
    documents = {}
    for doc in data['documents']:
        url = 'https://adilet.zan.kz/api/documents/' + doc['source_version_id']
        try:
            raw = urllib.request.urlopen(url, timeout=30).read()
            obj = json.loads(raw)['document']
            if obj['group_number'] != doc['document_id'] or not obj.get('text_content'):
                raise ValueError('document identity/content mismatch')
            (dest / (doc['document_id'] + '.json')).write_bytes(raw)
            documents[doc['document_id']] = dict(api_url=url, sha256=hashlib.sha256(raw).hexdigest(),
                status=obj['status'], is_actual=obj['is_actual'], document=obj)
        except Exception as exc:
            documents[doc['document_id']] = {'error': str(exc)}
    audit = {'fetched_at':datetime.now(timezone.utc).isoformat(), 'documents':{}, 'rules':{}}
    for key, item in documents.items():
        audit['documents'][key] = {k:v for k,v in item.items() if k != 'document'}
    for rule in data['rules']:
        doc = rule['legal_document']; source = documents.get(doc['document_id'], {})
        html = source.get('document', {}).get('text_content', '')
        checks = []
        for ref in doc.get('clause_refs', []):
            anchor = ref.get('anchor') or ''
            match = re.search(r'<[^>]+\bid=["\']' + re.escape(anchor) + r'["\'][^>]*>(.*?)</(?:p|h\d|div)>', html, re.S)
            paragraph = plain(match.group(1)) if match else ''
            quote = plain(ref.get('verified_paragraph_excerpt', ''))
            original_anchor = anchor
            if quote and quote not in paragraph:
                alternatives = [(m.group(1),plain(m.group(2))) for m in re.finditer(
                    r'<p\b[^>]*\bid=["\']([^"\']+)["\'][^>]*>(.*?)</p>', html, re.S)
                    if quote in plain(m.group(2))]
                if len(alternatives)==1:
                    anchor,paragraph=alternatives[0]; match=True
            if quote and quote not in paragraph and not original_anchor:
                alternatives = [plain(m.group(1)) for m in re.finditer(r'<p(?:\s[^>]*)?>(.*?)</p>',html,re.S)
                                if quote in plain(m.group(1))]
                if len(alternatives)==1:
                    paragraph=alternatives[0]
            verified_url=doc['url'].split('#')[0]+'#'+anchor if anchor else doc['url']
            checks.append({'anchor':anchor, 'supplied_anchor':original_anchor,
                'url':verified_url, 'supplied_url':ref['url'], 'quote':quote,
                'anchor_found':bool(match), 'excerpt_matches':bool(quote and quote in paragraph),
                'official_paragraph':paragraph})
        audit['rules'][rule['rule_id']] = {'text_verified':bool(checks) and all(c['excerpt_matches'] for c in checks),
            'document_current':source.get('is_actual') is True and source.get('status') not in ('yts',), 'clauses':checks}
    (ROOT / 'source_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'documents':len(documents), 'rules':len(audit['rules']),
        'text_verified':sum(r['text_verified'] for r in audit['rules'].values()),
        'mismatches':[k for k,v in audit['rules'].items() if not v['text_verified']]}, ensure_ascii=False))

if __name__ == '__main__': main()
