import * as React from "react";
import { animate, useReducedMotion } from "framer-motion";

/** Courbe d'accélération « ease-out expo » utilisée par toutes les animations du dashboard. */
export const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

/**
 * Anime une valeur numérique depuis sa valeur précédente vers `target`.
 * - au montage : compte à partir de 0 (effet compteur) ;
 * - lors d'un changement de valeur : transition fluide depuis la valeur courante ;
 * - respecte `prefers-reduced-motion` (affichage direct, sans animation).
 */
export function useAnimatedValue(target: number, duration = 1.1): number {
  const reduce = useReducedMotion();
  const [value, setValue] = React.useState(reduce ? target : 0);
  const previous = React.useRef(reduce ? target : 0);

  React.useEffect(() => {
    if (reduce) {
      previous.current = target;
      setValue(target);
      return;
    }
    const controls = animate(previous.current, target, {
      duration,
      ease: EASE_OUT,
      onUpdate: (latest) => {
        previous.current = latest;
        setValue(latest);
      },
    });
    return () => controls.stop();
  }, [target, duration, reduce]);

  return value;
}
