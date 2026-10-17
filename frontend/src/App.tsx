import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Cable, CircleHelp, FileText, Folder, Info, LayoutDashboard, Play, Plus, Search, ShieldCheck, UploadCloud, X, AlertCircle } from './components/Icons';
import './styles.css';
import './motion.css';
import './pages.css';
import type { ReviewEvent, ReviewJob, Settings } from './api/types';
import { useReviews } from './hooks/useReviews';
import { useContentTransition } from './hooks/useContentTransition';
import { useRoute, type Route } from './hooks/useRoute';
import { BrandIntro } from './components/BrandIntro';
import { ForteSculpture } from './components/ForteSculpture';
import { Modal } from './components/Modal';
import { ReviewDetail, VideoPlayer, clock } from './components/ReviewDetail';
import { ReportLibrary, collectionNames } from './components/ReportLibrary';
import { Overview } from './components/Overview';
import { SidebarFaq } from './components/SidebarFaq';
import { ServiceConnection } from './components/ServiceConnection';

type Dialog={type:'help'}|{type:'upload'}|{type:'rules';event:ReviewEvent}|{type:'player';job:ReviewJob;event?:ReviewEvent}|{type:'evidence';image:string;time:number}|null;
const navigation=[{id:'overview',Icon:LayoutDashboard,label:'Обзор',short:'Обзор'},{id:'reports',Icon:Folder,label:'Видеоотчёты',short:'Отчёты'},{id:'sources',Icon:FileText,label:'Источники',short:'Источники'},{id:'connection',Icon:Cable,label:'Подключение',short:'Сервер'}] as const;
const pageCopy={overview:['Важное — в фокусе.','Состояние проверок и события, которые требуют вашего внимания.'],reports:['Видеоотчёты','Откройте папку, выберите запись и проверьте каждый важный момент.'],sources:['Нормативные источники','Документы и правила, связанные с событиями в ваших отчётах.'],connection:['Подключение сервера','Адрес, ключ доступа и готовность сервиса к анализу записей.']};

