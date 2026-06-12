import type { KeyboardEvent, ReactNode } from 'react';
import { BLUEPRINT, messages } from '@/config';
import { isSelectableFacility, localizedFacilityName } from '@/core/domain';
import type {
  BlueprintDecoration,
  BlueprintRoom,
  Facility,
  Floor,
} from '@/core/domain';
import type { Language } from '@/core/i18n';
import { cx } from '@/core/utils';
import styles from './Blueprint.module.css';

interface BlueprintProps {
  floor: Floor;
  facilities: Facility[];
  onSelect: (facility: Facility) => void;
  selectedId?: string;
  language: Language;
  /** 로봇 실시간 현위치 비율 {u,v} ∈ [0,1] (없으면 점 미표시). */
  here?: { u: number; v: number } | null;
}

/**
 * Schematic floor plan ("건설도면처럼", #4). Each facility is drawn as a
 * recognizable fixture (room, desk, elevator hatch, escalator treads, doors,
 * benches, ticket gates, platforms) from its footprint, and is tappable.
 */
export function Blueprint({
  floor,
  facilities,
  onSelect,
  selectedId,
  language,
  here,
}: BlueprintProps) {
  const { outline } = floor;
  const trainLabel = messages[language].map.train;

  return (
    <svg
      className={styles.svg}
      viewBox={`${BLUEPRINT.minX} 0 ${BLUEPRINT.width} ${BLUEPRINT.height}`}
      role="group"
      aria-label={`${floor.name} 시설 안내도`}
    >
      <defs>
        <pattern id="bp-grid" width="8" height="8" patternUnits="userSpaceOnUse">
          <path className={styles.grid} d="M8 0H0V8" fill="none" />
        </pattern>
      </defs>

      <rect
        className={styles.outline}
        x={outline.x}
        y={outline.y}
        width={outline.w}
        height={outline.h}
        rx="2.5"
      />
      <rect
        x={outline.x}
        y={outline.y}
        width={outline.w}
        height={outline.h}
        rx="2.5"
        fill="url(#bp-grid)"
      />

      {floor.walls?.map((wall) => (
        <polyline
          key={wall.id}
          className={styles.wall}
          points={wall.points.map(([x, y]) => `${x},${y}`).join(' ')}
          fill="none"
        />
      ))}

      {floor.decorations?.map((deco) => (
        <Train key={deco.id} deco={deco} label={trainLabel} />
      ))}

      {facilities.map((facility) => (
        <Fixture
          key={facility.id}
          facility={facility}
          selected={facility.id === selectedId}
          onSelect={onSelect}
          language={language}
        />
      ))}

      {here && <HereDot outline={floor.outline} u={here.u} v={here.v} />}
    </svg>
  );
}

/**
 * 로봇 실시간 현위치 — 점멸하는 빨간 점. outline 사각형 안에서 비율 {u,v}로 위치를
 * 잡는다(맵 보정: config/mapCalibration). 펄스 링이 퍼지며 코어가 깜빡인다.
 */
function HereDot({
  outline,
  u,
  v,
}: {
  outline: BlueprintRoom;
  u: number;
  v: number;
}) {
  const cx = outline.x + u * outline.w;
  const cy = outline.y + v * outline.h;
  return (
    <g className={styles.here} aria-hidden="true">
      <circle className={styles.herePulse} cx={cx} cy={cy} r="2.5" />
      <circle className={styles.hereCore} cx={cx} cy={cy} r="2.4" />
    </g>
  );
}

