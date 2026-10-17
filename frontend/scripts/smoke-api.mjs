// Real frontend-client E2E. No mocks. Supply a local MOV and secret via environment.
import {readFile} from 'node:fs/promises';
import {analyze,getHealth,TIMEOUT_MS} from '../src/api/client.ts';
const [filePath,baseUrl]=process.argv.slice(2);
if(!filePath||!baseUrl||!process.env.FORTE_TEST_API_KEY)throw new Error('Usage: FORTE_TEST_API_KEY=... node --experimental-strip-types scripts/smoke-api.mjs video.mov https://service');
const settings={mode:'api',baseUrl,apiKey:process.env.FORTE_TEST_API_KEY};
const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),TIMEOUT_MS);
try {
 const health=await getHealth(settings,controller.signal);
 if(!health.analysis_available)throw new Error('Worker not ready');
 const file=new File([await readFile(filePath)],'submission.mov',{type:'video/quicktime'});
 let final;const started=performance.now();
 await analyze(file,settings,controller.signal,result=>{final=result});
 if(final?.status!=='done')throw new Error(`Analysis ended: ${final?.status}`);
 console.log(JSON.stringify({status:final.status,verdict:final.verdict,event_count:final.violations.length,rule_links:final.violations.every(v=>!!v.rule?.url),wall_sec:+((performance.now()-started)/1000).toFixed(2)}));
} finally {clearTimeout(timer)}
