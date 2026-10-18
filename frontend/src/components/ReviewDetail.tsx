import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowDownToLine, ArrowLeft, ArrowRight, Check, FileText, Info, LoaderCircle, Play, RotateCcw, Video } from './Icons';
import { frameUrl } from '../api/client';
import type { ReviewEvent, ReviewJob } from '../api/types';

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
  job?: ReviewJob; onPlay: (event?: ReviewEvent) => void; onRule: (event: ReviewEvent) => void;
  onCancel: (id: string) => void; onRetry: (job: ReviewJob) => void; onSettings: () => void;
  onBack: () => void; onEvidence: (image: string, time: number) => void;
};

export function ReviewDetail({ job, onPlay, onRule, onCancel, onRetry, onSettings, onBack, onEvidence }: DetailProps) {
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
      <VideoPreview key={job.id} url={job.url} time={event?.time || 0} onPlay={() => onPlay(event)}/>
      {job.events.length > 1 && <div className="event-tabs" aria-label="События проверки">{job.events.map((item, i) => <button key={i} aria-pressed={index === i} className={index === i ? 'selected' : ''} onClick={() => setIndex(i)}>{clock(item.time)}<span>Событие {i + 1}</span></button>)}</div>}
      <div key={`${job.id}-${index}`} className="event-copy">
        <div className={`verdict ${job.status === 'clean' ? 'clean' : ''}`}>{job.status === 'clean' ? <Check size={14}/> : <AlertCircle size={14}/>}<span>{job.status === 'clean' ? 'Нарушение не обнаружено' : 'Обнаружены признаки возможных нарушений'}</span></div>
        <h3 className="event-title">{event?.title || 'Всё спокойно'}</h3>
        <p className="description">{event?.description || (job.demo ? 'В исходной разметке эта запись отмечена «без нарушения».' : 'По результатам анализа событий, требующих внимания, не обнаружено.')}</p>
      </div>
      {event?.rule?.reason&&<div className="notice"><Info size={18}/><span>Нормативная применимость требует проверки. {event.rule.reason}</span></div>}
      {!!event?.frames.length && <div className="evidence-section"><span className="overline">КАДРЫ-ДОКАЗАТЕЛЬСТВА</span><div className="evidence-strip">{event.frames.map((frame, i) => <button key={i} onClick={() => onEvidence(frameUrl(frame.image_base64), frame.timestamp_sec)}><img src={frameUrl(frame.image_base64)} alt={`Кадр ${i + 1} на ${clock(frame.timestamp_sec)}`}/><span>{clock(frame.timestamp_sec)}<ArrowDownToLine size={12}/></span></button>)}</div></div>}
      <div className="detail-actions"><button className="soft-button" onClick={() => onPlay(event)}>{event ? 'Открыть фрагмент' : 'Смотреть видео'}<ArrowRight size={16}/></button>{event && <button className="text-link" onClick={() => onRule(event)}><FileText size={14}/>Правило</button>}</div>
      <div className="human-note"><Info size={14}/><span>Вывод требует проверки человеком</span></div>
    </>}
  </div>;
}
export function VideoPlayer({job,event}:{job:ReviewJob;event?:ReviewEvent}){
 const video=useRef<HTMLVideoElement>(null);const [failed,setFailed]=useState(false),[frame,setFrame]=useState('');
 const time=event?.time||0;
 function capture(){const v=video.current;if(!v?.videoWidth)return;const canvas=document.createElement('canvas');canvas.width=v.videoWidth;canvas.height=v.videoHeight;canvas.getContext('2d')?.drawImage(v,0,0);setFrame(canvas.toDataURL('image/jpeg'))}
 return <><div className="player-video"><video ref={video} src={job.url} controls playsInline muted preload="metadata" onError={()=>setFailed(true)} onLoadedMetadata={()=>{if(video.current)video.current.currentTime=Math.min(time,Math.max(0,video.current.duration-.1))}} onSeeked={()=>{if(video.current&&Math.abs(video.current.currentTime-time)<.2)capture()}}/>{failed&&<div className="player-error"><Video/><p>Видео недоступно или кодек не поддерживается браузером. Кадры из результата API доступны в карточке проверки.</p></div>}</div><span className="player-time">{clock(time)} — {event?'Событие':'Начало записи'}</span><h3>{event?.title||'Нарушение не обнаружено'}</h3><p>{event?.description||'События, требующие внимания, не отмечены.'}</p>{frame&&event&&!event.frames.length&&<details><summary>Предпросмотр кадра — {clock(time)}</summary><img className="evidence" src={frame} alt={`Предпросмотр ${clock(time)}`}/><a className="text-link" href={frame} download={`${job.name}-preview.jpg`}><ArrowDownToLine size={15}/>Скачать кадр</a></details>}<div className="notice"><Info size={17}/>Результат — подсказка проверяющему, а не окончательное заключение.</div></>;
}
