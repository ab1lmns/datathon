import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowDownToLine, Camera, Repeat2, RotateCcw, RotateCw, Video } from './Icons';
import type { ReviewJob } from '../api/types';

const clock=(time:number)=>`${Math.floor(time/60).toString().padStart(2,'0')}:${Math.floor(time%60).toString().padStart(2,'0')}`;
export function ReviewVideo({job,index=0,onSelect}:{job:ReviewJob;index?:number;onSelect?:(index:number)=>void}){
 const video=useRef<HTMLVideoElement>(null);
 const [duration,setDuration]=useState(0),[position,setPosition]=useState(0),[speed,setSpeed]=useState('1'),[loop,setLoop]=useState(false),[error,setError]=useState(''),[seeking,setSeeking]=useState(false),[snapshot,setSnapshot]=useState<{url:string;time:number}|null>(null);
 const event=job.events[index];
 const start=Math.max(0,(event?.time||0)-3),end=Math.min(duration,(event?.time||0)+3);
 function seek(time:number){const v=video.current;if(!v||!Number.isFinite(v.duration))return;const next=Math.max(0,Math.min(time,Math.max(0,v.duration-.04)));v.currentTime=next;setPosition(next)}
 useEffect(()=>{seek(event?.time||0)},[index,job.id,event?.time]);
 function update(){const v=video.current;if(!v)return;if(loop&&event&&end>start&&(v.currentTime>=end||v.currentTime<start-.1)){v.currentTime=start;setPosition(start)}else setPosition(v.currentTime)}
 function toggleLoop(){const enabled=!loop;setLoop(enabled);if(enabled)seek(start)}
 function capture(){
  const v=video.current;if(!v?.videoWidth||v.seeking||v.readyState<2)return;
  try{const canvas=document.createElement('canvas');canvas.width=v.videoWidth;canvas.height=v.videoHeight;canvas.getContext('2d')?.drawImage(v,0,0);setSnapshot({url:canvas.toDataURL('image/jpeg',.94),time:v.currentTime});setError('')}
  catch{setError('Сервер видео не разрешил сохранить кадр. Кадры из анализа доступны в отчёте.')}
 }
 return <div className="review-player">
 <div className="review-video-stage"><video ref={video} src={job.url} controls playsInline muted preload="metadata" onLoadedMetadata={()=>{const v=video.current;if(v&&Number.isFinite(v.duration)){setDuration(v.duration);v.playbackRate=Number(speed);seek(event?.time||0)}}} onSeeking={()=>setSeeking(true)} onSeeked={()=>setSeeking(false)} onTimeUpdate={update} onEnded={()=>{if(loop&&event){seek(start);void video.current?.play().catch(()=>{})}}} onError={()=>setError('Не удалось открыть видео. Проверьте файл или поддержку кодека в браузере.')}/>{!duration&&<span className="video-source-label"><Video size={13}/>Исходная запись</span>}</div>
 <div className="video-timeline"><div className="timeline-clock"><span>{clock(position)} <span>/ {clock(duration)}</span></span><span>{job.demo?'Локальный пример':'Исходное видео'}</span></div><div className="timeline-track">
 {loop&&event&&duration>0&&<span className="loop-region" style={{left:`${start/duration*100}%`,width:`${(end-start)/duration*100}%`}}/>}
 <input aria-label="Позиция видео" type="range" min="0" max={duration||0} step="0.04" disabled={!duration} value={position} onChange={e=>{setLoop(false);seek(Number(e.target.value))}}/>
 {duration>0&&job.events.map((item,i)=><button key={i} className={`timeline-marker ${index===i?'selected':''}`} style={{left:`${Math.min(99,Math.max(1,item.time/duration*100))}%`}} title={`${clock(item.time)} — ${item.title}`} aria-label={`Событие ${i+1} на ${clock(item.time)}`} aria-pressed={index===i} onClick={()=>{onSelect?.(i);seek(item.time)}}><span/></button>)}
 </div></div>
 <div className="video-tools"><div className="seek-tools"><button title="Назад на 1 секунду" aria-label="Назад на 1 секунду" onClick={()=>seek(position-1)} disabled={!duration}><RotateCcw size={16}/><span>1 с</span></button><button title="Вперёд на 1 секунду" aria-label="Вперёд на 1 секунду" onClick={()=>seek(position+1)} disabled={!duration}><RotateCw size={16}/><span>1 с</span></button></div><label className="speed-control"><span className="sr-only">Скорость воспроизведения</span><select aria-label="Скорость воспроизведения" value={speed} onChange={e=>{setSpeed(e.target.value);if(video.current)video.current.playbackRate=Number(e.target.value)}}>{['0.25','0.5','1','1.5','2'].map(value=><option key={value} value={value}>{value}×</option>)}</select></label><button className={loop?'tool-active':''} disabled={!duration||!event} aria-pressed={loop} onClick={toggleLoop} title={event?'Повторять 3 секунды до и после события':'Повтор доступен для записи с событием'}><Repeat2 size={16}/><span>Повтор</span></button><button onClick={capture} disabled={!duration||seeking}><Camera size={16}/><span>Кадр</span></button></div>
 {loop&&event&&<p className="loop-caption" role="status">Повтор фрагмента {clock(start)}–{clock(end)}. Нажмите ▶ на видео.</p>}
 {!!job.events.length&&<div className="player-event-list" aria-label="Моменты на видео">{job.events.map((item,i)=><button key={i} className={index===i?'selected':''} aria-pressed={index===i} onClick={()=>{onSelect?.(i);seek(item.time)}}><span>{clock(item.time)}</span>{item.title}</button>)}</div>}
 {error&&<p className="player-notice" role="alert"><AlertCircle size={15}/>{error}</p>}
 {snapshot&&<div className="snapshot-result"><div><strong>Кадр исходного видео · {clock(snapshot.time)}</strong><button onClick={()=>setSnapshot(null)} aria-label="Закрыть предпросмотр кадра">Закрыть</button></div><img src={snapshot.url} alt={`Кадр исходного видео на ${clock(snapshot.time)}`}/><a className="text-link" href={snapshot.url} download={`${job.name}-${snapshot.time.toFixed(2)}s.jpg`}><ArrowDownToLine size={14}/>Скачать JPEG</a><p>Сохранён вручную из плеера, не является отдельным доказательством модели.</p></div>}
 </div>;
}
