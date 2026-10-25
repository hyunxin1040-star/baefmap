"""
ODsay Lab 대중교통 길찾기 API 연동.

도보 전용인 routing_engine.py와 별개로, 두 지점 사이의 지하철/버스 이동 옵션을
조회해 "도보 경로"와 비교할 수 있게 합니다.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

ODSAY_API_KEY = os.environ.get("ODSAY_API_KEY")
ODSAY_BASE_URL = "https://api.odsay.com/v1/api/searchPubTransPathT"

# ODsay 문서에 정의된, "경로를 못 찾음"이 아니라 "호출 자체가 잘못된" 에러 코드
ODSAY_NO_ROUTE_CODES = {3, 4, 5, 6, -98, -99}


def get_transit_option(
    start_latitude, start_longitude, end_latitude, end_longitude, subway_only=False, timeout=8
):
    """
    두 지점 사이의 대중교통 이동 옵션 중 추천 경로 1개를 반환합니다.

    subway_only=True면 지하철만 검색합니다. ODsay는 버스가 저상버스인지,
    역에 엘리베이터가 있는지는 알려주지 않습니다. 서울 지하철역은 대부분
    엘리베이터가 설치돼 있지만 버스는 차량별 편차가 커서, 배리어프리(휠체어) 모드에서는
    접근성을 보장할 수 없는 버스를 후보에서 제외하기 위한 옵션입니다.

    반환(성공 시):
        {
            "total_time_minutes": int,
            "fare_won": int,
            "subway_transfer_count": int,
            "bus_transfer_count": int,
            "total_walk_minutes": int,
            "total_distance_m": int,
        }
    실패/데이터 없음 시 None을 반환합니다 (호출부에서 "대중교통 정보 없음"으로 처리).
    """
    if not ODSAY_API_KEY:
        return None

    params = {
        "SX": start_longitude,
        "SY": start_latitude,
        "EX": end_longitude,
        "EY": end_latitude,
        "OPT": 0,  # 추천경로
        "SearchType": 0,  # 도시내 이동
        "SearchPathType": 1 if subway_only else 0,  # 1: 지하철만, 0: 모두(버스+지하철)
        "apiKey": ODSAY_API_KEY,
    }

    try:
        response = requests.get(ODSAY_BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    if "error" in data:
        # {"error": {"code": "-99", "message": "..."}} 형태
        return None

    result = data.get("result")
    if not result or not result.get("path"):
        return None

    best_path = result["path"][0]
    info = best_path.get("info", {})

    total_walk_time = info.get("totalWalkTime", -1)

    return {
        "total_time_minutes": info.get("totalTime"),
        "fare_won": info.get("payment"),
        "subway_transfer_count": info.get("subwayTransitCount", 0),
        "bus_transfer_count": info.get("busTransitCount", 0),
        "total_walk_minutes": total_walk_time if total_walk_time is not None and total_walk_time >= 0 else None,
        "total_distance_m": info.get("totalDistance"),
    }
