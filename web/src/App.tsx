// Phase 0: one test star, drawn in the colour the contract fixture carries.
// shortcut: reads the fixture itself, not an export; switch to fetching web/public/data in Phase 1.

import fixture from "../../contract/fixture.json";
import { parseDocument } from "./data/loader";
import { starDisplayCss } from "./rendering/starColour";

const doc = parseDocument(fixture);
// The fixture's middle point is its present-day star
const point = Math.floor(doc.track.age_yr.length / 2);
const colour = starDisplayCss(doc.track.rgb[point]);

export default function App() {
  return (
    <main>
      <h1>Stellar-Forge</h1>
      <div
        className="star"
        role="img"
        aria-label="Test star"
        style={{ background: colour, boxShadow: `0 0 60px 20px ${colour}` }}
      />
      <dl>
        <dt>Mass</dt>
        <dd>{doc.meta.inputs.mass_msun} M☉</dd>
        <dt>Age</dt>
        <dd>{(doc.track.age_yr[point] / 1e9).toFixed(2)} billion years</dd>
        <dt>Source</dt>
        <dd>{doc.meta.dataset}</dd>
        <dt>Provenance</dt>
        <dd>{doc.track.provenance}{doc.track.flags.length > 0 && ` (${doc.track.flags.join(", ")})`}</dd>
        <dt>Colour</dt>
        <dd>boosted for legibility</dd>
      </dl>
    </main>
  );
}
