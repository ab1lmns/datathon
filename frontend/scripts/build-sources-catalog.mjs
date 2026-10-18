import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const read=async name=>JSON.parse(await fs.readFile(path.join(root,'backend/regulatory',name),'utf8'));
const [corpus,audit,extras,provenance]=await Promise.all(['regulatory_rules.json','source_audit.json','applicability_sources.json','provenance.json'].map(read));
const titles={V1900019680:'Кассовые операции и инкассация',V2000020075:'Охрана и устройство банковских помещений',V1700016120:'Платёжность банкнот и монет',V1900018545:'Обмен наличной иностранной валюты',V2600038217:'Изменения по наличному денежному обращению',V2600039191:'Изменения постановлений Национального Банка',V2400035552:'Изменения требований к банковским помещениям',V2500037429:'Изменения правил обращения наличных и инкассации',V1900019391:'Автомобильные инкассаторские перевозки',V010001482_:'Кассовые операции и инкассация — прежние правила',V1200008080:'Охрана банковских помещений — прежние правила',V030002689_:'Платёжность банкнот и монет — прежние правила'};
const documents=corpus.documents.map(doc=>({...doc,shortTitle:titles[doc.document_id]||doc.title,group:doc.status_as_of_check==='REPEALED'?'archive':doc.title.startsWith('О внесении')?'amendments':'rules',links:[]}));
function addLink(docId,url,section,rule,quote='',origin='archive'){
 if(!url)return;
 const parsed=new URL(url);if(parsed.protocol!=='https:'||parsed.hostname!=='adilet.zan.kz')throw Error('Unexpected source URL');
 const doc=documents.find(d=>d.document_id===docId);if(!doc)throw Error(`Missing document ${docId}`);
 let link=doc.links.find(l=>l.url===url);
 if(!link){link={url,sections:[],topics:[],quote,origins:[]};doc.links.push(link)}
 if(section&&!link.sections.includes(section))link.sections.push(section);
 if(quote&&!link.quote)link.quote=quote;
 if(!link.origins.includes(origin))link.origins.push(origin);
 if(rule&&!link.topics.some(t=>t.id===rule.rule_id))link.topics.push({id:rule.rule_id,title:rule.event_name_ru,summary:rule.norm_summary,status:rule.legal_status});
}
for(const rule of corpus.rules){
 const doc=rule.legal_document;
 if(!doc.clause_refs?.length)addLink(doc.document_id,doc.url,doc.clause,rule);
 for(const ref of doc.clause_refs||[])addLink(doc.document_id,ref.url,ref.clause,rule,ref.verified_paragraph_excerpt);
 for(const ref of rule.additional_legal_refs||[])addLink(ref.document_id,ref.url,ref.clause,rule);
 for(const clause of audit.rules[rule.rule_id]?.clauses||[])addLink(doc.document_id,clause.url,doc.clause,rule,clause.quote,'audit');
 for(const extra of extras[rule.rule_id]||[]){
  const id=documents.find(d=>new URL(d.url).pathname===new URL(extra.url).pathname)?.document_id;
  addLink(id,extra.url,extra.section,rule,extra.quote,'applicability');
 }
}
const catalog={checkedAt:corpus.checked_at,sourceArchive:provenance.source_archive,ruleCount:corpus.rules.length,documents};
await fs.mkdir(path.join(root,'frontend/src/data'),{recursive:true});
await fs.writeFile(path.join(root,'frontend/src/data/sources-catalog.json'),JSON.stringify(catalog,null,2)+'\n');
console.log(`${documents.length} documents, ${corpus.rules.length} topics, ${new Set(documents.flatMap(d=>[d.url,...d.links.map(l=>l.url)])).size} unique source URLs`);
