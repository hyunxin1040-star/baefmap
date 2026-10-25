/**
 * 🔲 FEATURE: 최적 경로 / 장애물 페널티
 * 출발 → 경유지(도착) → "이동 가능 경로 중 최단"
 * 장애물: 엘리베이터·에스컬레이터·급경사·지하철·저상버스(예약)
 *
 * server/ 의 FastAPI 경로 추천 엔진(실 OSM 보행망 + 다익스트라 + 방문 순서 순열 비교)을
 * 호출해 최적 방문 순서와 경로 좌표를 계산합니다.
 */
import { Stop, Place } from '@/types';
import { optimizeRoute, RouteApiResult, RouteLeg } from '@/data/api';
import { PLACE_MAP } from '@/data/mockPlaces';

export interface RoutingOptions {
  routeMode?: 'shortest' | 'wheelchair' | 'balanced';
  excludeStairs: boolean;
  excludeSteepSlope: boolean;
  preferElevator: boolean;
  preferIndoor: boolean;
  profile: 'manual' | 'power' | 'stroller' | 'crutch';
}

export interface ComputedRoute {
  order: Stop[];
  distanceM: number;
  estimatedMinutes: number;
  warningCount: number;
  informationRate: number;
  warningDetails: string[];
  segmentsCoordinates: number[][][];
  legs: RouteLeg[];
}

// excludeStairs/excludeSteepSlope 중 하나라도 켜져 있으면 휠체어 친화 경로(계단·
// wheelchair=no 구간 완전 제외)로 계산합니다. preferElevator/preferIndoor/profile은
// 이식한 엔진에서 아직 별도로 반영하지 않는 세부 옵션입니다.
function toRouteMode(opts: RoutingOptions): 'shortest' | 'wheelchair' | 'balanced' {
  if (opts.routeMode) return opts.routeMode;
  return opts.excludeStairs || opts.excludeSteepSlope ? 'wheelchair' : 'shortest';
}

export async function computeRoutes(
  stops: Stop[],
  opts: RoutingOptions,
): Promise<ComputedRoute[]> {
  if (stops.length < 2) return [];

  const startStop = stops.find((s) => s.role === 'start') ?? stops[0];

  const places: Place[] = stops.map((s) => PLACE_MAP[s.placeId]);
  if (places.some((p) => !p?.coord)) {
    throw new Error('경로를 계산하려면 모든 장소에 실제 좌표(coord)가 필요합니다.');
  }

  const result: RouteApiResult = await optimizeRoute(
    stops.map((s) => ({
      id: s.placeId,
      name: s.name,
      latitude: PLACE_MAP[s.placeId].coord!.latitude,
      longitude: PLACE_MAP[s.placeId].coord!.longitude,
    })),
    startStop.placeId,
    toRouteMode(opts),
    stops.find(s=>s.role === 'end')?.placeId,
    opts.profile,
    opts.excludeSteepSlope,
  );

  if (!result.found) {
    throw new Error(result.message ?? '경로를 찾지 못했습니다.');
  }

  const nameToStop = new Map(stops.map((s) => [s.name, s]));
  const orderedStops = result.order
    .map((name) => nameToStop.get(name))
    .filter((s): s is Stop => Boolean(s));

  return [
    {
      order: orderedStops,
      distanceM: result.distanceM ?? 0,
      estimatedMinutes: result.estimatedMinutes ?? 0,
      warningCount: result.warningCount ?? 0,
      informationRate: result.informationRate ?? 0,
      warningDetails: result.warningDetails,
      segmentsCoordinates: result.segmentsCoordinates,
      legs: result.legs,
    },
  ];
}
