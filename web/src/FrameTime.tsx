// Frame-time read-out (Phase 7 step 7), shown in development mode only: the mean and worst time
// between animation frames over the last second, for the G210 budget (Validation, Phase 7).

import { useEffect, useState } from "react";

export default function FrameTime() {
  const [text, setText] = useState("");
  useEffect(() => {
    let raf = 0, last = performance.now(), since = last, worst = 0, frames = 0;
    const tick = (now: number) => {
      const dt = now - last;
      last = now;
      worst = Math.max(worst, dt);
      frames++;
      if (now - since >= 1000) {
        const mean = (now - since) / frames;
        setText(`${mean.toFixed(1)} ms/frame · ${(1000 / mean).toFixed(0)} fps · worst ${worst.toFixed(0)} ms`);
        since = now;
        worst = 0;
        frames = 0;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <output className="frame-time" aria-live="off">{text}</output>;
}
