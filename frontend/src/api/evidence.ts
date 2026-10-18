import type { EvidenceObject, ObjectObservation, ReviewEvent } from './types.ts';

const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object';
const time=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
export function parseObjects(value:unknown):EvidenceObject[]|undefined{
 if(!Array.isArray(value))return undefined;
 const ids=new Set<string>();
 return value.filter(record).flatMap(o=>{
  if(typeof o.id!=='string'||!o.id||ids.has(o.id)||typeof o.name!=='string'||typeof o.kind!=='string'||typeof o.state!=='string'||!Array.isArray(o.bbox)||o.bbox.length!==4||!o.bbox.every(n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=1))return [];
  const [x1,y1,x2,y2]=o.bbox as number[];
  if(x2<=x1||y2<=y1)return [];
  ids.add(o.id);
  const history=Array.isArray(o.history)?o.history.filter(record).filter(h=>time(h.timestamp_sec)&&typeof h.state==='string').map(h=>({timestamp_sec:h.timestamp_sec as number,state:h.state as string})):undefined;
  return [{id:o.id,name:o.name,kind:o.kind,state:o.state,bbox:[x1,y1,x2,y2] as [number,number,number,number],color:typeof o.color==='string'&&/^#[0-9a-f]{6}$/i.test(o.color)?o.color:undefined,history}];
 });
}

export function objectHistory(object:EvidenceObject,events:ReviewEvent[]):ObjectObservation[]{
 const points=[...(object.history||[])];
 for(const event of events)for(const frame of event.frames){
  const match=frame.objects?.find(o=>o.id===object.id);
  if(match){points.push({timestamp_sec:frame.timestamp_sec,state:match.state});points.push(...(match.history||[]))}
 }
 return [...new Map(points.sort((a,b)=>a.timestamp_sec-b.timestamp_sec).map(p=>[p.timestamp_sec,p])).values()];
}
