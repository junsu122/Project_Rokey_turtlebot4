import { LANGUAGES, useLanguage } from '@/core/i18n';
import { cx } from '@/core/utils';
import { useStrings } from '@/config';
import styles from './LanguageSwitcher.module.css';

/** Language picker (ko/en/ja/zh) — requirement ver02 §2.5.3. */
export function LanguageSwitcher({ className }: { className?: string }) {
  const { language, setLanguage } = useLanguage();
  const strings = useStrings();

  return (
    <div
      className={cx(styles.switcher, className)}
      role="group"
      aria-label={strings.lang.label}
    >
      {LANGUAGES.map((option) => (
        <button
          key={option.code}
          type="button"
          className={cx(
            styles.option,
            option.code === language && styles.active,
          )}
          aria-pressed={option.code === language}
          onClick={() => setLanguage(option.code)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
