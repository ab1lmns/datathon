import unittest
from service.regulatory import RULES, MAPPING, reference_for, enrich
from cashguard.registry import REGISTRY

class RegulatoryTest(unittest.TestCase):
    def test_no_unverified_rule_is_automatically_mapped(self):
        for ids,_ in MAPPING.values():
            self.assertTrue(all(RULES[r]['legal_status']=='VERIFIED' for r in ids))
        self.assertFalse(any('CASH_033' in ids for ids,_ in MAPPING.values()))
    def test_missing_conditions_do_not_become_proven(self):
        for code in REGISTRY:
            ref=reference_for(code)
            self.assertEqual(ref['assessment'],'NEEDS_REVIEW')
            self.assertTrue(all(c['value']=='UNKNOWN' for c in ref['unknown_conditions']))
    def test_foreign_person_is_not_exchange_office_rule(self):
        ref=reference_for('E_unauthorized_person')
        self.assertNotIn('CASH_053',ref['rule_ids'])
    def test_unknown_type_has_no_invented_link(self):
        self.assertIsNone(reference_for('unknown')['url'])
    def test_official_clause_links_and_no_event_suppression(self):
        original={'type':REGISTRY['F_bag_no_check']['name'],'timecode_sec':8.8,'description':'raw visual output','evidence_frames':[{'timestamp_sec':8.8,'image_base64':'test'}]}
        result=enrich({'status':'done','verdict':'violation','violations':[original.copy()]})
        self.assertEqual(result['verdict'],'violation')
        self.assertEqual(len(result['violations']),1)
        for key,value in original.items():self.assertEqual(result['violations'][0][key],value)
        ref=result['violations'][0]['rule']
        self.assertEqual(ref['rule_ids'],['CASH_035'])
        self.assertTrue(all(s['url'].startswith('https://adilet.zan.kz/') for s in ref['sources']))
