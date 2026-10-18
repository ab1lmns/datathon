import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseJob } from '../src/api/client.ts';
import { parseObjects, objectHistory } from '../src/api/evidence.ts';

const safe={id:'scene:safe',kind:'safe',name:'Сейф',state:'закрыт',bbox:[.6,.3,.9,.8],color:'#00c8c8'};
test('object regions reject invalid coordinates, duplicate IDs and unsafe colors',()=>{
 const parsed=parseObjects([safe,{...safe},{...safe,id:'bad',bbox:[.9,0,.2,1]},{...safe,id:'nan',bbox:[0,0,NaN,1]},{...safe,id:'color',color:'url(evil)'}]);
 assert.equal(parsed.length,2);assert.equal(parsed[1].color,undefined);
 assert.equal(parseObjects(null),undefined);
});
test('API retains optional objects without changing old frame contract',()=>{
 const response=frames=>({job_id:'a',status:'done',verdict:'violation',violations:[{type:'Сейф',timecode_sec:5,description:'Открыт',evidence_frames:frames}]});
 const old={timestamp_sec:1,image_base64:'jpeg'};
 assert.deepEqual(parseJob(response([old])).violations[0].evidence_frames[0],old);
 const frame=parseJob(response([{...old,objects:[safe]}])).violations[0].evidence_frames[0];
 assert.equal(frame.objects[0].id,'scene:safe');
});
test('history merges chronological observations only for the same object',()=>{
 const person={...safe,id:'person:1',kind:'person',state:'Виден на кадре'};
 const events=[{frames:[{timestamp_sec:10,objects:[{...safe,state:'открыт'},person]},{timestamp_sec:1,objects:[safe]}]}];
 assert.deepEqual(objectHistory({...safe,history:[{timestamp_sec:5,state:'открыт'}]},events),[{timestamp_sec:1,state:'закрыт'},{timestamp_sec:5,state:'открыт'},{timestamp_sec:10,state:'открыт'}]);
 assert.deepEqual(objectHistory(person,events),[{timestamp_sec:10,state:'Виден на кадре'}]);
});
