// The meta block of the file a view is drawing, for every provenance label inside it (ProvTag.tsx).

import { createContext } from "react";
import type { Meta } from "./types";

export const MetaContext = createContext<Meta | null>(null);
