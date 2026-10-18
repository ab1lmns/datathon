import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowDownToLine, ArrowLeft, ArrowUpRight, Check, FileText, Info, LoaderCircle, Play, RotateCcw, Video } from './Icons';
import { ReviewVideo } from './ReviewVideo';
import { frameUrl } from '../api/client';
import type { EvidenceFrame, ReviewEvent, ReviewJob } from '../api/types';

export const clock = (sec: number) => `${Math.floor(sec / 60).toString().padStart(2,'0')}:${Math.floor(sec % 60).toString().padStart(2,'0')}`;

export function VideoPreview({ url, time, onPlay }: { url: string; time: number; onPlay: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false), [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const element = video.current;
    if (element && element.readyState >= 1) element.currentTime = Math.min(time, Math.max(0, element.duration - .1));
  }, [time]);
  return <div className="preview">
      <video ref={video} src={url} muted playsInline preload="auto"
        onLoadedData={() => setLoaded(true)} onSeeked={() => setLoaded(true)}
        onLoadedMetadata={() => {
          const element = video.current;
          if (!element) return;
          element.currentTime = Math.min(time, Math.max(0, element.duration - .1));
        }} onError={() => setFailed(true)}/>
      {!loaded && !failed && <div className="video-loading"><LoaderCircle size={17} className="spin" aria-hidden="true"/><span>Загрузка записи</span></div>}
      {failed ? <div className="media-fallback"><Video size={28}/><strong>Нет предпросмотра</strong><span>Файл недоступен или кодек не поддерживается.</span></div> : <button className="preview-play" aria-label="Воспроизвести фрагмент" onClick={onPlay}><Play size={20} fill="currentColor"/></button>}
      <span className="preview-caption">ИСХОДНАЯ ЗАПИСЬ</span><span className="time-chip">{clock(time)}</span>
  </div>;
}

type DetailProps = {
  job?: ReviewJob;
  onCancel: (id: string) => void; onRetry: (job: ReviewJob) => void; onSettings: () => void;
  onBack: () => void; onEvidence: (frame: EvidenceFrame) => void;
};

