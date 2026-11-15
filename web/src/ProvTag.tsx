// A provenance label that opens its value's provenance (Phase 7): the label and what it means, how
// the value was made, its validity warnings, and the dataset, models, parameters, code and sources
// named in the meta block of the file it came from. Everything shown is read from the file.

import { useContext, useState } from "react";
import { createPortal } from "react-dom";
import { MetaContext } from "./data/metaContext";
import type { Provenance } from "./data/types";

const MEANING: Record<Provenance, string> = {
  published: "Read from the published dataset, unchanged.",
  interpolated: "Interpolated in Python between published tracks.",
  substituted: "The nearest published track stands in for this star.",
  derived: "Computed by Stellar-Forge from published inputs.",
  predicted: "A model prediction, not a measurement.",
};

/** `what` names the value (with its unit), `how` says how it was made, `flags` are its warnings. */
export default function ProvTag({ p, what, how, flags = [] }: { p: Provenance; what?: string; how?: string; flags?: string[] }) {
  const meta = useContext(MetaContext);
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className={`prov prov-${p}`} aria-haspopup="dialog" title="Where this value comes from" onClick={() => setOpen(true)}>{p}</button>
      {open && createPortal(
        <dialog className="prov-panel" aria-label="Provenance" ref={(d) => { if (d && !d.open) d.showModal(); }}
          onClose={() => setOpen(false)} onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
          <div>
            <h2>{what ?? "Provenance"} <span className={`prov prov-${p}`}>{p}</span></h2>
            <dl>
              <dt>Label</dt><dd>{MEANING[p]}</dd>
              {how && <><dt>How</dt><dd>{how}</dd></>}
              <dt>Warnings</dt><dd className={flags.length > 0 ? "flags" : undefined}>{flags.length > 0 ? flags.join("; ") : "none"}</dd>
              {meta && (
                <>
                  <dt>Dataset</dt><dd>{meta.dataset}</dd>
                  <dt>Models</dt>
                  <dd>{Object.entries(meta.models).map(([k, v]) => <div key={k}><em>{k}</em>: {v}</div>)}</dd>
                  <dt>Parameters</dt>
                  <dd>
                    {Object.entries(meta.inputs).map(([k, v]) => `${k} = ${v}`).join(", ") || "none"}
                    {meta.seed !== null && `; seed ${meta.seed}`}
                  </dd>
                  <dt>Made by</dt>
                  <dd>{meta.generator.name} {meta.generator.version}, code {meta.generator.git_commit}, {meta.created}; schema {meta.schema_version}</dd>
                  <dt>Sources</dt>
                  <dd>
                    {meta.references.map((r) => (
                      // Citations carry <i> tags and &amp; from their records; shown as plain text
                      <div key={r.key}>{r.citation.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&")}{" "}
                        <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer">doi:{r.doi}</a></div>
                    ))}
                  </dd>
                </>
              )}
            </dl>
            <button autoFocus onClick={() => setOpen(false)}>Close</button>
          </div>
        </dialog>,
        document.body,
      )}
    </>
  );
}
