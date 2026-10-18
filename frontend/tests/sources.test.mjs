import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const read=url=>JSON.parse(fs.readFileSync(url,'utf8'));
const catalog=read(new URL('../src/data/sources-catalog.json',import.meta.url));
const corpus=read(new URL('../../backend/regulatory/regulatory_rules.json',import.meta.url));
test('catalog preserves every archive document, official link and topic',()=>{
 assert.equal(catalog.documents.length,corpus.documents.length);
 const links=new Set(catalog.documents.flatMap(d=>[d.url,...d.links.map(l=>l.url)]));
 const topics=new Set(catalog.documents.flatMap(d=>d.links.flatMap(l=>l.topics.map(t=>t.id))));
 for(const doc of corpus.documents){const output=catalog.documents.find(d=>d.document_id===doc.document_id);assert.equal(output.status_as_of_check,doc.status_as_of_check);assert.ok(links.has(doc.url))}
 for(const rule of corpus.rules){assert.ok(topics.has(rule.rule_id),rule.rule_id);assert.ok(links.has(rule.legal_document.url));for(const ref of [...rule.legal_document.clause_refs,...rule.additional_legal_refs])assert.ok(links.has(ref.url),ref.url)}
 for(const link of links){const url=new URL(link);assert.equal(url.protocol,'https:');assert.equal(url.hostname,'adilet.zan.kz')}
});
test('catalog includes audit corrections and applicability references',()=>{
 const links=new Set(catalog.documents.flatMap(d=>[d.url,...d.links.map(l=>l.url)]));
 const audit=read(new URL('../../backend/regulatory/source_audit.json',import.meta.url));
 const extras=read(new URL('../../backend/regulatory/applicability_sources.json',import.meta.url));
 for(const rule of Object.values(audit.rules))for(const clause of rule.clauses)assert.ok(links.has(clause.url));
 for(const list of Object.values(extras))for(const ref of list)assert.ok(links.has(ref.url));
});
