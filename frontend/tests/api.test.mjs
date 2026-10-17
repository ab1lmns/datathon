import {test} from 'node:test';
import assert from 'node:assert/strict';
import {analyze,parseJob,validateVideo,safeSourceUrl,frameUrl} from '../src/api/client.ts';
const settings={baseUrl:'http://localhost:8000/',apiKey:'test-key',mode:'api'};
const event={type:'Проверить хранение',timecode_sec:9,description:'Описание наблюдаемого события',evidence_frames:[{timestamp_sec:9,image_base64:'/9j/test'}],rule:{document:'Документ',section:'Пункт',url:'https://adilet.zan.kz/example'}};
test('validates exact jury results, including multiple events and frames',()=>{
 assert.equal(parseJob({job_id:'a',status:'done',verdict:'violation',violations:[event,event]}).violations.length,2);
 assert.equal(parseJob({job_id:'a',status:'done',verdict:'no_violation',violations:[]}).verdict,'no_violation');
 assert.throws(()=>parseJob({job_id:'a',status:'done',verdict:'no_violation',violations:[event]}));
 assert.throws(()=>parseJob({job_id:'a',status:'done',verdict:'violation',violations:[]}));
 assert.throws(()=>parseJob({job_id:'a',status:'done',verdict:'violation',violations:[{...event,timecode_sec:-1}]}));
 assert.throws(()=>parseJob({job_id:'a',status:'done',verdict:'violation',violations:[{...event,evidence_frames:[]}]}));
});
test('MOV validation and safe source links',()=>{
 assert.equal(validateVideo({name:'video.MOV',size:29e6}),null);
 assert.ok(validateVideo({name:'video.mp4',size:100}));assert.ok(validateVideo({name:'video.mov',size:0}));
 assert.equal(safeSourceUrl('javascript:alert(1)'),undefined);assert.ok(frameUrl('/9j/test').startsWith('data:image/jpeg;base64,'));
});
test('uploads multipart file with API key then reads job result',async()=>{
 const previous=globalThis.fetch;const calls=[];
 globalThis.fetch=async(url,options)=>{calls.push({url,options});return new Response(JSON.stringify(calls.length===1?{job_id:'a/b'}:{job_id:'a/b',status:'done',verdict:'violation',violations:[event]}),{status:200})};
 try{const updates=[];await analyze(new File(['video'],'sample.mov'),settings,new AbortController().signal,j=>updates.push(j));assert.equal(calls[0].url,'http://localhost:8000/api/v1/analyze');assert.equal(calls[0].options.headers['X-API-Key'],'test-key');assert.equal(calls[0].options.body.get('file').name,'sample.mov');assert.equal(calls[1].url,'http://localhost:8000/api/v1/jobs/a%2Fb');assert.equal(updates.at(-1).status,'done')}finally{globalThis.fetch=previous}
});
test('HTTP failure never falls back to fake result',async()=>{const previous=globalThis.fetch;globalThis.fetch=async()=>new Response('',{status:401});try{await assert.rejects(analyze(new File(['x'],'x.mov'),settings,new AbortController().signal,()=>{}),/API-ключ/)}finally{globalThis.fetch=previous}});
test('rejects result belonging to another job',async()=>{const previous=globalThis.fetch;let count=0;globalThis.fetch=async()=>new Response(JSON.stringify(++count===1?{job_id:'a'}:{job_id:'b',status:'done',verdict:'no_violation',violations:[]}));try{await assert.rejects(analyze(new File(['x'],'x.mov'),settings,new AbortController().signal,()=>{}),/другой проверки/)}finally{globalThis.fetch=previous}});
test('cancels polling while processing',async()=>{const previous=globalThis.fetch;let count=0;globalThis.fetch=async()=>new Response(JSON.stringify(++count===1?{job_id:'a'}:{job_id:'a',status:'processing'}));const controller=new AbortController();try{await assert.rejects(analyze(new File(['x'],'x.mov'),settings,controller.signal,j=>{if(j.status==='processing'&&count===2)controller.abort()}),/Aborted/)}finally{globalThis.fetch=previous}});
