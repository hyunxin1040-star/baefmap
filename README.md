# BaefMap / 배프맵

기존 Expo SDK 51 UI와 OSMnx/NetworkX 프로토타입을 연결한 서울 종로·중구 보행 경로 MVP입니다. 저장소의 기존 app.py와 requirements.txt는 Streamlit 원본으로 보존됩니다.

## 실행

- 웹: npm ci, npm run typecheck, EXPO_PUBLIC_ROUTING_API_BASE를 설정하고 npm run build:web
- API: pip install -r server/requirements.txt, python server/prepare_graph.py, uvicorn main:app --app-dir server --host 0.0.0.0 --port 8000
- 테스트: pip install pytest httpx, python -m pytest server/tests -q

## 무료 배포

Netlify: 루트 netlify.toml 사용. EXPO_PUBLIC_ROUTING_API_BASE에 Render URL 지정. 이 값은 공개 API 주소이며 비밀키를 넣지 않습니다.
Render: Python 웹 서비스, plan free, 빌드 명령 pip install -r server/requirements.txt && python server/prepare_graph.py, 시작 명령 uvicorn main:app --app-dir server --host 0.0.0.0 --port $PORT --workers 1. CORS_ORIGINS에 Netlify 사이트 원점을 지정합니다.

## 제공 기능과 한계

- 실제 OSM 보행 경로, 고정 출발·도착, 최대 10개 장소. 총 8개 이하는 정확 탐색, 이후 다중 시작 + 2-opt.
- 최단/접근성 우선/균형. 후자의 두 모드는 계단·wheelchair=no를 제외하며, 8% 초과 확인된 경사를 선택적으로 제외합니다.
- 이동 프로필은 추정 속도에 반영됩니다. 가중치는 사용자 연구로 보정되지 않은 휴리스틱입니다.
- 장소의 대표 좌표와 도로 연결점 사이 최대 150m는 경로 거리 및 접근성 계산에서 제외하며 경고합니다. 접근 가능한 출입구로 검증된 좌표가 아닙니다.
- 정보 없음은 안전을 의미하지 않습니다. 확인률은 6개 접근성 태그의 입력률이며 안전 점수가 아닙니다.
- 실제 경로가 단절되면 실패를 반환합니다. 서울역 대표점 등에서 접근성 경로를 못 찾을 수 있습니다. 직선이나 일반 경로로 대체하지 않습니다.
- 시설 정보·후기·혼잡도·실시간 위치추적은 검증된 데이터가 없어 제공하지 않습니다.
- OSM: https://www.openstreetmap.org/copyright . 웹 지도는 Leaflet 1.9.4와 OSM 타일을 사용합니다.
- 무료 Render는 유휴 시 중지되어 첫 요청에 기동 대기가 있습니다. 요금제는 무료로 유지하며 워크스페이스의 사용량 한도가 적용됩니다.

## 배포 도로망 스냅샷

seoul.graphml.gz는 2026-10-25 OpenStreetMap에서 OSMnx walk 방식으로 수집한 중심 37.568,126.982 / 반경 4km 도로망입니다(28,775 노드, 79,630 방향 간선). ODbL: https://www.openstreetmap.org/copyright . 원본 데이터의 접근성 태그 결측은 보완하거나 안전으로 추정하지 않습니다. 빌드·실행은 이 스냅샷을 우선 사용하여 외부 Overpass 접속 장애에 의존하지 않습니다. 데이터 갱신은 별도 재수집이 필요합니다.

웹: https://baefmap-seoul.netlify.app
API: https://baefmap-api.onrender.com/docs
