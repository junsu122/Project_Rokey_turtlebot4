import { createContext, useContext, useRef, type ReactNode } from 'react';
import { createDefaultServices } from './createServices';
import type { Services } from './types';

const ServicesContext = createContext<Services | null>(null);

interface ServiceProviderProps {
  children: ReactNode;
  /** Override services (real ROS/STT/LLM, or test doubles). Defaults to mocks. */
  services?: Services;
}

export function ServiceProvider({ children, services }: ServiceProviderProps) {
  const ref = useRef<Services | null>(null);
  if (ref.current === null) {
    ref.current = services ?? createDefaultServices();
  }
  return (
    <ServicesContext.Provider value={ref.current}>
      {children}
    </ServicesContext.Provider>
  );
}

/** Access the injected services. Throws if used outside <ServiceProvider>. */
export function useServices(): Services {
  const ctx = useContext(ServicesContext);
  if (!ctx) {
    throw new Error('useServices must be used within a <ServiceProvider>');
  }
  return ctx;
}
