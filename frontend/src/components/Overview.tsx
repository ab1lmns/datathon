import { ArrowRight, Check, Clock3, FileText, Video } from './Icons';
import type { ReviewJob, Settings } from '../api/types';
import { JobStatus } from './ReportLibrary';
import { clock } from './ReviewDetail';
export function Overview({jobs,settings,onOpen,onConnection}:{jobs:ReviewJob[];settings:Settings;onOpen:(job:ReviewJob)=>void;onConnection:()=>void}){
 const done=jobs.filter(j=>j.status==='clean'||j.status==='attention');
 const events=jobs.flatMap(job=>job.events.map(event=>({job,event})));
 return <>
 <section className="overview-metrics" aria-label="Сводка сессии" data-reveal>{[{Icon:Video,label:'Загружено видео',value:jobs.length},{Icon:Clock3,label:'В обработке',value:jobs.filter(j=>j.status==='processing').length},{Icon:Check,label:'Готовых отчётов',value:done.length},{Icon:FileText,label:'Событий для проверки',value:events.length}].map(({Icon,label,value})=><div className="metric" key={label}><Icon size={18}/><span>{label}</span><strong>{value.toString().padStart(2,'0')}</strong></div>)}</section>
 <div className="overview-columns">
 <section className="panel activity-panel" data-reveal><div className="panel-heading"><div><h2>Последние проверки</h2><p>{settings.mode==='demo'?'Примеры из разметки датасета':'Записи текущей сессии'}</p></div></div>
 {jobs.slice(0,5).map(job=><button key={job.id} className="activity-row" onClick={()=>onOpen(job)}><span className="file-icon"><Video size={19}/></span><span className="activity-name"><strong>{job.name}</strong><small>{job.demo?'Разметка датасета':job.time}</small></span><JobStatus job={job}/><ArrowRight size={15}/></button>)}
 {!jobs.length&&<div className="onboarding"><span className="overline">ПЕРВАЯ ПРОВЕРКА</span><h3>От записи к понятному результату</h3><ol><li><strong>Загрузите MOV</strong><span>Одна кнопка вверху, до 200 МБ.</span></li><li><strong>Дождитесь анализа</strong><span>Статус обновляется автоматически.</span></li><li><strong>Откройте видеоотчёт</strong><span>События, таймкоды, кадры и правила.</span></li></ol></div>}
 </section>
 <section className="panel attention-panel" data-reveal><div className="panel-heading"><div><h2>На что обратить внимание</h2><p>Переход сразу к записи с событием</p></div></div>{events.slice(0,4).map(({job,event},i)=><button key={`${job.id}-${i}`} className="attention-event" onClick={()=>onOpen(job)}><span className="event-time">{clock(event.time)}</span><span><strong>{event.title}</strong><small>{job.name} / {job.demo?'отметка датасета':'результат анализа'}</small></span><ArrowRight size={15}/></button>)}{!events.length&&<div className="overview-empty"><Check size={28}/><h3>Событий пока нет</h3><p>Здесь появятся моменты, которые нужно просмотреть после анализа.</p></div>}
 <div className="session-note"><strong>{settings.mode==='demo'?'Вы смотрите примеры':'Работа в текущей сессии'}</strong><p>{settings.mode==='demo'?'Это исходная разметка, а не вывод модели. Для своей записи подключите сервер.':'Отчёты доступны до перезагрузки вкладки. Готовый результат можно скачать из отчёта.'}</p>{settings.mode==='demo'&&<button className="text-link" onClick={onConnection}>Подключить сервер<ArrowRight size={14}/></button>}</div>
 </section></div></>;
}
