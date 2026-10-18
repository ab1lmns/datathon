import { useState, type CSSProperties } from 'react';
import { ArrowDownToLine, Info } from './Icons';
import { frameUrl } from '../api/client';
import { objectHistory } from '../api/evidence';
import type { EvidenceFrame, ReviewEvent } from '../api/types';
import { clock } from './ReviewDetail';

export function EvidenceInspector({frame,events,onFrame}:{frame:EvidenceFrame;events:ReviewEvent[];onFrame:(frame:EvidenceFrame)=>void}){
 const [selectedId,setSelectedId]=useState<string|null>(null);
 const objects=frame.objects||[];
 const selected=objects.find(o=>o.id===selectedId);
 const observations=selected?objectHistory(selected,events):[];
 const related=selected?events.filter(e=>e.frames.some(f=>f.objects?.some(o=>o.id===selected.id))):[];
 const frames=[...new Map(events.flatMap(e=>e.frames).map(f=>[f.timestamp_sec,f])).values()].sort((a,b)=>a.timestamp_sec-b.timestamp_sec);
 return <>
  <div className="evidence-inspector">
   <aside className="object-information" aria-label="Информация об объекте">
    <span className="overline">ОБЪЕКТЫ НА КАДРЕ</span>
    {objects.length?<><p className="object-hint">Наведите на рамку и нажмите на объект.</p><div className="object-picker">{objects.map(o=><button key={o.id} aria-pressed={selected?.id===o.id} onClick={()=>setSelectedId(o.id)}><i style={{background:o.color||'#a12a60'}}/>{o.name}</button>)}</div></>:<p className="object-hint">В этом результате рамки сохранены в изображении. Для выбора объектов нужен анализ обновлённой серверной версией.</p>}
    {selected?<div className="object-details" aria-live="polite">
     <h3>{selected.name}</h3><span className="object-state">{selected.state}</span><p className="field-hint">На кадре {clock(frame.timestamp_sec)}</p>
     <h4>Наблюдения по видео</h4>
     <ol className="object-history">{observations.map((point,i)=>{
      const evidence=frames.find(f=>Math.abs(f.timestamp_sec-point.timestamp_sec)<.051&&f.objects?.some(o=>o.id===selected.id));
      return <li key={`${point.timestamp_sec}-${i}`}><time>{clock(point.timestamp_sec)}</time><div><span>{point.state}</span>{evidence&&evidence!==frame&&<button className="text-link" onClick={()=>onFrame(evidence)}>Показать кадр</button>}</div></li>;
     })}</ol>
     {selected.kind==='person'&&<p className="field-hint">Это трек человека в этой записи. Роль определена моделью по положению в сцене.</p>}
     {!!related.length&&<div className="object-related"><h4>События в этих кадрах</h4>{related.map((e,i)=><p key={i}>{clock(e.time)} — {e.title}</p>)}<p className="field-hint">Совместное присутствие на кадре не устанавливает, кто совершил действие.</p></div>}
    </div>:objects.length>0&&<div className="object-placeholder"><Info size={23}/><p>Выберите сейф, человека или другой выделенный объект, чтобы увидеть сведения о нём.</p></div>}
   </aside>
   <div className="inspector-image-stage"><div className="inspector-image">
    <img className="inspected-frame" src={frameUrl(frame.image_base64)} alt={`Кадр на ${clock(frame.timestamp_sec)}`} />
    <div className="object-hotspots">{objects.map(o=><button key={o.id} className={`object-hotspot ${selected?.id===o.id?'selected':''}`} aria-label={`${o.name}: ${o.state}`} aria-pressed={selected?.id===o.id} title={`${o.name}: ${o.state}`} onClick={()=>setSelectedId(o.id)} style={{left:`${o.bbox[0]*100}%`,top:`${o.bbox[1]*100}%`,width:`${(o.bbox[2]-o.bbox[0])*100}%`,height:`${(o.bbox[3]-o.bbox[1])*100}%`,'--object-color':o.color||'#a12a60',zIndex:Math.round(1000-(o.bbox[2]-o.bbox[0])*(o.bbox[3]-o.bbox[1])*900)} as CSSProperties}><span>{o.name} · {o.state}</span></button>)}</div>
   </div></div>
  </div>
  <div className="inspector-footer"><span>{objects.length?`${objects.length} объектов на кадре`:'Исходный кадр анализа'}</span><a className="soft-button" href={frameUrl(frame.image_base64)} download={`evidence-${frame.timestamp_sec}.jpg`}><ArrowDownToLine size={16}/>Скачать кадр</a></div>
 </>;
}
