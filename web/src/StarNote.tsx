// Says when a view shows another star than the current one, because its grid has no closer star.

import type { CurrentStar } from "./currentStar";
import { fmtFeh } from "./currentStar";

export default function StarNote({ star, shown }: { star: CurrentStar; shown: { mass_msun: number; feh: number } }) {
  if (shown.mass_msun === star.mass_msun && shown.feh === star.feh) return null;
  return (
    <p className="note" role="note">
      The current star is {star.mass_msun} M☉, [Fe/H] {fmtFeh(star.feh)}. This view shows the nearest star it has
      data for: {shown.mass_msun} M☉, [Fe/H] {fmtFeh(shown.feh)}.
    </p>
  );
}