function Fixture({
  facility,
  selected,
  onSelect,
  language,
}: {
  facility: Facility;
  selected: boolean;
  onSelect: (facility: Facility) => void;
  language: Language;
}) {
  const fp = facility.footprint;
  const label = localizedFacilityName(facility, language);
  // Display-only fixtures (e.g. benches) are drawn but not navigable: no button
  // role, tap target, keyboard handler, or selection ring.
  const interactive = isSelectableFacility(facility);

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(facility);
    }
  };

  // Fallback: no footprint -> simple marker.
  if (!fp) {
    const { x, y } = facility.position;
    return (
      <g
        className={interactive ? styles.fixture : styles.fixtureStatic}
        role={interactive ? 'button' : undefined}
        tabIndex={interactive ? 0 : undefined}
        aria-label={label}
        aria-disabled={interactive ? undefined : true}
        onClick={interactive ? () => onSelect(facility) : undefined}
        onKeyDown={interactive ? onKeyDown : undefined}
      >
        {interactive && <circle className={styles.hit} cx={x} cy={y} r="9" />}
        <circle
          className={cx(styles.dot, selected && styles.dotSelected)}
          cx={x}
          cy={y}
          r="5"
        />
        <text className={styles.fxLabel} x={x} y={y + 10} textAnchor="middle">
          {label}
        </text>
      </g>
    );
  }

  // platform renders its code inside; gate labels sit above (elevator/escalator
  // are right below them). Everything else (incl. restroom) labels below so
  // longer translations don't overflow the fixture.
  const labelInside = facility.category === 'platform';
  const labelAbove = facility.category === 'gate';
  const labelX = fp.x + fp.w / 2;
  const labelY = labelAbove ? fp.y - 2.4 : fp.y + fp.h + 4.4;

  const centerX = fp.x + fp.w / 2;
  const centerY = fp.y + fp.h / 2;
  const shapeTransform = facility.rotation
    ? `rotate(${facility.rotation} ${centerX} ${centerY})`
    : undefined;

  return (
    <g
      className={interactive ? styles.fixture : styles.fixtureStatic}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={facility.name}
      aria-disabled={interactive ? undefined : true}
      onClick={interactive ? () => onSelect(facility) : undefined}
      onKeyDown={interactive ? onKeyDown : undefined}
    >
      {/* full-footprint tap target */}
      {interactive && (
        <rect
          className={styles.hit}
          x={fp.x - 1}
          y={fp.y - 1}
          width={fp.w + 2}
          height={fp.h + 2}
        />
      )}

      <g transform={shapeTransform}>{drawFixture(facility)}</g>

      {selected && (
        <rect
          className={styles.selectRing}
          x={fp.x - 2.5}
          y={fp.y - 2.5}
          width={fp.w + 5}
          height={fp.h + 5}
          rx="2.5"
        />
      )}

      {!labelInside && (
        <text className={styles.fxLabel} x={labelX} y={labelY} textAnchor="middle">
          {label}
        </text>
      )}
    </g>
  );
}

/** Draws the shape for a facility based on category/variant (footprint required). */
function drawFixture(facility: Facility): ReactNode {
  const fp = facility.footprint;
  if (!fp) return null;
  const { x, y, w, h } = fp;
  const cxp = x + w / 2;
  const cyp = y + h / 2;

  switch (facility.category) {
    case 'restroom':
      // Box + male/female pictogram. Name is drawn below (see labelInside).
      return (
        <>
          <rect className={styles.room} x={x} y={y} width={w} height={h} rx="1.5" />
          {restroomSymbol(x, y, w, h)}
        </>
      );

    case 'info':
      return (
        <>
          <rect className={styles.box} x={x} y={y} width={w} height={h} rx="1" />
          <rect
            className={styles.deskCounter}
            x={x}
            y={y + h - 3}
            width={w}
            height={3}
          />
        </>
      );

    case 'elevator':
      return (
        <>
          <rect className={styles.box} x={x} y={y} width={w} height={h} rx="1" />
          <line className={styles.hatch} x1={x} y1={y} x2={x + w} y2={y + h} />
          <line className={styles.hatch} x1={x + w} y1={y} x2={x} y2={y + h} />
          <text className={styles.evMark} x={cxp} y={cyp} textAnchor="middle">
            E/V
          </text>
        </>
      );

    case 'escalator':
      return (
        <>
          <rect className={styles.box} x={x} y={y} width={w} height={h} rx="1" />
          {[0.22, 0.42, 0.62, 0.82].map((t, i) => (
            <line
              key={i}
              className={styles.tread}
              x1={x + 1.5}
              y1={y + h * t}
              x2={x + w - 1.5}
              y2={y + h * t}
            />
          ))}
          <path
            className={styles.arrow}
            d={`M${cxp - 3.2} ${y + h - 2.5} L${cxp} ${y + 2.5} L${cxp + 3.2} ${y + h - 2.5}`}
            fill="none"
          />
        </>
      );

    case 'exit':
    case 'transit': {
      const isTransit = facility.category === 'transit';
      return (
        <>
          <rect
            className={cx(styles.box, isTransit && styles.transitBox)}
            x={x}
            y={y}
            width={w}
            height={h}
            rx="1"
          />
          {/* door leaf + swing arc */}
          <line
            className={cx(styles.doorLeaf, isTransit && styles.transitStroke)}
            x1={x + 1.5}
            y1={y + h - 1.5}
            x2={x + w * 0.66}
            y2={y + 1.8}
          />
          <path
            className={cx(styles.doorArc, isTransit && styles.transitStroke)}
            d={`M${x + w * 0.66} ${y + 1.8} A ${w * 0.66} ${h * 0.9} 0 0 1 ${x + w - 1.5} ${y + h - 1.5}`}
            fill="none"
          />
        </>
      );
    }

    case 'bench':
      return facility.variant === 'b'
        ? // rounded 3-seat bench with circular arms
          (
            <>
              <rect className={styles.sofa} x={x} y={y} width={w} height={h} rx="5" />
              <rect
                className={styles.sofaCushion}
                x={x + 5}
                y={y + h * 0.32}
                width={w - 10}
                height={h * 0.52}
                rx="2.5"
              />
              <circle className={styles.sofaArm} cx={x + 3} cy={cyp} r="2.4" />
              <circle className={styles.sofaArm} cx={x + w - 3} cy={cyp} r="2.4" />
            </>
          )
        : // 2-seat bench with a center split
          (
            <>
              <rect className={styles.sofa} x={x} y={y} width={w} height={h} rx="2" />
              <rect
                className={styles.sofaCushion}
                x={x + 2}
                y={y + h * 0.36}
                width={w / 2 - 2.6}
                height={h * 0.5}
                rx="1"
              />
              <rect
                className={styles.sofaCushion}
                x={x + w / 2 + 0.6}
                y={y + h * 0.36}
                width={w / 2 - 2.6}
                height={h * 0.5}
                rx="1"
              />
            </>
          );

    case 'gate': {
      const wide = facility.variant === 'wide';
      const postW = wide ? w * 0.22 : w * 0.34;
      return (
        <>
          <rect
            className={styles.gatePost}
            x={x}
            y={y}
            width={postW}
            height={h}
            rx="0.8"
          />
          <rect
            className={styles.gatePost}
            x={x + w - postW}
            y={y}
            width={postW}
            height={h}
            rx="0.8"
          />
          {wide && (
            <text className={styles.wheelchair} x={cxp} y={cyp} textAnchor="middle">
              ♿
            </text>
          )}
        </>
      );
    }

    case 'platform': {
      const code = facility.name.split(' ').pop() ?? facility.name;
      return (
        <>
          <rect className={styles.box} x={x} y={y} width={w} height={h} rx="1" />
          <line
            className={styles.safety}
            x1={x + 1.5}
            y1={y + h - 1.6}
            x2={x + w - 1.5}
            y2={y + h - 1.6}
          />
          <text className={styles.platformCode} x={cxp} y={cyp} textAnchor="middle">
            {code}
          </text>
        </>
      );
    }

    default:
      return <rect className={styles.box} x={x} y={y} width={w} height={h} rx="1" />;
  }
}

