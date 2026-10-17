import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight } from './Icons';
import { ForteSculpture } from './ForteSculpture';
import { BRAND_TURN_MS, BRAND_SETTLE_MS, BRAND_FLIGHT_MS, BRAND_FADE_MS } from './brandMotion';

/** A bounded intro: one turn, a measured flight to the header, then the workspace. */
export function BrandIntro({ onFinish }: { onFinish: () => void }) {
  const overlay = useRef<HTMLDivElement>(null);
  const liquid = useRef<SVGRectElement>(null);
  const drops = useRef<SVGGElement>(null);
  const veil = useRef<HTMLDivElement>(null);
  const surfaces = useRef<HTMLDivElement>(null);
  const filterId = `brand-liquid-${useId().replace(/:/g,'')}`;
  const logo = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const markReady = useCallback(() => setReady(true), []);

  useLayoutEffect(() => {
    const target = document.querySelector('.header-sculpture');
    if (!target || !logo.current) return;
    const bounds = target.getBoundingClientRect();
    const width = Math.min(480, window.innerWidth * 0.8);
    const height = width * bounds.height / bounds.width;
    Object.assign(logo.current.style, {
      width: `${width}px`, height: `${height}px`,
      left: `${(window.innerWidth - width) / 2}px`,
      top: `${(window.innerHeight - height) / 2 - 28}px`,
    });
  }, []);

  useEffect(() => {
    // No WebGL/network issue is allowed to leave the workspace covered.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const fallback = window.setTimeout(markReady, 900);
    const safety = window.setTimeout(onFinish, 4400);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const skip = () => { if (reduced.matches) onFinish(); };
    window.addEventListener('resize', onFinish);
    reduced.addEventListener('change', skip);
    return () => {
      document.body.style.overflow = previousOverflow;
      clearTimeout(fallback); clearTimeout(safety);
      document.querySelector('.app-shell')?.removeAttribute('data-brand-revealing');
      document.querySelector('.app-shell')?.removeAttribute('data-brand-landed');
      window.removeEventListener('resize', onFinish);
      reduced.removeEventListener('change', skip);
    };
  }, [markReady, onFinish]);

  useEffect(() => {
    if (!ready) return;
    let disposed = false;
    const animations: Animation[] = [];
    async function run() {
      const stage = logo.current, screen = overlay.current;
      const target = document.querySelector('.header-sculpture');
      if (!stage || !screen || !target || !stage.animate) { onFinish(); return; }
      try {
        const width = window.innerWidth, height = window.innerHeight;
        const diameter = Math.min(width * .86, 540);
        const cx = width / 2, cy = height / 2 - 28;
        const blob = liquid.current;
        const shell = document.querySelector('.app-shell');
        if (blob) {
          const gather = blob.animate([
            { x: '0px', y: '0px', width: `${width}px`, height: `${height}px`, rx: '0px', ry: '0px' },
            { x: `${cx - diameter * .57}px`, y: `${cy - diameter * .43}px`, width: `${diameter * 1.14}px`, height: `${diameter * .86}px`, rx: `${diameter * .4}px`, ry: `${diameter * .4}px`, offset: .78 },
            { x: `${cx - diameter / 2}px`, y: `${cy - diameter / 2}px`, width: `${diameter}px`, height: `${diameter}px`, rx: `${diameter / 2}px`, ry: `${diameter / 2}px` },
          ], { delay: 300, duration: 1250, easing: 'cubic-bezier(.65,0,.2,1)', fill: 'both' });
          animations.push(gather);
        }
        const hold = stage.animate([{ opacity: 1 }, { opacity: 1 }], { duration: BRAND_TURN_MS + BRAND_SETTLE_MS });
        animations.push(hold);
        await hold.finished;
        if (disposed) return;
        const from = stage.getBoundingClientRect(), to = target.getBoundingClientRect();
        screen.dataset.flying = 'true';
        shell?.setAttribute('data-brand-revealing', 'true');
        if (veil.current) animations.push(veil.current.animate([{opacity:1},{opacity:0}],{duration:460,fill:'forwards'}));
        // The final surfaces copy actual CSS, avoiding a flat red → gradient snap.
        const landing: Animation[] = [];
        ['.sidebar', '.global-upload'].forEach(selector => {
          const element = document.querySelector<HTMLElement>(selector);
          if (!element || !surfaces.current) return;
          const bounds = element.getBoundingClientRect(), style = getComputedStyle(element);
          if (!bounds.width || !bounds.height) return;
          const patch = document.createElement('div');
          patch.className = 'startup-landing-surface';
          Object.assign(patch.style, {
            left: `${bounds.left}px`, top: `${bounds.top}px`, width: `${bounds.width}px`, height: `${bounds.height}px`,
            background: style.background, borderRadius: style.borderRadius, boxShadow: style.boxShadow,
            border: style.border, opacity: '0',
          });
          surfaces.current.appendChild(patch);
          const blend = patch.animate([{opacity:0},{opacity:1}],{delay:BRAND_FLIGHT_MS-220,duration:220,easing:'ease-out',fill:'forwards'});
          landing.push(blend); animations.push(blend);
        });
        const sidebar = document.querySelector('.sidebar');
        const sidebarBounds = sidebar?.getBoundingClientRect();
        if (blob && sidebarBounds) {
          animations.push(blob.animate([
            { x: `${cx-diameter/2}px`, y: `${cy-diameter/2}px`, width: `${diameter}px`, height: `${diameter}px`, rx: `${diameter/2}px`, ry: `${diameter/2}px` },
            { x: `${sidebarBounds.left}px`, y: `${sidebarBounds.top}px`, width: `${sidebarBounds.width}px`, height: `${sidebarBounds.height}px`, rx: window.innerWidth>760?'0px':'19px', ry: window.innerWidth>760?'0px':'19px' },
          ],{duration:BRAND_FLIGHT_MS,easing:'cubic-bezier(.45,0,.15,1)',fill:'forwards'}));
        }
        if (blob) {
          const dissolve = blob.animate([{opacity:1},{opacity:0}],{delay:BRAND_FLIGHT_MS-220,duration:220,fill:'forwards'});
          landing.push(dissolve); animations.push(dissolve);
        }
        const destinations = ['.global-upload'];
        destinations.forEach(selector => {
          const element = document.querySelector(selector);
          const destination = element?.getBoundingClientRect();
          const radius = element ? getComputedStyle(element).borderRadius : '9px';
          if (!destination || !drops.current || destination.width===0) return;
          const drop = document.createElementNS('http://www.w3.org/2000/svg','rect');
          drop.setAttribute('fill','#940d42');
          drops.current.appendChild(drop);
          animations.push(drop.animate([
            { x:`${cx-52}px`, y:`${cy-52}px`, width:'104px',height:'104px',rx:'52px',ry:'52px',opacity:1 },
            { x:`${destination.left}px`,y:`${destination.top}px`,width:`${destination.width}px`,height:`${destination.height}px`,rx:radius,ry:radius,opacity:1,offset:.74 },
            { x:`${destination.left}px`,y:`${destination.top}px`,width:`${destination.width}px`,height:`${destination.height}px`,rx:radius,ry:radius,opacity:0 },
          ],{duration:BRAND_FLIGHT_MS,easing:'cubic-bezier(.45,0,.15,1)',fill:'both'}));
        });
        const flight = stage.animate([
          { transform: 'translate(0,0) scale(1,1)' },
          { transform: `translate(${to.left - from.left}px,${to.top - from.top}px) scale(${to.width / from.width},${to.height / from.height})` },
        ], { duration: BRAND_FLIGHT_MS, easing: 'cubic-bezier(.45,0,.15,1)', fill: 'forwards' });
        animations.push(flight);
        await Promise.all([flight.finished, ...landing.map(animation => animation.finished)]);
        if (disposed) return;
        // Atomic handoff: never draw the moving copy over the real header/menu.
        shell?.setAttribute('data-brand-landed', 'true');
        screen.dataset.landed = 'true';
        const fade = screen.animate([{ opacity: 1 }, { opacity: 0 }], { duration: BRAND_FADE_MS, fill: 'forwards' });
        animations.push(fade);
        await fade.finished;
        if (!disposed) onFinish();
      } catch { if (!disposed) onFinish(); }
    }
    void run();
    return () => { disposed = true; animations.forEach(animation => animation.cancel()); };
  }, [ready, onFinish]);

  return createPortal(<div className="startup-screen" ref={overlay} aria-label="Запуск видеоконтроля">
    <div className="startup-veil" ref={veil}/>
    <svg className="startup-liquid" width="100%" height="100%" aria-hidden="true">
      <defs><filter id={filterId} x="-20%" y="-20%" width="140%" height="140%" colorInterpolationFilters="sRGB"><feGaussianBlur in="SourceGraphic" stdDeviation="9" result="blur"/><feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -9"/></filter></defs>
      <g filter={`url(#${filterId})`}><rect ref={liquid} x="0" y="0" width="100%" height="100%" fill="#940d42"/><g ref={drops}/></g>
    </svg>
    <div className="startup-surfaces" ref={surfaces} aria-hidden="true"/>
    <div className="startup-edition">DATATHON 26 <span>/</span> FORTEBANK</div>
    <div className="startup-logo" ref={logo}><ForteSculpture intro onReady={markReady}/></div>
    <div className="startup-caption">Кассовая дисциплина под видеоконтролем</div>
    <button className="startup-skip" onClick={onFinish}>Перейти к проверкам<ArrowRight size={16}/></button>
  </div>, document.body);
}
