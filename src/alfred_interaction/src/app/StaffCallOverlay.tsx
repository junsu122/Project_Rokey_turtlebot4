import { Modal } from '@/components';
import { useStrings } from '@/config';
import { useKioskDispatch, useKioskState } from '@/core/kiosk';

/**
 * Requirement #11: the "직원 호출" popup. Shows "직원이 오고 있습니다" and only
 * closes when staff press the close button (backdrop dismissal is disabled).
 */
export function StaffCallOverlay() {
  const { staffCallActive } = useKioskState();
  const dispatch = useKioskDispatch();
  const strings = useStrings();

  return (
    <Modal
      open={staffCallActive}
      icon="🛎️"
      title={strings.staff.title}
      description={strings.staff.description}
      note={strings.staff.note}
      closeLabel={strings.staff.close}
      onClose={() => dispatch({ type: 'CLOSE_STAFF_CALL' })}
    />
  );
}