/** Male/female restroom pictogram, centered inside the footprint. */
function restroomSymbol(x: number, y: number, w: number, h: number): ReactNode {
  const cx = x + w / 2;
  const figH = Math.min(h * 0.62, w * 0.6); // figures are 30 local units tall
  const s = figH / 30;
  const top = y + (h - figH) / 2;
  const d = 4.5 * s + 1.1; // half-distance between the two figure centers
  const manTx = cx - d - 6 * s; // local x=6 is each figure's center
  const womanTx = cx + d - 6 * s;
  return (
    <g aria-hidden="true">
      {/* man */}
      <g transform={`translate(${manTx} ${top}) scale(${s})`}>
        <circle className={styles.wcFigure} cx="6" cy="4" r="3" />
        <rect className={styles.wcFigure} x="2.5" y="8" width="7" height="11" rx="1.6" />
        <rect className={styles.wcFigure} x="3" y="17.5" width="2.4" height="11.5" rx="0.8" />
        <rect className={styles.wcFigure} x="6.6" y="17.5" width="2.4" height="11.5" rx="0.8" />
      </g>
      {/* divider */}
      <line
        className={styles.wcDivider}
        x1={cx}
        y1={top + 6 * s}
        x2={cx}
        y2={top + 28 * s}
      />
      {/* woman */}
      <g transform={`translate(${womanTx} ${top}) scale(${s})`}>
        <circle className={styles.wcFigure} cx="6" cy="4" r="3" />
        <path className={styles.wcFigure} d="M6 7.5 L10.5 19 L1.5 19 Z" />
        <rect className={styles.wcFigure} x="4" y="18.5" width="1.9" height="10.5" rx="0.7" />
        <rect className={styles.wcFigure} x="6.1" y="18.5" width="1.9" height="10.5" rx="0.7" />
      </g>
    </g>
  );
}

/** Decorative train car alongside the platforms (non-interactive). */
function Train({ deco, label }: { deco: BlueprintDecoration; label: string }) {
  const { x, y, w, h } = deco;
  const windowCount = 5;
  const slot = h / (windowCount + 0.6);
  const windows = Array.from({ length: windowCount }, (_, i) => (
    <rect
      key={i}
      className={styles.trainWindow}
      x={x + w * 0.22}
      y={y + slot * (i + 0.55)}
      width={w * 0.56}
      height={slot * 0.5}
      rx="0.8"
    />
  ));

  return (
    <g aria-hidden="true">
      <rect className={styles.trainBody} x={x} y={y} width={w} height={h} rx="3.5" />
      {/* platform-facing edge (doors side) */}
      <line
        className={styles.trainStripe}
        x1={x + w}
        y1={y + 1.5}
        x2={x + w}
        y2={y + h - 1.5}
      />
      {windows}
      <text
        className={styles.trainLabel}
        x={x + w / 2}
        y={y + h + 4}
        textAnchor="middle"
      >
        {label}
      </text>
    </g>
  );
}
