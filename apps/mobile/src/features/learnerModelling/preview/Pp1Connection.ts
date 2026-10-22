import { createContext, useContext } from "react";
import type { Pp1Connection } from "../data/pp1Client";
/** In-memory authenticated capability; never persisted with demo choices. */
export const Pp1ConnectionContext = createContext<Pp1Connection | undefined>(undefined);
export const usePp1Connection = () => useContext(Pp1ConnectionContext);
