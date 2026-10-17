import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight } from 'lucide-react';
import { ForteSculpture } from './ForteSculpture';

/** A bounded intro: one turn, a measured flight to the header, then the workspace. */
export function BrandIntro({ onFinish }: { onFinish: () => void }) {
  const overlay = useRef<HTMLDivElement>(null);
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
    const safety = window.setTimeout(onFinish, 3400);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const skip = () => { if (reduced.matches) onFinish(); };
    window.addEventListener('resize', onFinish);
    reduced.addEventListener('change', skip);
    return () => {
      document.body.style.overflow = previousOverflow;
      clearTimeout(fallback); clearTimeout(safety);
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
        const hold = stage.animate([{ opacity: 1 }, { opacity: 1 }], { duration: 1120 });
        animations.push(hold);
        await hold.finished;
        if (disposed) return;
        const from = stage.getBoundingClientRect(), to = target.getBoundingClientRect();
        screen.dataset.flying = 'true';
        const flight = stage.animate([
          { transform: 'translate(0,0) scale(1,1)' },
          { transform: `translate(${to.left - from.left}px,${to.top - from.top}px) scale(${to.width / from.width},${to.height / from.height})` },
        ], { duration: 720, easing: 'cubic-bezier(.65,0,.15,1)', fill: 'forwards' });
        animations.push(flight);
        await flight.finished;
        if (disposed) return;
        const fade = screen.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, fill: 'forwards' });
        animations.push(fade);
        await fade.finished;
        if (!disposed) onFinish();
      } catch { if (!disposed) onFinish(); }
    }
    void run();
    return () => { disposed = true; animations.forEach(animation => animation.cancel()); };
  }, [ready, onFinish]);

  return createPortal(<div className="startup-screen" ref={overlay} aria-label="Запуск видеоконтроля">
    <div className="startup-edition">DATATHON 26 <span>/</span> FORTEBANK</div>
    <div className="startup-logo" ref={logo}><ForteSculpture intro onReady={markReady}/></div>
    <div className="startup-caption">Кассовая дисциплина под видеоконтролем</div>
    <button className="startup-skip" onClick={onFinish}>Перейти к проверкам<ArrowRight size={16}/></button>
  </div>, document.body);
}
