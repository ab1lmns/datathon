import { useCallback, useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';

type TransitionOptions = { source?: HTMLButtonElement };

/** Open the clicked folder, then reveal each section without remounting video players. */
export function useContentTransition<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const animations = useRef<Animation[]>([]);
  const source = useRef<HTMLButtonElement | null>(null);
  const version = useRef(0);
  const morph = useRef<HTMLElement | null>(null);

  const cancel = useCallback(() => {
    version.current++;
    animations.current.forEach(animation => animation.cancel());
    animations.current = [];
    morph.current?.remove();
    morph.current = null;
    source.current?.removeAttribute('data-opening');
    source.current = null;
    ref.current?.removeAttribute('data-transitioning');
    ref.current?.removeAttribute('data-entering');
  }, []);

  const reveal = useCallback(() => {
    cancel();
    const target = ref.current;
    if (!target?.animate || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const current = version.current;
    target.dataset.entering = 'true';
    const shell = target.closest('.app-shell');
    const schedule: { element: HTMLElement; delay: number; distance: number }[] = [];
    const add = (selector: string, delay: number, step = 0, distance = 5) => {
      shell?.querySelectorAll<HTMLElement>(selector).forEach((element, index) => schedule.push({element,delay:delay+index*step,distance}));
    };
    // First establish navigation, then header controls, then the page contents.
    add('.sidebar .nav-overline', 0);
    add('.sidebar nav button', 60, 65, 7);
    add('.sidebar-faq', 340);
    add('.app-header .search, .mobile-search-toggle', 240);
    add('.global-upload > *', 300, 45, 3);
    add('.app-header .help', 360);
    target.querySelectorAll<HTMLElement>('[data-reveal]').forEach((element,index) => {
      schedule.push({element,delay:400+Math.min(index,8)*125,distance:8});
    });
    add('main .bottom-note', 1050);
    animations.current = schedule.map(({element,delay,distance}) => element.animate(
      [{opacity:0,transform:`translateY(${distance}px)`},{opacity:1,transform:'translateY(0)'}],
      {duration:560,delay,easing:'cubic-bezier(.16,1,.3,1)',fill:'both'},
    ));
    void Promise.all(animations.current.map(animation => animation.finished)).then(
      () => { if (version.current === current) cancel(); },
      () => { if (version.current === current) cancel(); },
    );
  }, [cancel]);

  const transition = useCallback((update: () => void, options: TransitionOptions = {}) => {
    const element = ref.current;
    const opacity = element ? getComputedStyle(element).opacity : '1';
    cancel();
    if (!element || !element.animate || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      update();
      return;
    }
    const current = version.current;
    const target = element;
    const origin = options.source?.getBoundingClientRect();
    const front = options.source?.querySelector<HTMLElement>('.folder-front');
    const surface = front ? getComputedStyle(front).backgroundImage : 'none';
    const color = front ? getComputedStyle(front).backgroundColor : '#fff';
    source.current = options.source ?? null;
    source.current?.setAttribute('data-opening', 'true');
    target.dataset.transitioning = 'true';

    async function run() {
      try {
        const exit = target.animate(
          [{opacity,transform:'translateY(0)'},{opacity:0,transform:'translateY(-4px)'}],
          {delay:options.source?170:0,duration:100,easing:'ease-in',fill:'both'},
        );
        animations.current = [exit];
        await exit.finished;
        if (version.current !== current) return;
        flushSync(update);
        source.current?.removeAttribute('data-opening');
        source.current = null;
        if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
          cancel();
          return;
        }

        if (origin) {
          const destination = target.querySelector<HTMLElement>('.opened-folder');
          if (destination) {
            const bounds = destination.getBoundingClientRect();
            const cover = document.createElement('div');
            cover.className = 'folder-morph';
            cover.setAttribute('aria-hidden', 'true');
            Object.assign(cover.style, { left: `${origin.left}px`, top: `${origin.top + 20}px`, width: `${origin.width}px`, height: `${Math.max(1,origin.height - 20)}px`, backgroundImage: surface, backgroundColor: color });
            document.body.appendChild(cover);
            morph.current = cover;
            const unfold = cover.animate([
              { left: `${origin.left}px`, top: `${origin.top + 20}px`, width: `${origin.width}px`, height: `${Math.max(1,origin.height - 20)}px`, borderRadius: '14px', opacity: 1 },
              { left: `${bounds.left}px`, top: `${bounds.top}px`, width: `${bounds.width}px`, height: `${bounds.height}px`, borderRadius: '16px', opacity: 1 },
            ], { duration: 460, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'both' });
            const panel = destination.animate([{opacity:0},{opacity:0}],{duration:460,fill:'both'});
            animations.current.push(unfold,panel);
            exit.cancel();
            await unfold.finished;
            if (version.current !== current) return;
            panel.cancel();
            const fade = cover.animate([{opacity:1},{opacity:0}],{duration:180,fill:'forwards'});
            animations.current.push(fade);
            void fade.finished.then(() => { cover.remove(); if (morph.current === cover) morph.current = null; }, () => cover.remove());
          }
        }
        target.dataset.entering = 'true';
        const sections = Array.from(target.querySelectorAll<HTMLElement>(origin ? '.intro, .library-heading, .opened-folder-title, .report-card, .library .empty' : '[data-reveal]'));
        const entering = (sections.length ? sections : [target]).map((section, index) => section.animate(
          [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'translateY(0)' }],
          { duration: 420, delay: index * 55, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
        ));
        exit.cancel();
        animations.current = entering;
        // The new page is interactive while the remaining sections settle into place.
        target.removeAttribute('data-transitioning');
        await Promise.all(entering.map(animation => animation.finished));
        if (version.current === current) cancel();
      } catch {
        // New navigation, search, uploads and unmounting cancel the previous sequence.
        if (version.current === current) cancel();
      }
    }
    void run();
  }, [cancel]);

  useEffect(() => {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const finish = () => { if (reduced.matches) animations.current.forEach(animation => animation.finish()); };
    reduced.addEventListener('change', finish);
    return () => { reduced.removeEventListener('change', finish); cancel(); };
  }, [cancel]);
  return { ref, transition, cancel, reveal };
}
