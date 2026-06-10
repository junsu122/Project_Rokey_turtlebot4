import { cx } from '@/core/utils';
import styles from './ButlerFace.module.css';

interface ButlerFaceProps {
  /** Large line under the face (e.g. patrol hint). */
  caption?: string;
  /** Smaller supporting line under the caption. */
  subtitle?: string;
  /** 'xl' enlarges the face (used on the patrol screen). */
  size?: 'default' | 'xl';
  className?: string;
}

/**
 * ALFRED as a kind, elderly butler — the face shown full-screen during patrol.
 * A dignified gentleman: silver side-parted hair, warm crinkled eyes behind round
 * spectacles, a groomed moustache, wing collar + burgundy bow tie. A warm
 * spotlight lifts him off the dark screen; he breathes and blinks gently so he
 * reads as present and welcoming rather than a frozen graphic.
 */
export function ButlerFace({
  caption,
  subtitle,
  size = 'default',
  className,
}: ButlerFaceProps) {
  return (
    <div className={cx(styles.wrap, className)}>
      <svg
        className={cx(styles.face, size === 'xl' && styles.faceXl)}
        viewBox="0 0 240 264"
        role="img"
        aria-label="집사 알프레드"
      >
        <defs>
          <radialGradient
            id="butlerGlow"
            gradientUnits="userSpaceOnUse"
            cx="120"
            cy="110"
            r="116"
          >
            <stop offset="0%" stopColor="#ffd79a" stopOpacity="0.42" />
            <stop offset="42%" stopColor="#e7a86a" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#e7a86a" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="butlerSkin" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f4d3ad" />
            <stop offset="100%" stopColor="#e0b487" />
          </linearGradient>
          <linearGradient id="butlerHair" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#eef1f6" />
            <stop offset="100%" stopColor="#bcc5d4" />
          </linearGradient>
          <linearGradient id="butlerJacket" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#202a3a" />
            <stop offset="100%" stopColor="#0e131c" />
          </linearGradient>
        </defs>

        {/* warm spotlight */}
        <circle
          className={styles.glow}
          cx="120"
          cy="112"
          r="150"
          fill="url(#butlerGlow)"
        />

        <g className={styles.figure}>
          {/* ---- attire ---- */}
          <path
            d="M16 264 C 20 208 60 190 120 190 C 180 190 220 208 224 264 Z"
            fill="url(#butlerJacket)"
          />
          <path d="M120 196 L 84 214 L 99 264 L 120 242 Z" fill="#2a3445" />
          <path d="M120 196 L 156 214 L 141 264 L 120 242 Z" fill="#2a3445" />
          <path d="M108 202 L 132 202 L 127 264 L 113 264 Z" fill="#f1eee4" />
          {/* neck */}
          <path d="M103 168 L 137 168 L 139 202 L 101 202 Z" fill="#d9ab81" />
          {/* wing collar */}
          <path d="M106 198 L 120 208 L 110 218 Z" fill="#f7f4ec" />
          <path d="M134 198 L 120 208 L 130 218 Z" fill="#f7f4ec" />
          {/* bow tie */}
          <path d="M120 208 L 98 197 L 98 219 Z" fill="#8c2f3d" />
          <path d="M120 208 L 142 197 L 142 219 Z" fill="#8c2f3d" />
          <rect x="114" y="201" width="12" height="14" rx="3" fill="#6d2531" />

          {/* ---- head ---- */}
          <ellipse cx="58" cy="124" rx="11" ry="16" fill="url(#butlerSkin)" />
          <ellipse cx="182" cy="124" rx="11" ry="16" fill="url(#butlerSkin)" />
          <ellipse cx="120" cy="118" rx="61" ry="71" fill="url(#butlerSkin)" />
          {/* soft jaw + cheeks */}
          <path
            d="M88 166 Q120 186 152 166 Q120 178 88 166 Z"
            fill="#d3a37e"
            opacity="0.45"
          />
          <ellipse cx="82" cy="150" rx="13" ry="8.5" fill="#e79f7c" opacity="0.34" />
          <ellipse cx="158" cy="150" rx="13" ry="8.5" fill="#e79f7c" opacity="0.34" />

          {/* ---- hair ---- */}
          <path
            d="M55 126 C 44 78 78 44 120 44 C 162 44 196 78 185 126
               C 181 105 172 96 160 94 C 157 79 144 73 130 76
               C 126 69 114 69 110 76 C 96 73 83 79 80 94
               C 68 96 59 105 55 126 Z"
            fill="url(#butlerHair)"
          />
          <path
            d="M104 50 Q97 72 95 94"
            stroke="#a9b3c3"
            strokeWidth="2"
            fill="none"
            opacity="0.7"
            strokeLinecap="round"
          />
          <path d="M70 108 L 81 108 L 79 140 L 70 133 Z" fill="url(#butlerHair)" />
          <path d="M170 108 L 159 108 L 161 140 L 170 133 Z" fill="url(#butlerHair)" />

          {/* ---- brows ---- */}
          <path
            d="M80 105 Q97 95 113 104"
            stroke="#d2d8e2"
            strokeWidth="7"
            fill="none"
            strokeLinecap="round"
          />
          <path
            d="M127 104 Q143 95 160 105"
            stroke="#d2d8e2"
            strokeWidth="7"
            fill="none"
            strokeLinecap="round"
          />

          {/* ---- eyes (blink) ---- */}
          <g className={styles.eyes}>
            <ellipse cx="96" cy="126" rx="16" ry="11" fill="#fbf7f0" />
            <ellipse cx="144" cy="126" rx="16" ry="11" fill="#fbf7f0" />
            <circle cx="98" cy="127" r="6.6" fill="#5b4636" />
            <circle cx="146" cy="127" r="6.6" fill="#5b4636" />
            <circle cx="98" cy="127" r="3" fill="#2b2019" />
            <circle cx="146" cy="127" r="3" fill="#2b2019" />
            <circle cx="100.4" cy="124.6" r="1.7" fill="#fff" opacity="0.92" />
            <circle cx="148.4" cy="124.6" r="1.7" fill="#fff" opacity="0.92" />
            {/* hooded upper lids */}
            <path
              d="M80 123 Q96 114 113 122"
              stroke="#d0a07b"
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
            />
            <path
              d="M127 122 Q144 114 160 123"
              stroke="#d0a07b"
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
            />
            {/* kind under-eye creases */}
            <path
              d="M83 138 Q96 144 109 138"
              stroke="#d3a37e"
              strokeWidth="2"
              fill="none"
              opacity="0.45"
              strokeLinecap="round"
            />
            <path
              d="M131 138 Q144 144 157 138"
              stroke="#d3a37e"
              strokeWidth="2"
              fill="none"
              opacity="0.45"
              strokeLinecap="round"
            />
          </g>

          {/* ---- spectacles ---- */}
          <g fill="none" stroke="#c9a35b" strokeWidth="2.6">
            <ellipse cx="96" cy="126" rx="23" ry="18" />
            <ellipse cx="144" cy="126" rx="23" ry="18" />
            <path d="M116 122 Q120 117 124 122" strokeLinecap="round" />
            <path d="M73 124 L 62 121" strokeLinecap="round" />
            <path d="M167 124 L 178 121" strokeLinecap="round" />
          </g>

          {/* ---- nose ---- */}
          <path
            d="M120 126 C 117 140 112 150 116 153 Q120 156 124 153 C 128 150 123 140 120 126 Z"
            fill="#e6c19c"
          />
          <path
            d="M113 151 Q116 155 119 153"
            stroke="#cf9f79"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
          />
          <path
            d="M127 151 Q124 155 121 153"
            stroke="#cf9f79"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
          />

          {/* ---- moustache ---- */}
          <path
            d="M120 156 C 109 151 96 153 87 161 C 83 165 86 170 92 169
               C 102 168 112 164 120 159 C 128 164 138 168 148 169
               C 154 170 157 165 153 161 C 144 153 131 151 120 156 Z"
            fill="url(#butlerHair)"
          />

          {/* ---- warm smile ---- */}
          <path
            d="M101 172 Q120 185 139 172"
            stroke="#a85e4c"
            strokeWidth="3.6"
            fill="none"
            strokeLinecap="round"
          />

          {/* ---- gentle age lines ---- */}
          <g stroke="#d3a37e" fill="none" strokeLinecap="round" opacity="0.28">
            <path d="M99 74 Q120 69 141 74" strokeWidth="2" />
            <path d="M104 150 Q98 162 105 173" strokeWidth="2" />
            <path d="M136 150 Q142 162 135 173" strokeWidth="2" />
            <path d="M74 123 L 67 119 M74 128 L 66 127" strokeWidth="1.6" />
            <path d="M166 123 L 173 119 M166 128 L 174 127" strokeWidth="1.6" />
          </g>
        </g>
      </svg>

      {caption && <p className={styles.caption}>{caption}</p>}
      {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
    </div>
  );
}
