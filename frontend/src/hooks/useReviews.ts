import { useEffect, useRef, useState } from 'react';
import { analyze, TIMEOUT_MS, validateVideo } from '../api/client';
import type { ReviewJob, Settings } from '../api/types';
const annotated = (time:number) => ({title:'Событие из разметки',time,description:'В разметке отмечено нарушение. Тип события и нормативное основание пока не указаны.',frames:[]});
export const samples: ReviewJob[] = [
 {id:'sample-26',name:'Х-26.mov',status:'attention',time:'Разметка датасета — 00:09',url:'/demo/x-26.mov',events:[annotated(9)],demo:true},
 {id:'sample-3',name:'Х-3.mov',status:'clean',time:'Разметка датасета',url:'/demo/x-3.mov',events:[],demo:true},
 {id:'sample-20',name:'Х-20.mov',status:'attention',time:'Разметка датасета — 00:05',url:'/demo/x-20.mov',events:[annotated(5)],demo:true},
];
export function useReviews(settings:Settings){
 const [jobs,setJobs]=useState<ReviewJob[]>(samples);const controllers=useRef(new Map<string,AbortController>());const urls=useRef<string[]>([]);
 useEffect(()=>()=>{controllers.current.forEach(c=>c.abort());urls.current.forEach(URL.revokeObjectURL)},[]);
 function patch(id:string,fields:Partial<ReviewJob>){setJobs(prev=>prev.map(j=>j.id===id?{...j,...fields}:j))}
 async function run(job:ReviewJob){
  if(!job.file)return;const controller=new AbortController();controllers.current.set(job.id,controller);
  let expired=false;const timer=setTimeout(()=>{expired=true;controller.abort()},TIMEOUT_MS);
  patch(job.id,{status:'processing',error:undefined,progress:undefined,events:[]});
  try{
   if(settings.mode==='demo'){
    await new Promise<void>((resolve,reject)=>{const t=setTimeout(resolve,1800);controller.signal.addEventListener('abort',()=>{clearTimeout(t);reject(new DOMException('Aborted','AbortError'))},{once:true})});
    // Never fabricate a verdict for an arbitrary uploaded file, even in demo mode.
    patch(job.id,{status:'failed',error:'Демо завершено. Для анализа вашей записи подключите API в настройках. Готовые примеры доступны в списке.'});
   }else await analyze(job.file,settings,controller.signal,result=>{
    if(result.status==='done')patch(job.id,{remoteId:result.job_id,status:result.verdict==='violation'?'attention':'clean',events:result.violations.map(v=>({title:v.type,time:v.timecode_sec,description:v.description,frames:v.evidence_frames,rule:v.rule})),progress:100});
    else if(result.status==='failed')patch(job.id,{remoteId:result.job_id,status:'failed',error:result.error||'Сервер не смог обработать запись.'});
    else patch(job.id,{remoteId:result.job_id,progress:result.progress});
   });
  }catch(e){patch(job.id,{status:'failed',error:expired?'Превышено время ожидания — 5 минут.':controller.signal.aborted?'Ожидание отменено. Серверная обработка могла продолжиться.':e instanceof Error?e.message:'Не удалось обработать видео.'})}
  finally{clearTimeout(timer);controllers.current.delete(job.id)}
 }
 function upload(files:FileList|null){const errors:string[]=[];const added:ReviewJob[]=[];for(const file of Array.from(files||[])){const error=validateVideo(file);if(error){errors.push(`${file.name}: ${error}`);continue}const url=URL.createObjectURL(file);urls.current.push(url);added.push({id:crypto.randomUUID(),name:file.name,status:'processing',time:new Date().toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}),url,events:[],demo:settings.mode==='demo',file})}setJobs(p=>[...added,...p]);added.forEach(j=>void run(j));return {id:added[0]?.id,error:errors.join(' ')}}
 return {jobs:jobs.filter(j=>j.demo===(settings.mode==='demo')),upload,cancel:(id:string)=>controllers.current.get(id)?.abort(),retry:(job:ReviewJob)=>{patch(job.id,{demo:settings.mode==='demo'});void run(job)}};
}
