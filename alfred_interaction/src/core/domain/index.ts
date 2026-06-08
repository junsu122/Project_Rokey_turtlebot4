/** Domain barrel — import domain types from a single place. */
export type {
  Facility,
  FacilityCategory,
  FacilityPosition,
  FacilityPose,
  FacilityFootprint,
} from './facility';
export {
  TRANSFER_CATEGORIES,
  isTransferFacility,
  isSelectableFacility,
  localizedFacilityName,
} from './facility';

export type {
  Floor,
  BlueprintRoom,
  BlueprintWall,
  BlueprintDecoration,
} from './floor';

export type {
  NavigationKind,
  TransferStep,
  NavigationPlan,
  NavigationPhase,
  NavigationProgress,
  NavigationSession,
} from './navigation';
export { isTerminalPhase } from './navigation';
