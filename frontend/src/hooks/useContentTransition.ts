import { useCallback, useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';

type TransitionOptions = { source?: HTMLButtonElement };

/** Open the clicked folder, then reveal each section without remounting video players. */
export function useContentTransition<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const animations = useRef<Animation[]>([]);
  const source = useRef<HTMLButtonElement | null>(null);
  const version = useRef(0);

  const cancel = useCallback(() => {
    version.current++;
    animations.current.forEach(animation => animation.cancel());
    animations.current = [];
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
    animations.current = Array.from(target.querySelectorAll<HTMLElement>('[data-reveal]')).map((section, index) => section.animate(
      [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration: 380, delay: index * 38, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
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
    source.current = options.source ?? null;
    source.current?.setAttribute('data-opening', 'true');
    target.dataset.transitioning = 'true';

    async function run() {
      try {
        // The cover starts moving immediately; the page follows within 170 ms.
        const exit = target.animate(
          [{ opacity, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(-4px)' }],
          { delay: options.source ? 170 : 0, duration: 100, easing: 'ease-in', fill: 'both' },
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

        target.dataset.entering = 'true';
        const sections = Array.from(target.querySelectorAll<HTMLElement>('[data-reveal]'));
        const entering = (sections.length ? sections : [target]).map((section, index) => section.animate(
          [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'translateY(0)' }],
          { duration: 380, delay: index * 38, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
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
