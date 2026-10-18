import html
import json
import re
import unittest
from pathlib import Path
from service.regulatory import enrich, reference_for, APPLICABILITY_SOURCES, RULES
from forte.registry import REGISTRY, describe

class ApplicabilityTest(unittest.TestCase):
    def test_supplemental_quotes_match_exact_official_paragraphs(self):
        root=Path(__file__).resolve().parents[1]/'regulatory'
        for rid,sources in APPLICABILITY_SOURCES.items():
            doc=RULES[rid]['legal_document']['document_id']
            content=json.loads((root/'source_evidence'/f'{doc}.json').read_text())['document']['text_content']
            for source in sources:
                anchor=source['url'].split('#')[1]
                m=re.search(r'<p\b[^>]*\bid="'+re.escape(anchor)+r'"[^>]*>(.*?)</p>',content,re.S)
                self.assertIsNotNone(m)
                text=' '.join(html.unescape(re.sub('<[^>]+>',' ',m[1])).split())
                self.assertEqual(source['quote'],text)
    def test_storage_cites_storage_not_client_presence(self):
        for code in ('A_unattended_valuables','B_safe_open','C_cash_on_desk_next_client'):
            self.assertIn('Все ранее принятые',reference_for(code)['sources'][0]['quote'])
    def test_bag_cites_actual_checks(self):
        sources=reference_for('F_bag_no_check')['sources']
        self.assertTrue(any('проверяет целостность сумки' in s['quote'] for s in sources))
        self.assertTrue(any('правильность пломбирования' in s['quote'] for s in sources))
    def test_known_templates_qualified_and_original_evidence_preserved(self):
        for code in REGISTRY:
            for details in ({},{'kind':'drinking'}):
                d=describe(code,8.8,details)
                original=dict(type=d['type'],timecode_sec=8.8,description=d['description']+' Возможное нарушение требования: '+d['norm']+'.',evidence_frames=[dict(timestamp_sec=8.8,image_base64='original')])
                out=enrich(dict(status='done',verdict='violation',violations=[original.copy()]))
                e=out['violations'][0]
                self.assertTrue(e['description'].startswith('Система'))
                self.assertNotEqual(e['description'],original['description'])
                for key in ('type','timecode_sec','evidence_frames'):self.assertEqual(e[key],original[key])
                self.assertEqual(enrich(out),out)
    def test_no_inference_of_money_next_to_drink(self):
        d=describe('G_personal_items',14,{'kind':'drinking'})
        out=enrich(dict(status='done',violations=[dict(type=d['type'],description=d['description'])]))
        self.assertNotIn('находятся наличные',out['violations'][0]['description'])
    def test_structural_norm_not_a_direct_prohibition(self):
        for code in ('B_safe_open','E_unauthorized_person','H_door_open'):
            self.assertEqual(reference_for(code)['relation'],'RELATED_ONLY')