export default function App(){
 const [booting,setBooting]=useState(()=>!matchMedia('(prefers-reduced-motion: reduce)').matches);
 const finishStartup=useCallback(()=>setBooting(false),[]);
 const [settings,setSettings]=useState<Settings>({mode:'api',baseUrl:import.meta.env.VITE_API_BASE_URL||'',apiKey:''});
 const {jobs,upload:submitFiles,cancel,retry}=useReviews(settings);
 const {route,go}=useRoute();
 const [query,setQuery]=useState(''),[dialog,setDialog]=useState<Dialog>(null),[drag,setDrag]=useState(false),[error,setError]=useState(''),[searchOpen,setSearchOpen]=useState(false);
 const input=useRef<HTMLInputElement>(null),search=useRef<HTMLInputElement>(null),dragDepth=useRef(0);
 const dashboard=useContentTransition<HTMLElement>();
 useLayoutEffect(()=>{if(!booting)dashboard.reveal()},[booting,dashboard.reveal]);
 useEffect(()=>{if(searchOpen)search.current?.focus()},[searchOpen]);
 const job=route.jobId?jobs.find(j=>j.id===route.jobId):undefined;
 function navigate(next:Route,source?:HTMLButtonElement){
  dashboard.transition(()=>{go(next);setQuery('');setError('');window.scrollTo({top:0,behavior:'instant'})},{source});
 }
 function openJob(j:ReviewJob){navigate({page:'reports',jobId:j.id,collection:route.collection})}
 function connection(){setDialog(null);navigate({page:'connection'})}
 function upload(files:FileList|null){
  if(!files?.length)return;
  dashboard.cancel();
  if(settings.mode!=='api'||!settings.apiKey){setError('Для новой записи выберите режим API и введите ключ на странице «Подключение».');return;}
  const result=submitFiles(files);setError(result.error);
  if(result.id){setDialog(null);go({page:'reports',jobId:result.id});setQuery('')}
  if(input.current)input.current.value='';
 }
 function exportReport(j:ReviewJob){
  const result={job_id:j.remoteId||j.id,filename:j.name,source:j.demo?'dataset_annotation':'api',status:'done',verdict:j.status==='clean'?'no_violation':'violation',violations:j.events.map(e=>({type:e.title,timecode_sec:e.time,description:e.description,evidence_frames:e.frames,...(e.rule?{rule:e.rule}:{})}))};
  const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`${j.name.replace(/\.mov$/i,'')}-report.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 const sources=jobs.flatMap(j=>j.events.filter(e=>e.rule).map(e=>({event:e,job:j})));
 return <><div className="app-shell" inert={booting} data-booting={booting||undefined}>
 <a className="skip-link" href="#workspace" onClick={e=>{e.preventDefault();document.getElementById('workspace')?.focus()}}>Перейти к содержимому</a>
 <header className="app-header"><ForteSculpture onActivate={()=>navigate({page:'overview'})}/><span className="product-name"><span className="product-name-label">Видеоконтроль</span></span>
 <label className={`search ${searchOpen?'is-open':''}`}><Search size={17}/><input ref={search} aria-label="Поиск видеоотчётов" placeholder="Найти видеоотчёт" value={query} onChange={e=>{dashboard.cancel();setQuery(e.target.value);go({page:'reports'})}}/>{query?<button aria-label="Очистить поиск" onClick={()=>setQuery('')}><X size={15}/></button>:<span className="search-hint">.mov</span>}<button className="mobile-search-close icon-button" aria-label="Закрыть поиск" onClick={()=>{setSearchOpen(false);setQuery('')}}><X size={18}/></button></label>
 <div className="header-actions"><button className="mobile-search-toggle icon-button" aria-label="Открыть поиск" onClick={()=>setSearchOpen(true)}><Search size={19}/></button><button className="primary global-upload" onClick={()=>{setError('');setDialog({type:'upload'})}}><Plus size={17}/><span>Загрузить видео</span></button><button className="help icon-button" aria-label="Помощь" onClick={()=>setDialog({type:'help'})}><CircleHelp size={19}/></button></div>
 </header>
 <aside className="sidebar"><span className="nav-overline">РАБОЧЕЕ ПРОСТРАНСТВО</span><nav aria-label="Основная навигация">{navigation.map(({id,Icon,label,short})=><button key={id} aria-current={route.page===id?'page':undefined} className={route.page===id?'active':''} onClick={()=>navigate({page:id})}><Icon size={19}/><span className="nav-label">{label}</span><span className="nav-short">{short}</span></button>)}</nav><SidebarFaq/></aside>
 <main id="workspace" tabIndex={-1} ref={dashboard.ref} className={`workspace-folder page-${route.page}`}><span className="workspace-tab" aria-hidden="true">{navigation.find(n=>n.id===route.page)?.label}</span><div className="workspace-content">
 <section className="intro page-intro" data-reveal><div className="intro-copy"><div className="eyebrow">Рабочее пространство <span className="eyebrow-separator">/</span> {navigation.find(n=>n.id===route.page)?.label}</div><h1>{route.jobId?'Отчёт по видеозаписи':pageCopy[route.page][0]}</h1><p>{route.jobId?'Проверьте событие, исходную запись и нормативное основание.':pageCopy[route.page][1]}</p></div><span className="session-label">{settings.mode==='demo'?'Примеры датасета':'Сервер команды'}</span></section>
 {error&&dialog?.type!=='upload'&&<div role="alert" className="error"><AlertCircle size={17}/><span>{error}</span><button className="icon-button" aria-label="Закрыть ошибку" onClick={()=>setError('')}><X size={16}/></button></div>}
 {route.page==='overview'&&<Overview jobs={jobs} settings={settings} onOpen={openJob} onConnection={connection}/>}
 {route.page==='reports'&&!route.jobId&&<ReportLibrary jobs={jobs} collection={route.collection} query={query} onFolder={(collection,source)=>navigate({page:'reports',collection},source)} onOpen={openJob} onBack={()=>navigate({page:'reports'})}/>}
 {route.page==='reports'&&route.jobId&&<><div className="report-toolbar" data-reveal><button className="text-link" onClick={()=>navigate({page:'reports',collection:route.collection})}><ArrowLeft size={16}/>{route.collection?collectionNames[route.collection]:'К видеоотчётам'}</button>{job&&(job.status==='clean'||job.status==='attention')&&<button className="soft-button" onClick={()=>exportReport(job)}><ArrowDownToLine size={15}/>Скачать JSON</button>}</div>{job?<section className="panel detail full-report" data-reveal aria-label="Видеоотчёт"><ReviewDetail key={job.id} job={job} onPlay={event=>setDialog({type:'player',job,event})} onRule={event=>setDialog({type:'rules',event})} onCancel={cancel} onRetry={retry} onSettings={connection} onBack={()=>navigate({page:'reports'})} onEvidence={(image,time)=>setDialog({type:'evidence',image,time})}/>{job.remoteId&&<p className="job-reference">Номер проверки: {job.remoteId}</p>}</section>:<section className="panel empty" data-reveal><FileText size={30}/><h3>Отчёт не найден в этой сессии</h3><p>После перезагрузки вкладки локальный список очищается. Сохранённый JSON остаётся у вас.</p></section>}</>}
 {route.page==='sources'&&<section className="panel rules-page" data-reveal><div className="section-icon"><FileText size={23}/></div><h2>Правила из результатов анализа</h2><p>Каждый источник связан с конкретным событием. Неподтверждённые ссылки здесь не добавляются.</p>{sources.map(({event,job:j},i)=><div className="source-entry" key={`${j.id}-${i}`}><button className="rule-row" onClick={()=>setDialog({type:'rules',event})}><ShieldCheck size={20}/><span><strong>{event.rule!.document}</strong><small>{event.rule!.section||'Пункт не указан'} — {event.title}</small></span><ArrowUpRight size={16}/></button><button className="text-link" onClick={()=>openJob(j)}>Открыть {j.name}<ArrowRight size={14}/></button></div>)}{!sources.length&&<div className="empty"><span className="empty-icon"><FileText/></span><h3>Источники пока не предоставлены</h3><p>Они появятся, когда сервер вернёт правило вместе с событием. В разметке демонстрационных видео нормативных ссылок нет.</p></div>}</section>}
 {route.page==='connection'&&<ServiceConnection settings={settings} onSave={s=>{setSettings(s);setError('')}}/>}
 <div className="bottom-note"><ShieldCheck size={13}/><span>Результат — подсказка проверяющему. Окончательное решение принимает человек.</span></div>
 </div></main><input ref={input} aria-label="Выбрать MOV" type="file" hidden accept=".mov" multiple onChange={e=>upload(e.target.files)}/>
 {dialog?.type==='upload'&&<Modal title="Новая видеопроверка" onClose={()=>{setDialog(null);setDrag(false);dragDepth.current=0}}><p>Загрузите запись кассовой зоны. Формат MOV, до 250 МБ. Анализ занимает до 5 минут.</p>{settings.mode==='api'&&settings.apiKey?<div className={`upload-target ${drag?'dragging':''}`} onDragEnter={e=>{e.preventDefault();dragDepth.current++;setDrag(true)}} onDragOver={e=>e.preventDefault()} onDragLeave={e=>{e.preventDefault();if(--dragDepth.current<=0)setDrag(false)}} onDrop={e=>{e.preventDefault();dragDepth.current=0;setDrag(false);upload(e.dataTransfer.files)}}><UploadCloud size={38}/><strong>{drag?'Отпустите запись':'Перетащите видео сюда'}</strong><span>или выберите файл на устройстве</span><button className="primary" onClick={()=>input.current?.click()}>Выбрать MOV<ArrowRight size={16}/></button></div>:<div className="upload-connection"><Cable size={30}/><h3>Сначала подключите сервер</h3><p>Для анализа нужен API-ключ команды. Адрес можно оставить пустым — используется текущий сайт.</p><button className="primary" onClick={connection}>Настроить подключение<ArrowRight size={16}/></button></div>}{error&&<p className="error" role="alert">{error}</p>}</Modal>}
  {dialog?.type==='help'&&<Modal title="От записи — к важному моменту" onClose={()=>setDialog(null)}><p>Три простых шага для внимательной проверки.</p>{[['01','Загрузите запись','Выберите MOV или перетащите файл в область загрузки.'],['02','Дождитесь результата','В режиме API анализ выполняется на сервере команды, до 5 минут.'],['03','Проверьте детали','Откройте фрагмент, изучите кадры-доказательства и нормативный источник.']].map(([n,t,d])=><div className="help-step" key={n}><span>{n}</span><div><h3>{t}</h3><p>{d}</p></div></div>)}<div className="notice"><Info size={18}/>Результаты поступают от серверной модели. Для анализа подключите API.</div><div className="help-actions"><button className="text-link" onClick={connection}>Настройки подключения<ArrowUpRight size={14}/></button></div></Modal>}
  {dialog?.type==='rules'&&<Modal title="Правило проверки" onClose={()=>setDialog(null)}><span className="rule-category">{dialog.event.title}</span>{dialog.event.rule?<div className="source-card"><FileText size={24}/><h3>{dialog.event.rule.document}</h3><p>{dialog.event.rule.section||'Пункт не указан'}</p>{dialog.event.rule.url&&<a className="text-link" href={dialog.event.rule.url} target="_blank" rel="noreferrer">Открыть источник<ArrowUpRight size={15}/></a>}</div>:<div className="notice"><Info size={18}/>Нормативный источник пока не предоставлен. Вывод требует дополнительной проверки.</div>}<p>Это подсказка проверяющему, а не юридическое или дисциплинарное заключение.</p></Modal>}
  {dialog?.type==='player'&&<Modal title={dialog.job.name} className="player-modal" onClose={()=>setDialog(null)}><VideoPlayer job={dialog.job} event={dialog.event}/></Modal>}
  {dialog?.type==='evidence'&&<Modal title={`Кадр-доказательство — ${clock(dialog.time)}`} className="player-modal" onClose={()=>setDialog(null)}><img className="evidence" src={dialog.image} alt={`Кадр на ${clock(dialog.time)}`}/><a className="soft-button download-evidence" href={dialog.image} download={`evidence-${dialog.time}.jpg`}><ArrowDownToLine size={16}/>Скачать кадр</a></Modal>}
 </div>{booting&&<BrandIntro onFinish={finishStartup}/>}</>;
}
