import { Place } from '@/types';

/**
 * 🔲 REAL DATA SLOT
 * 실 연동 대상(예정):
 *  - 공공데이터포털: 무장애 관광 정보
 *  - 서울교통공사: 역사 엘리베이터/에스컬레이터/출구
 *  - 저상버스 노선·예약 API
 *  - OpenStreetMap: wheelchair / incline 태그
 *
 * 지금은 mock 반환. 실 API 붙일 때 이 함수 본문만 교체하면
 * 화면 코드는 수정 불필요(같은 Place[] 형태 유지).
 */
export async function fetchPlaces(): Promise<Place[]> {
  const { PLACES } = await import('@/data/mockPlaces');
  return PLACES;
  // TODO: const res = await fetch(`${API_BASE}/barrier-free/places?area=jongno-jung`);
  //       return (await res.json()).map(mapToPlace);
}

// server/ (FastAPI 경로 추천 엔진)의 주소. 휴대폰(Expo Go)이 같은 Wi-Fi에서
// 접속할 수 있도록 PC의 LAN IP로 설정했습니다. 네트워크가 바뀌면 다시 바꿔주세요.
const ROUTING_API_BASE = process.env.EXPO_PUBLIC_ROUTING_API_BASE?.replace(/\/$/, '') ?? ''; 

export interface RoutingPlaceInput {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
}

export interface TransitOption {
  totalTimeMinutes: number | null;
  fareWon: number | null;
  subwayTransferCount: number | null;
  busTransferCount: number | null;
}

export interface RouteLeg {
  fromPlace: string;
  toPlace: string;
  mode: 'walk' | 'transit';
  minutes: number;
  walkDistanceM: number | null;
  transit: TransitOption | null;
}

export interface RouteApiResult {
  found: boolean;
  order: string[];
  segmentsCoordinates: number[][][];
  distanceM: number | null;
  estimatedMinutes: number | null;
  warningCount: number | null;
  informationRate: number | null;
  warningDetails: string[];
  optimizationMethod: string | null;
  legs: RouteLeg[];
  message?: string;
}

export async function optimizeRoute(
  places: RoutingPlaceInput[],
  startPlaceId: string,
  routeMode: 'shortest' | 'wheelchair' | 'balanced',
  endPlaceId?: string,
  profile: 'manual' | 'power' | 'stroller' | 'crutch' = 'manual',
  avoidSteep = false,
): Promise<RouteApiResult> {
  if (!ROUTING_API_BASE) throw new Error('경로 서버 주소가 설정되지 않았습니다.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 180000);
  let res: Response;
  try {
  res = await fetch(`${ROUTING_API_BASE}/route`, {
    method: 'POST',
    signal: controller.signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      places,
      start_place_id: startPlaceId,
      route_mode: routeMode,
      end_place_id: endPlaceId,
      mobility_profile: profile,
      avoid_steep: avoidSteep,
    }),
  });

  } catch(error) { throw new Error(controller.signal.aborted ? '서버 응답이 늦어지고 있습니다. 잠시 후 다시 시도하세요.' : '서버에 연결하지 못했습니다. 네트워크와 서버 상태를 확인하세요.'); } finally { clearTimeout(timer); }
  if (!res.ok) {
    const error = await res.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : '경로 요청에 실패했습니다 (' + res.status + ').');
  }

  const data = await res.json();

  return {
    found: data.found,
    order: data.order ?? [],
    segmentsCoordinates: data.segments_coordinates ?? [],
    distanceM: data.distance_m ?? null,
    estimatedMinutes: data.estimated_minutes ?? null,
    warningCount: data.warning_count ?? null,
    informationRate: data.information_rate ?? null,
    warningDetails: data.warning_details ?? [],
    optimizationMethod: data.optimization_method ?? null,
    legs: (data.legs ?? []).map((leg: any) => ({
      fromPlace: leg.from_place,
      toPlace: leg.to_place,
      mode: leg.mode,
      minutes: leg.minutes,
      walkDistanceM: leg.walk_distance_m ?? null,
      transit: leg.transit
        ? {
            totalTimeMinutes: leg.transit.total_time_minutes ?? null,
            fareWon: leg.transit.fare_won ?? null,
            subwayTransferCount: leg.transit.subway_transfer_count ?? null,
            busTransferCount: leg.transit.bus_transfer_count ?? null,
          }
        : null,
    })),
    message: data.message,
  };
}
