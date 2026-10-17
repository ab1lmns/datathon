import { AlertCircle, ArrowLeft, ArrowUpRight, Check, Clock3, FileText, Folder, LoaderCircle, Search, Video } from './Icons';
import type { ReviewJob } from '../api/types';
import type { Collection } from '../hooks/useRoute';
import { FolderCard } from './FolderCard';
export const collectionNames:Record<Collection,string>={attention:'Требуют внимания',clean:'Без нарушений',processing:'В обработке',failed:'Не завершены'};
export function JobStatus({job}:{job:ReviewJob}){
 const Icon=job.status==='clean'?Check:job.status==='processing'?LoaderCircle:AlertCircle;
 return <span className={`status ${job.status}`}><Icon size={13} className={job.status==='processing'?'spin':''}/>{job.status==='processing'?(job.progress===undefined?'В обработке':`${Math.round(job.progress)}%`):job.status==='failed'?'Не завершена':job.status==='clean'?'Без нарушений':'Требует внимания'}</span>;
}
export function ReportLibrary({jobs,collection,query,onFolder,onOpen,onBack}:{jobs:ReviewJob[];collection?:Collection;query:string;onFolder:(folder:Collection,source:HTMLButtonElement)=>void;onOpen:(job:ReviewJob)=>void;onBack:()=>void}){
 const visible=jobs.filter(j=>(!collection||j.status===collection)&&j.name.toLowerCase().includes(query.toLowerCase()));
 return <>
 {!collection&&!query&&<><div className="section-label" data-reveal><h2>Папки отчётов</h2><span className="data-label">Текущая сессия</span></div><section className="folders" aria-label="Папки отчётов">{([{id:'attention',color:'coral',Icon:AlertCircle,sub:'проверить события'},{id:'clean',color:'cream',Icon:Check,sub:'готовые результаты'},{id:'processing',color:'wine',Icon:Clock3,sub:'ожидают результата'},{id:'failed',color:'pink',Icon:FileText,sub:'нужен повтор'}] as const).map(({id,color,Icon,sub},i)=><FolderCard key={id} title={collectionNames[id]} value={jobs.filter(j=>j.status===id).length} subtitle={sub} Icon={Icon} color={color} order={i} selected={false} onClick={source=>onFolder(id,source)}/>)}</section></>}
 <section className={`panel library ${collection?'opened-folder':''}`} data-reveal>
 <div className="library-heading">{collection?<button className="text-link" onClick={onBack}><ArrowLeft size={15}/>Все папки</button>:<span className="overline">{query?'РЕЗУЛЬТАТЫ ПОИСКА':'ВСЕ ВИДЕООТЧЁТЫ'}</span>}<span className="data-label">{visible.length} записей</span></div>
 {collection&&<h2 className="opened-folder-title"><Folder size={22}/>{collectionNames[collection]}</h2>}
 <div className="report-grid">{visible.map(j=><button key={j.id} className="report-card" onClick={()=>onOpen(j)}><div className="report-card-top"><span className="report-file-icon"><Video size={22}/></span><ArrowUpRight size={17}/></div><strong>{j.name}</strong><span className="report-meta">{j.demo?'Пример из датасета':j.time}</span><JobStatus job={j}/><div className="report-card-footer"><span>{j.status==='processing'?'Анализ выполняется':j.status==='failed'?'Открыть подробности':`${j.events.length} событий`}</span><span>Открыть отчёт →</span></div></button>)}</div>
 {!visible.length&&<div className="empty"><span className="empty-icon">{query?<Search/>:<Folder/>}</span><h3>{query?'Ничего не найдено':'В папке пока нет записей'}</h3><p>{query?'Попробуйте другое название.':'Загруженные видео распределятся по папкам после начала обработки.'}</p></div>}
 </section></>;
}
