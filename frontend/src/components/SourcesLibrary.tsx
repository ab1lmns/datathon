import { useId, useState } from 'react';
import { ArrowRight, ArrowUpRight, ChevronDown, FileText, Folder, Search, ShieldCheck, X } from './Icons';
import catalog from '../data/sources-catalog.json';
import type { ReviewEvent, ReviewJob } from '../api/types';

type SourceDocument=typeof catalog.documents[number];
type SourceLink=SourceDocument['links'][number];
type Group='all'|'rules'|'amendments'|'archive';
const groups:{id:Group;label:string;description:string}[]=[{id:'all',label:'Все документы',description:'Полный нормативный пакет'},{id:'rules',label:'Основные правила',description:'Операции, помещения и наличные'},{id:'amendments',label:'Изменения',description:'Поправки к основным актам'},{id:'archive',label:'Прежние редакции',description:'Акты, утратившие силу по пакету'}];
const normalize=(s:string)=>s.toLocaleLowerCase('ru').replaceAll('ё','е').trim();
const matches=(s:string,q:string)=>normalize(s).includes(q);
const linkText=(link:SourceLink)=>[...link.sections,...link.topics.flatMap(t=>[t.title,t.summary]),link.quote,link.url].join(' ');
const date=(value:string)=>value.split('-').reverse().join('.');

function DocumentCard({document,query}:{document:SourceDocument;query:string}){
 const [expanded,setExpanded]=useState(false),[all,setAll]=useState(false);
 const id=useId();
 const open=expanded||!!query;
 const titleMatch=matches(`${document.shortTitle} ${document.title} ${document.number}`,query);
 const links=query&&!titleMatch?document.links.filter(l=>matches(linkText(l),query)):document.links;
 const shown=all||query?links:links.slice(0,4);
 return <article className={`source-document ${open?'is-open':''}`}>
  <div className="source-document-heading">
   <button className="source-document-toggle" onClick={()=>setExpanded(v=>!v)} aria-expanded={open} aria-controls={id} disabled={!!query}>
    <span className="source-document-icon"><FileText size={22}/></span><span className="source-document-title"><span className="source-document-meta">ПОСТАНОВЛЕНИЕ № {document.number}<span>{date(document.adoption_date)}</span></span><strong>{document.shortTitle}</strong><span className="source-document-caption">{links.length?`${links.length} ссылок на пункты`:'Официальный текст документа'}</span></span><ChevronDown size={19} className="source-chevron"/>
   </button>
  </div>
  <div className="source-document-content" id={id} aria-hidden={!open} inert={!open}><div className="source-document-content-inner"><div className="source-document-body">
   <p className="source-official-title">{document.title}</p>
   <a className="source-link source-document-open" href={document.url} target="_blank" rel="noreferrer"><FileText size={18}/>Открыть документ в Әділет<ArrowUpRight size={18}/></a>
   {document.revision_note&&<p className="source-revision-note">{document.revision_note}</p>}
   {links.length>0&&<div className="source-clauses"><div className="source-clauses-heading"><h3>Пункты и темы</h3><span>Ссылки из нормативного пакета</span></div>{shown.map(link=><div className="source-clause" key={link.url}>
    <div className="source-clause-copy"><h4>{link.sections.join(' · ')||'Текст документа'}</h4><p>{link.topics.map(t=>t.title).join(' / ')}</p>{link.topics.some(t=>t.status!=='VERIFIED')&&<span className="source-clause-review">Применимость требует проверки по пакету</span>}</div>
    <a className="source-clause-link" href={link.url} target="_blank" rel="noreferrer" aria-label={`Открыть ${link.sections.join(', ')||'текст документа'}`}>К пункту<ArrowUpRight size={16}/></a>
   </div>)}{!query&&links.length>4&&<button className="source-show-all" aria-expanded={all} onClick={()=>setAll(v=>!v)}>{all?'Свернуть список':`Показать все ссылки (${links.length})`}<ChevronDown size={16} className={all?'rotated':''}/></button>}</div>}
  </div></div></div>
 </article>;
}

export function SourcesLibrary({sources,onRule,onJob}:{sources:{event:ReviewEvent;job:ReviewJob}[];onRule:(event:ReviewEvent)=>void;onJob:(job:ReviewJob)=>void}){
 const [query,setQuery]=useState(''),[group,setGroup]=useState<Group>('all');
 const q=normalize(query);
 const visible=catalog.documents.filter(d=>(group==='all'||d.group===group)&&(!q||matches(`${d.shortTitle} ${d.title} ${d.number} ${d.url}`,q)||d.links.some(l=>matches(linkText(l),q))));
 return <div className="sources-library">
  <section className="sources-introduction" data-reveal><div><span className="overline">НОРМАТИВНАЯ БИБЛИОТЕКА</span><h2>Документы для внимательной проверки</h2><p>Кассовые операции, безопасность помещений, банкноты и валютный обмен — все ссылки собраны по документам.</p></div><div className="sources-package"><ShieldCheck size={20}/><span>Пакет от {date(catalog.checkedAt)}<small>{catalog.documents.length} документов · {catalog.ruleCount} темы</small></span></div></section>
  <div className="sources-layout">
   <aside className="sources-navigation" aria-label="Разделы источников" data-reveal><span className="overline">КАТАЛОГ</span>{groups.map(g=><button key={g.id} aria-pressed={group===g.id} onClick={()=>setGroup(g.id)}><span><strong>{g.label}</strong><small>{g.description}</small></span><span className="sources-group-count">{g.id==='all'?catalog.documents.length:catalog.documents.filter(d=>d.group===g.id).length}</span></button>)}<p className="sources-provenance">Статусы и примечания приведены на дату пакета. Для конкретного события проверяйте редакцию и условия применения.</p></aside>
   <section className="sources-results" aria-label="Каталог нормативных документов" data-reveal>
    <div className="sources-toolbar"><label className="sources-search"><Search size={18}/><input aria-label="Поиск по нормативным источникам" placeholder="Документ, номер или тема — например, сейф" value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button aria-label="Очистить поиск источников" onClick={()=>setQuery('')}><X size={16}/></button>}</label><span className="sources-result-count" role="status">Найдено: {visible.length}</span></div>
    <div className="source-documents">{visible.map(d=><DocumentCard key={d.document_id} document={d} query={q}/>)}</div>
    {!visible.length&&<div className="panel empty"><Search size={26}/><h3>Ничего не найдено</h3><p>Измените запрос или выберите другой раздел.</p><button className="text-link" onClick={()=>{setQuery('');setGroup('all')}}>Показать все документы</button></div>}
   </section>
  </div>
  {!!sources.length&&<section className="panel sources-report-references" data-reveal><div className="sources-report-heading"><Folder size={20}/><div><h2>Источники в ваших отчётах</h2><p>Нормы, которые сервер связал с найденными событиями.</p></div></div>{sources.map(({event,job},i)=><div className="source-entry" key={`${job.id}-${i}`}><button className="rule-row" onClick={()=>onRule(event)}><FileText size={20}/><span><strong>{event.rule!.document}</strong><small>{event.rule!.section||'Пункт не указан'} — {event.title}</small></span><ArrowUpRight size={16}/></button><button className="text-link" onClick={()=>onJob(job)}>Открыть {job.name}<ArrowRight size={14}/></button></div>)}</section>}
 </div>;
}
