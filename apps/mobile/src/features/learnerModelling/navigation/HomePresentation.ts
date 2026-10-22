import { createContext } from "react";

/** Reports Home visibility only; never carries learner data or authorization. */
export const HomePresentationContext = createContext<((home: boolean) => void) | undefined>(undefined);
