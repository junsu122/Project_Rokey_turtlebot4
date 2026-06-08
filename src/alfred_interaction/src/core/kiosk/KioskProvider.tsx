import {
  createContext,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react';
import { initialKioskState, kioskReducer } from './kioskMachine';
import type { KioskEvent, KioskState } from './types';

export const KioskStateContext = createContext<KioskState | null>(null);
export const KioskDispatchContext = createContext<Dispatch<KioskEvent> | null>(
  null,
);

export function KioskProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(kioskReducer, initialKioskState);

  return (
    <KioskStateContext.Provider value={state}>
      <KioskDispatchContext.Provider value={dispatch}>
        {children}
      </KioskDispatchContext.Provider>
    </KioskStateContext.Provider>
  );
}
