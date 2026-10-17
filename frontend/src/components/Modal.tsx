import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
export function Modal({title,id='modal-title',className='',onClose,children}:{title:string;id?:string;className?:string;onClose:()=>void;children:ReactNode}){
 const ref=useRef<HTMLElement>(null),close=useRef(onClose);close.current=onClose;
 useEffect(()=>{
  const previous=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;
  document.body.style.overflow='hidden';
  const focusable=()=>Array.from(ref.current?.querySelectorAll<HTMLElement>('button, input, select, a[href], summary, video[controls]')||[]).filter(el=>!el.hasAttribute('disabled')&&el.getClientRects().length>0);
  focusable()[0]?.focus();
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape')close.current();if(e.key==='Tab'){const items=focusable(),first=items[0],last=items.at(-1);if(!first||!last)return;if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}};
  document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);document.body.style.overflow=overflow;previous?.focus()};
 },[]);
 return <div className="modal-backdrop" onClick={onClose}><section ref={ref} className={`modal ${className}`} role="dialog" aria-modal="true" aria-labelledby={id} onClick={e=>e.stopPropagation()}><div className="sheet-handle"/><button className="modal-close icon-button" aria-label="Закрыть окно" onClick={onClose}><X size={20}/></button><h2 id={id}>{title}</h2>{children}</section></div>;
}
