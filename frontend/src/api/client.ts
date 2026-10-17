import type { JobResponse, Settings, Violation } from './types';
export const TIMEOUT_MS = 300_000;
export const POLL_MS = 2_000;
export function validateVideo(file: Pick<File, 'name'|'size'>): string | null {
 if (!/\.mov$/i.test(file.name)) return 'По ТЗ принимаются видео в формате .MOV.';
 if (!file.size) return 'Файл пустой. Выберите другую запись.';
 if (file.size > 250 * 1024 * 1024) return 'Файл больше 250 МБ — лимит интерфейса.';
 return null;
}
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object';
const seconds = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0;
export function parseJob(value: unknown): JobResponse {
 if (!record(value) || typeof value.job_id !== 'string' || !value.job_id) throw new Error('API: отсутствует job_id.');
 if(value.status === 'processing') return {job_id:value.job_id,status:'processing',progress:seconds(value.progress)?Math.min(100,value.progress):undefined};
 if(value.status === 'failed') return {job_id:value.job_id,status:'failed',error:typeof value.error==='string'?value.error:undefined};
 if(value.status !== 'done' || !['violation','no_violation'].includes(String(value.verdict)) || !Array.isArray(value.violations)) throw new Error('API: неверный формат результата.');
 const violations: Violation[] = value.violations.map(v=>{
  if(!record(v)||typeof v.type!=='string'||!seconds(v.timecode_sec)||typeof v.description!=='string'||!Array.isArray(v.evidence_frames)||v.evidence_frames.length<1||v.evidence_frames.length>3) throw new Error('API: событие должно содержать тип, таймкод, описание и 1–3 кадра.');
  const frames=v.evidence_frames.map(f=>{if(!record(f)||!seconds(f.timestamp_sec)||typeof f.image_base64!=='string'||!f.image_base64)throw new Error('API: неверный кадр-доказательство.');return {timestamp_sec:f.timestamp_sec,image_base64:f.image_base64}});
  const rule=record(v.rule)&&typeof v.rule.document==='string'?{document:v.rule.document,section:typeof v.rule.section==='string'?v.rule.section:undefined,url:typeof v.rule.url==='string'?safeSourceUrl(v.rule.url):undefined}:undefined;
  return {type:v.type,timecode_sec:v.timecode_sec,description:v.description,evidence_frames:frames,rule};
 });
 if((value.verdict==='no_violation'&&violations.length)||(value.verdict==='violation'&&!violations.length))throw new Error('API: вердикт противоречит списку событий.');
 return {job_id:value.job_id,status:'done',verdict:value.verdict as 'violation'|'no_violation',violations};
}
export function safeSourceUrl(raw: string): string | undefined {try {const url=new URL(raw);return ['https:','http:'].includes(url.protocol)?url.href:undefined}catch{return undefined}}
export function frameUrl(base64: string){return `data:image/jpeg;base64,${base64.replace(/^data:image\/jpeg;base64,/, '')}`}
async function request(settings: Settings, path: string, signal: AbortSignal, body?: FormData): Promise<unknown> {
 const headers: Record<string,string>={Accept:'application/json'};
 if(settings.apiKey)headers['X-API-Key']=settings.apiKey;
 let response: Response;
 try {response=await fetch(`${settings.baseUrl.replace(/\/$/,'')}${path}`,{method:body?'POST':'GET',body,headers,signal})}
 catch(e){if(signal.aborted)throw e;throw new Error('Нет соединения с API. Проверьте адрес сервера и CORS.');}
 if(!response.ok){const messages:Record<number,string>={401:'Неверный API-ключ.',403:'Доступ запрещён. Проверьте API-ключ.',413:'Сервер отклонил размер файла.',415:'Сервер не поддерживает этот формат видео.',422:'Сервер не принял видео. Ожидается multipart-поле file.',429:'Слишком много запросов. Повторите позже.'};throw new Error(messages[response.status]||`Ошибка сервера (${response.status}).`)}
 try{return await response.json()}catch{throw new Error('API вернул ответ не в формате JSON.')}
}
export async function analyze(file: File, settings: Settings, signal: AbortSignal, onUpdate: (job: JobResponse)=>void) {
 const data=new FormData();data.append('file',file);
 const created=await request(settings,'/api/v1/analyze',signal,data);
 if(!record(created)||typeof created.job_id!=='string'||!created.job_id)throw new Error('API не вернул job_id после загрузки.');
 const id=created.job_id;
 onUpdate({job_id:id,status:'processing'});
 while(!signal.aborted){
  const result=parseJob(await request(settings,`/api/v1/jobs/${encodeURIComponent(id)}`,signal));
  if(result.job_id!==id)throw new Error('API вернул результат другой проверки.');
  onUpdate(result);if(result.status!=='processing')return;
  await new Promise<void>((resolve,reject)=>{const abort=()=>{clearTimeout(timer);reject(new DOMException('Aborted','AbortError'))};const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve()},POLL_MS);signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort()});
 }
}
