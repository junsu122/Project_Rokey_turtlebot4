import type { Facility } from '@/core/domain';

/**
 * Station facilities, modeled after the real 1F / 2F section drawings.
 * `name` is Korean (default); `i18n` carries en/ja/zh display names (§2.5.3).
 * `footprint`/`position` are blueprint-drawing units (viewBox 160×100);
 * `poiId`/`pose` are the FMS POI id and the real robot goal pose (meters) sent
 * to the server (fixed by the turtlebot4 team — see facilities_config). The
 * turtlebot charging bay ("대기" / station·station2) is omitted from the map,
 * and the benches are display-only (no poiId → not a navigation target).
 */
export const facilities: Facility[] = [
  // ============================ 1층 (F1) ============================
  {
    id: 'f1-exit1',
    name: '1번 출구',
    i18n: { en: 'Exit 1', ja: '1番出口', zh: '1号出口' },
    category: 'exit',
    variant: 'door',
    floorId: 'F1',
    poiId: 'entrance',
    pose: { x: -8.05, y: 2.56 },
    footprint: { x: 9, y: 11, w: 24, h: 12 }, // top-left corner
    position: { x: 26, y: 19 },
    aliases: ['일번출구', '1번', '출구', '출입구', '나가는곳', '밖'],
  },
  {
    id: 'f1-info',
    name: '안내데스크',
    i18n: { en: 'Information', ja: '案内デスク', zh: '问询处' },
    category: 'info',
    floorId: 'F1',
    poiId: 'info',
    pose: { x: -5.12, y: 3.2 },
    footprint: { x: 43, y: 11, w: 20, h: 8 }, // top-center
    position: { x: 77, y: 20 },
    aliases: ['안내', '데스크', '인포', '문의', '도움', '고객'],
  },
  {
    id: 'f1-elevator',
    name: '엘리베이터',
    i18n: { en: 'Elevator', ja: 'エレベーター', zh: '电梯' },
    category: 'elevator',
    floorId: 'F1',
    poiId: 'lift',
    pose: { x: -2.86, y: 3.82 },
    footprint: { x: 72, y: 11, w: 24, h: 22 }, // right of the info desk
    position: { x: 116, y: 25 },
    aliases: ['엘베', '승강기', '리프트', 'ev', '이브이'],
  },
  {
    id: 'f1-restroom',
    name: '화장실',
    i18n: { en: 'Restroom', ja: 'トイレ', zh: '洗手间' },
    category: 'restroom',
    floorId: 'F1',
    poiId: 'WC',
    pose: { x: -7.23, y: 1.37 },
    footprint: { x: 9, y: 69, w: 20, h: 20 }, // bottom-left corner
    position: { x: 29, y: 69 },
    aliases: ['변소', '토일렛', '용변', '볼일', 'wc', '화장실'],
  },
  {
    id: 'f1-escalator',
    name: '에스컬레이터',
    i18n: { en: 'Escalator', ja: 'エスカレーター', zh: '扶梯' },
    category: 'escalator',
    floorId: 'F1',
    poiId: 'esc',
    pose: { x: -5.0, y: 1.3 },
    footprint: { x: 35, y: 77, w: 30, h: 12 }, // bottom-center
    position: { x: 77, y: 78 },
    aliases: ['에스컬', '무빙워크', '올라가는'],
  },
  {
    id: 'f1-exit2',
    name: '2번 출구',
    i18n: { en: 'Exit 2', ja: '2番出口', zh: '2号出口' },
    category: 'exit',
    variant: 'door',
    floorId: 'F1',
    poiId: 'entrance2',
    pose: { x: -0.991, y: 2.48 },
    footprint: { x: 127, y: 77, w: 24, h: 12 }, // bottom-right corner
    position: { x: 132, y: 78 },
    aliases: ['이번출구', '2번', '출구', '출입구', '나가는곳', '밖'],
  },

  // ============================ 2층 (F2) ============================
  {
    id: 'f2-pa1',
    name: '탑승구 A-1',
    i18n: { en: 'Platform A-1', ja: 'のりば A-1', zh: '站台 A-1' },
    category: 'platform',
    floorId: 'F2',
    poiId: 'pl_1',
    pose: { x: -3.0, y: 3.23 },
    footprint: { x: 9, y: 11, w: 15, h: 7 }, // left column (train to the left)
    position: { x: 39, y: 21 },
    aliases: ['에이원', 'a1', '탑승구', '승강장', '플랫폼', '타는곳'],
  },
  {
    id: 'f2-pa2',
    name: '탑승구 A-2',
    i18n: { en: 'Platform A-2', ja: 'のりば A-2', zh: '站台 A-2' },
    category: 'platform',
    floorId: 'F2',
    poiId: 'pl_2',
    pose: { x: -3.0, y: 2.8 },
    footprint: { x: 9, y: 20, w: 15, h: 7 },
    position: { x: 39, y: 37 },
    aliases: ['에이투', 'a2', '탑승구', '승강장', '플랫폼'],
  },
  {
    id: 'f2-pa3',
    name: '탑승구 A-3',
    i18n: { en: 'Platform A-3', ja: 'のりば A-3', zh: '站台 A-3' },
    category: 'platform',
    floorId: 'F2',
    poiId: 'pl_3',
    pose: { x: -3.0, y: 2.25 },
    footprint: { x: 9, y: 29, w: 15, h: 7 },
    position: { x: 39, y: 53 },
    aliases: ['에이쓰리', 'a3', '탑승구', '승강장', '플랫폼'],
  },
  {
    id: 'f2-transfer',
    name: '환승출구',
    i18n: { en: 'Transfer', ja: '乗換口', zh: '换乘口' },
    category: 'transit',
    variant: 'door',
    floorId: 'F2',
    poiId: 'trans',
    pose: { x: -0.5, y: 3.5 },
    footprint: { x: 138, y: 11, w: 13, h: 10 }, // top-right corner
    position: { x: 135, y: 21 },
    aliases: ['환승', '갈아타', '환승통로', '환승출구'],
  },
  {
    id: 'f2-bench1',
    name: '벤치 1',
    i18n: { en: 'Bench 1', ja: 'ベンチ 1', zh: '长椅 1' },
    category: 'bench',
    variant: 'a',
    // rotation: 22,
    floorId: 'F2',
    footprint: { x: 45, y: 26, w: 20, h: 10 }, // upper (ahead on y), faces bench 2
    position: { x: 74, y: 35 },
    aliases: ['벤치', '의자', '쉼터', '앉', '소파', '쉬는곳'],
    selectable: false, // 지도 표시 전용 — 안내(이동) 목적지 아님
  },
  {
    id: 'f2-bench2',
    name: '벤치 2',
    i18n: { en: 'Bench 2', ja: 'ベンチ 2', zh: '长椅 2' },
    category: 'bench',
    variant: 'b',
    // rotation: 200,
    floorId: 'F2',
    footprint: { x: 86, y: 33, w: 16, h: 12 }, // lower-right, faces bench 1
    position: { x: 102, y: 51 },
    aliases: ['벤치', '의자', '쉼터', '앉', '소파', '쉬는곳'],
    selectable: false, // 지도 표시 전용 — 안내(이동) 목적지 아님
  },
  {
    id: 'f2-gate-normal',
    name: '개찰구',
    i18n: { en: 'Ticket gate', ja: '改札口', zh: '检票口' },
    category: 'gate',
    variant: 'narrow',
    floorId: 'F2',
    poiId: 'gate',
    pose: { x: -1.8, y: 2.0 },
    footprint: { x: 34, y: 60, w: 22, h: 12 }, // on the fare line, above the elevator
    position: { x: 77, y: 66 },
    aliases: ['개찰구', '게이트', '일반', '탑승', '타는곳'],
  },
  {
    id: 'f2-gate-accessible',
    name: '개찰구(장애인용)',
    i18n: {
      en: 'Accessible gate',
      ja: '改札口(車椅子)',
      zh: '无障碍检票口',
    },
    category: 'gate',
    variant: 'wide',
    floorId: 'F2',
    poiId: 'gate_b',
    pose: { x: -1.3, y: 2.0 },
    footprint: { x: 86, y: 60, w: 30, h: 12 }, // on the fare line, above the escalator
    position: { x: 131, y: 66 },
    aliases: ['개찰구', '장애인', '휠체어', '우대', '넓은'],
  },
  {
    id: 'f2-elevator',
    name: '엘리베이터',
    i18n: { en: 'Elevator', ja: 'エレベーター', zh: '电梯' },
    category: 'elevator',
    floorId: 'F2',
    poiId: 'lift2',
    pose: { x: -1.75, y: 1.25 },
    footprint: { x: 72, y: 78, w: 22, h: 11 }, // bottom-center
    position: { x: 77, y: 80 },
    aliases: ['엘베', '승강기', '리프트', 'ev', '이브이'],
  },
  {
    id: 'f2-escalator',
    name: '에스컬레이터',
    i18n: { en: 'Escalator', ja: 'エスカレーター', zh: '扶梯' },
    category: 'escalator',
    floorId: 'F2',
    poiId: 'esc2',
    pose: { x: -0.25, y: 1.25 },
    footprint: { x: 121, y: 78, w: 30, h: 11 }, // bottom-right corner
    position: { x: 133, y: 80 },
    aliases: ['에스컬', '무빙워크', '내려가는'],
  },
];
