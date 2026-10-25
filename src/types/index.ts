export type Category = 'sight' | 'hotel' | 'cafe' | 'food' | 'transport';
export type AccLevel = 'ok' | 'warn' | 'na';

export interface Place {
  id: string;
  name: string;
  category: Category;
  keywords: string;
  accLevel: AccLevel;
  // 🔲 실좌표 자리 — 지금은 데모 캔버스 좌표, 실연동 시 lat/lng 사용
  coord?: { latitude: number; longitude: number };
  demoXY: { x: number; y: number };
  access: { entry: AccLevel; toilet: AccLevel; elevator: AccLevel; slope: string; width: string };
  congestion: number[];
  bestVisit: string;
}

export interface Stop { sid: number; role: 'start' | 'via' | 'end'; placeId: string; name: string; }

export interface RouteOption {
  kind: 'short' | 'safe' | 'balance';
  label: string;
  time: number;
  dist: string;
  acc: number;
  danger: number;
  ev: number;
}
