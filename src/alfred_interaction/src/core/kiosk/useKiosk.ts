import { useContext, type Dispatch } from 'react';
import { KioskDispatchContext, KioskStateContext } from './KioskProvider';
import type { KioskEvent, KioskState } from './types';

export function useKioskState(): KioskState {
  const ctx = useContext(KioskStateContext);
  if (!ctx) throw new Error('useKioskState must be used within <KioskProvider>');
  return ctx;
}

export function useKioskDispatch(): Dispatch<KioskEvent> {
  const ctx = useContext(KioskDispatchContext);
  if (!ctx) {
    throw new Error('useKioskDispatch must be used within <KioskProvider>');
  }
  return ctx;
}
