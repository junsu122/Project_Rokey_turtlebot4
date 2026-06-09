import { useState } from 'react';
import {
  BigButton,
  FacilityIcon,
  LanguageSwitcher,
  ScreenFrame,
  StaffCallButton,
} from '@/components';
import {
  facilitiesOnFloor,
  floors,
  getFloorOrThrow,
  kioskConfig,
  useStrings,
} from '@/config';
import {
  isSelectableFacility,
  localizedFacilityName,
  type Facility,
} from '@/core/domain';
import { useLanguage } from '@/core/i18n';
import { useKioskDispatch } from '@/core/kiosk';
import { cx } from '@/core/utils';
import { useGuidance } from '@/features/guiding/GuidanceProvider';
import { Blueprint } from './Blueprint';
import styles from './MapScreen.module.css';

/**
 * Requirement #4 (button A): show this space's facilities as a blueprint; tapping
 * a facility dispatches the escort. A floor selector also surfaces other-floor
 * destinations, which route via the cross-floor handoff (#6).
 */
export function MapScreen() {
  const dispatch = useKioskDispatch();
  const strings = useStrings();
  const { language } = useLanguage();
  const { guideTo } = useGuidance();
  const [floorId, setFloorId] = useState(kioskConfig.currentFloorId);
  const [selectedId, setSelectedId] = useState<string>();

  const floor = getFloorOrThrow(floorId);
  const list = facilitiesOnFloor(floorId);
  // Benches etc. stay drawn on the blueprint for orientation, but only
  // selectable facilities appear in the tappable destination list.
  const selectable = list.filter(isSelectableFacility);

  const handleSelect = (facility: Facility) => {
    setSelectedId(facility.id);
    guideTo(facility);
  };

  return (
    <ScreenFrame tone="light">
      <header className={styles.header}>
        <div className={styles.topbar}>
          <div
            className={styles.floors}
            role="tablist"
            aria-label={strings.map.floorPickerLabel}
          >
            {floors.map((floorOption) => (
              <button
                key={floorOption.id}
                type="button"
                role="tab"
                aria-selected={floorOption.id === floorId}
                className={cx(
                  styles.floorTab,
                  floorOption.id === floorId && styles.floorTabActive,
                )}
                onClick={() => {
                  setFloorId(floorOption.id);
                  setSelectedId(undefined);
                }}
              >
                {floorOption.shortName}
                {floorOption.id === kioskConfig.currentFloorId && (
                  <span className={styles.hereTag}>{strings.map.here}</span>
                )}
              </button>
            ))}
          </div>
          <LanguageSwitcher />
        </div>

        <div className={styles.titleRow}>
          <BigButton
            tone="neutral"
            size="compact"
            icon="←"
            label={strings.map.back}
            onClick={() => dispatch({ type: 'GO_HOME' })}
          />
          <div className={styles.titleBlock}>
            <h1 className={styles.title}>{strings.map.title}</h1>
            <p className={styles.subtitle}>{strings.map.subtitle}</p>
          </div>
        </div>
      </header>

      <div className={styles.content}>
        <div className={styles.mapPane}>
          <Blueprint
            floor={floor}
            facilities={list}
            onSelect={handleSelect}
            selectedId={selectedId}
            language={language}
          />
        </div>

        <ul className={styles.list}>
          {selectable.map((facility) => (
            <li key={facility.id} className={styles.listCell}>
              <BigButton
                tone="neutral"
                size="compact"
                icon={<FacilityIcon category={facility.category} />}
                label={localizedFacilityName(facility, language)}
                onClick={() => handleSelect(facility)}
                className={styles.listItem}
              />
            </li>
          ))}
        </ul>
      </div>

      <StaffCallButton
        label={strings.home.staffCall}
        onClick={() => dispatch({ type: 'OPEN_STAFF_CALL' })}
      />
    </ScreenFrame>
  );
}