export function ReviewDetail({ job, onCancel, onRetry, onSettings, onBack, onEvidence }: DetailProps) {
  const [index, setIndex] = useState(0);
  const event = job?.events[index] || job?.events[0];
  if (!job) return <div className="empty detail-empty"><span className="empty-icon"><Video/></span><h3>Здесь будет результат</h3><p>Загрузите видео или выберите проверку из списка.</p></div>;
  return <div className="detail-content">
    <button className="mobile-back" onClick={onBack}><ArrowLeft size={16}/>К проверкам</button>
    <div className="detail-heading"><div><span className="overline">ВЫБРАННАЯ ПРОВЕРКА</span><h2 title={job.name}>{job.name}</h2></div><span className="tiny-demo">{job.demo ? 'Датасет' : 'API'}</span></div>
    {job.status === 'processing' ? <div className="processing-state">
      <div className="scanner"><Video size={28}/><span/></div><h3>Изучаем запись</h3>
      <p>{job.demo ? 'Предпросмотр процесса без AI' : 'Ожидаем ответ сервера — до 5 минут'}</p>
      <div className={`big-progress ${job.progress === undefined ? 'indeterminate' : ''}`} role="progressbar" aria-label="Обработка видео" aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100}><i style={{width:`${job.progress ?? 35}%`}}/></div>
      <span className="processing-caption">{job.progress === undefined ? 'Проверка выполняется…' : `${Math.round(job.progress)}%`}</span><button className="text-link" onClick={() => onCancel(job.id)}>Отменить ожидание</button>
    </div> : job.status === 'failed' ? <div className="processing-state"><span className="empty-icon error-icon"><AlertCircle/></span><h3>Проверка не завершена</h3><p role="alert">{job.error}</p><div className="state-actions"><button className="soft-button" onClick={() => onRetry(job)}><RotateCcw size={15}/>Повторить</button><button className="text-link" onClick={onSettings}>Подключение API</button></div></div> : <>
      <ReviewVideo key={job.id} job={job} index={index} onSelect={setIndex}/>

      <div key={`${job.id}-${index}`} className="event-copy">
        <div className={`verdict ${job.status === 'clean' ? 'clean' : ''}`}>{job.status === 'clean' ? <Check size={14}/> : <AlertCircle size={14}/>}<span>{job.status === 'clean' ? 'Нарушение не обнаружено' : 'Обнаружены признаки возможных нарушений'}</span></div>
        <h3 className="event-title">{event?.title || 'Всё спокойно'}</h3>
        <p className="description">{event?.description || (job.demo ? 'В исходной разметке эта запись отмечена «без нарушения».' : 'По результатам анализа событий, требующих внимания, не обнаружено.')}</p>
      </div>
      {!!event?.frames.length && <div className="evidence-section"><span className="overline">КАДРЫ-ДОКАЗАТЕЛЬСТВА</span><div className="evidence-strip">{event.frames.map((frame, i) => <button key={i} onClick={() => onEvidence(frame)}><img src={frameUrl(frame.image_base64)} alt={`Кадр ${i + 1} на ${clock(frame.timestamp_sec)}`}/><span>{clock(frame.timestamp_sec)}<ArrowDownToLine size={12}/></span></button>)}</div></div>}
      {event && <section className="report-rule" aria-label="Правило проверки">
        <h3><FileText size={17}/>Правило проверки</h3>
        {event.rule ? <>
          <h4>{event.rule.document}</h4>
          {event.rule.section && <p>{event.rule.section}</p>}
          {event.rule.reason && <p className="rule-applicability"><strong>{event.rule.relation === 'RELATED_ONLY' ? 'Связанное требование, не прямое основание. ' : event.rule.relation === 'NO_DIRECT_BASIS' ? 'Прямое основание не установлено. ' : 'Условия применения. '}</strong>{event.rule.reason}</p>}
          {event.rule.sources?.map((source, i) => <div className="report-rule-source" key={i}>
            <p>{source.document}{source.section && ` — ${source.section}`}</p>
            {source.quote && <blockquote>{source.quote}</blockquote>}
            {source.url && <a className="text-link" href={source.url} target="_blank" rel="noreferrer">Официальный источник</a>}
          </div>)}
          {!!event.rule.unknown_conditions?.length && <div className="rule-conditions"><p>Требует подтверждения</p><ul>{event.rule.unknown_conditions.map(condition => <li key={condition.id}>{condition.text}</li>)}</ul></div>}
          {event.rule.checked_at && <p className="field-hint">{event.rule.source_verification === 'OFFICIAL_TEXT_VERIFIED' ? 'Цитата сверена с официальным текстом' : 'Дата проверки, заявленная автором нормативного пакета'}: {event.rule.checked_at}</p>}
          {event.rule.url && <a className="source-link" href={event.rule.url} target="_blank" rel="noreferrer"><FileText size={19}/>Открыть источник<ArrowUpRight size={19}/></a>}
        </> : <p>Нормативный источник пока не предоставлен.</p>}
      </section>}
      <div className="human-note"><Info size={14}/><span>Вывод требует проверки человеком</span></div>
    </>}
  </div>;
}
export function VideoPlayer({job,event}:{job:ReviewJob;event?:ReviewEvent}){
 const [index,setIndex]=useState(Math.max(0,event?job.events.indexOf(event):0));
 const selected=job.events[index];
 return <><ReviewVideo job={job} index={index} onSelect={setIndex}/><h3>{selected?.title||'Просмотр исходной записи'}</h3><p>{selected?.description||'События, требующие внимания, не отмечены.'}</p><div className="notice"><Info size={17}/>Результат — подсказка проверяющему, а не окончательное заключение.</div></>;
}
