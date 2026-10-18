import json
import unittest
from service.regulatory_search import LegalSearch

class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.search=LegalSearch()
    def facts(self, text='Клиент ушёл, кассир пересчитывает принимаемые деньги клиента.'):
        return [dict(id='F1',text=text,pts_sec=[1.0,2.0],certainty='clear')]
    def test_retrieval_not_dependent_on_event_code(self):
        found=self.search.retrieve(self.facts())
        self.assertIn('CASH_005',[r['rule_id'] for r in found])
    def test_only_officially_verified_excerpts(self):
        for rule in self.search.rules:
            self.assertTrue(self.search.audit['rules'][rule['rule_id']]['text_verified'])
    def test_model_cannot_invent_rule_or_link(self):
        out=self.search.validate(json.dumps(dict(rule_id='FAKE',conditions=[],reason='test')),self.facts(),self.search.retrieve(self.facts()),'eos')
        self.assertEqual(out['assessment'],'REJECTED_MODEL_OUTPUT')
        self.assertFalse(out['sources'])
    def answer(self,value='UNKNOWN'):
        r=next(r for r in self.search.rules if r['rule_id']=='CASH_005')
        rows=[dict(id=c['condition_id'],value=value,fact_ids=[] if value=='UNKNOWN' else ['F1'],reason='test') for c in r['required_conditions']+r['abstention_conditions']]
        return r,dict(rule_id=r['rule_id'],conditions=rows,reason='test')
    def test_unknown_does_not_confirm(self):
        r,a=self.answer()
        self.assertEqual(self.search.validate(json.dumps(a),self.facts(),[r],'eos')['assessment'],'INSUFFICIENT_EVIDENCE')
    def test_unseen_fact_and_truncated_rejected(self):
        r,a=self.answer('TRUE'); a['conditions'][0]['fact_ids']=['fake']
        for finish in ('eos','length'):
            self.assertEqual(self.search.validate(json.dumps(a),self.facts(),[r],finish)['assessment'],'REJECTED_MODEL_OUTPUT')
    def test_missing_condition_rejected(self):
        r,a=self.answer(); a['conditions'].pop()
        self.assertEqual(self.search.validate(json.dumps(a),self.facts(),[r],'eos')['assessment'],'REJECTED_MODEL_OUTPUT')
    def test_uncertain_evidence_cannot_confirm(self):
        r,a=self.answer('TRUE'); facts=self.facts(); facts[0]['certainty']='uncertain'
        self.assertEqual(self.search.validate(json.dumps(a),facts,[r],'eos')['assessment'],'REJECTED_MODEL_OUTPUT')
    def test_abstentions_must_be_explicitly_false(self):
        r,a=self.answer('TRUE')
        self.assertEqual(self.search.validate(json.dumps(a),self.facts(),[r],'eos')['assessment'],'INSUFFICIENT_EVIDENCE')
        for row in a['conditions']:
            if '_A' in row['id']: row['value']='FALSE'
        out=self.search.validate(json.dumps(a),self.facts(),[r],'eos')
        self.assertEqual(out['assessment'],'POTENTIAL_MATCH')
        self.assertTrue(out['sources'][0]['quote'])
