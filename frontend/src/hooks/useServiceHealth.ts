import { useCallback, useEffect, useState } from 'react';
import { getHealth, type ServiceHealth } from '../api/client';
import type { Settings } from '../api/types';
export function useServiceHealth(settings:Settings){
 const [state,setState]=useState<{loading:boolean;data?:ServiceHealth;error?:string}>({loading:true});
 const [version,setVersion]=useState(0);
 useEffect(()=>{
  let active=true;
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),6000);
  setState({loading:true});
  getHealth(settings,controller.signal).then(data=>{if(active)setState({loading:false,data})}).catch(e=>{if(!active)return;if(!controller.signal.aborted)setState({loading:false,error:e.message});else setState({loading:false,error:'Сервер не ответил за 6 секунд.'})}).finally(()=>clearTimeout(timer));
  return()=>{active=false;clearTimeout(timer);controller.abort()};
 },[settings.baseUrl,settings.apiKey,version]);
 const refresh=useCallback(()=>setVersion(v=>v+1),[]);
 return {...state,refresh};
}
