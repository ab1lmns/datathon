import { useEffect, useState } from 'react';
export type Page = 'overview' | 'reports' | 'sources' | 'connection';
export type Collection = 'attention' | 'clean' | 'processing' | 'failed';
export interface Route { page: Page; collection?: Collection; jobId?: string }
const pages = new Set(['overview','reports','sources','connection']);
const collections = new Set(['attention','clean','processing','failed']);
function readRoute(): Route {
 const [path, search=''] = location.hash.slice(1).split('?');
 const parts=path.split('/').filter(Boolean);
 const page=pages.has(parts[0])?parts[0] as Page:'overview';
 const query=new URLSearchParams(search);
 const collection=collections.has(query.get('folder')||'')?query.get('folder') as Collection:undefined;
 let jobId: string|undefined;
 try { if(page==='reports'&&parts[1])jobId=decodeURIComponent(parts[1]); } catch { /* Invalid URL opens the library. */ }
 return {page,collection,jobId};
}
export function useRoute(){
 const [route,setRoute]=useState<Route>(readRoute);
 useEffect(()=>{const sync=()=>setRoute(readRoute());window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync)},[]);
 function go(next:Route){
  const hash=`#/${next.page}${next.jobId?`/${encodeURIComponent(next.jobId)}`:''}${next.collection?`?folder=${next.collection}`:''}`;
  if(location.hash!==hash)history.pushState(null,'',hash);
  setRoute(next);
 }
 return {route,go};
}
