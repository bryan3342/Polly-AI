import { createContext, useContext } from 'react';

/* The context object and its hook live here, apart from the provider component.
   React Fast Refresh only works when a module exports components exclusively, so
   keeping these non-component exports out of WebSocketContext.jsx preserves hot
   reload (and satisfies react-refresh/only-export-components). */
export const Ctx = createContext(null);

export const useWS = () => useContext(Ctx);
