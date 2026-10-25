"""
배프맵 경로 추천 엔진.

원본(Streamlit 데모, app.py)에서 실제로 사용되는 경로 계산 로직만 그대로 옮겼습니다.
Streamlit 전용 코드(st.cache_resource, session_state, UI 위젯)는 제거하고,
그래프 캐싱은 프로세스 메모리에 유지되는 간단한 dict 캐시로 대체했습니다.
"""
from functools import lru_cache
from itertools import permutations
from math import atan2, cos, factorial, radians, sin, sqrt, tan
import os
from pathlib import Path
from threading import Lock
import random
import re

import networkx as nx
import numpy as np
import osmnx as ox

from transit import get_transit_option

# 접근성 경로 평가에 필요한 OSM 태그를 보존합니다.
EXTRA_OSM_TAGS = [
    "wheelchair",
    "surface",
    "smoothness",
    "incline",
    "kerb",
    "kerb:height",
    "width",
    "highway",
    "footway",
]
ox.settings.useful_tags_way = list(
    dict.fromkeys(list(ox.settings.useful_tags_way) + EXTRA_OSM_TAGS)
)


# --------------------------------------------------
# 1. 공통 보조 함수
# --------------------------------------------------
def first_value(value):
    """OSM 태그가 리스트인 경우 첫 번째 값을 사용합니다."""
    if isinstance(value, (list, tuple, set)):
        return next(iter(value), None)
    return value


def normalized_text(value):
    value = first_value(value)
    if value is None:
        return ""
    return str(value).strip().lower()


def calculate_distance(lat1, lon1, lat2, lon2):
    """두 위도·경도 사이의 직선거리를 km 단위로 계산합니다."""
    earth_radius = 6371

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    latitude_difference = lat2 - lat1
    longitude_difference = lon2 - lon1

    value = (
        sin(latitude_difference / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(longitude_difference / 2) ** 2
    )

    central_angle = 2 * atan2(sqrt(value), sqrt(1 - value))
    return earth_radius * central_angle


def parse_incline_percent(value):
    """
    incline 값을 가능한 경우 퍼센트 숫자로 변환합니다.
    예: '8%' -> 8.0, '-5%' -> 5.0
    up/down/yes 등 수치가 아닌 값은 None으로 처리합니다.
    """
    text = normalized_text(value)

    if not text:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return abs(tan(radians(float(match.group()))) * 100) if "°" in text or "deg" in text else abs(float(match.group()))
    except ValueError:
        return None


def parse_width_meters(value):
    """width 태그에서 미터 단위 숫자를 가능한 범위에서 추출합니다."""
    text = normalized_text(value)

    if not text:
        return None

    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        width = float(match.group())
    except ValueError:
        return None

    # cm 표기가 있으면 m로 변환합니다.
    if "cm" in text:
        width /= 100

    return width


# --------------------------------------------------
# 2. OSM 보행 네트워크 및 접근성 비용
# --------------------------------------------------
_GRAPH_CACHE = {}


def load_walking_graph(center_latitude, center_longitude, radius_meters):
    """OpenStreetMap에서 보행 네트워크를 내려받습니다 (프로세스 메모리 캐시 적용)."""
    cache_key = (
        round(center_latitude, 5),
        round(center_longitude, 5),
        radius_meters,
    )

    if cache_key in _GRAPH_CACHE:
        return _GRAPH_CACHE[cache_key]

    graph = ox.graph.graph_from_point(
        center_point=(center_latitude, center_longitude),
        dist=radius_meters,
        network_type="walk",
        simplify=True,
        retain_all=False,
    )

    graph = add_accessibility_costs(graph)
    _GRAPH_CACHE[cache_key] = graph
    return graph


def edge_accessibility_profile(edge_data):
    """
    길 하나의 접근성 비용과 상태를 계산합니다.

    반환값:
    - multiplier: 거리 비용 배수
    - blocked: 휠체어 경로에서 제외할지 여부
    - warning: 주의 구간인지 여부
    - known_count: 확인 가능한 접근성 태그 수
    - total_count: 확인 대상으로 삼은 태그 수
    - reasons: 판단 이유
    """
    multiplier = 1.0
    blocked = False
    warning = False
    reasons = []

    highway = normalized_text(edge_data.get("highway"))
    wheelchair = normalized_text(edge_data.get("wheelchair"))
    surface = normalized_text(edge_data.get("surface"))
    smoothness = normalized_text(edge_data.get("smoothness"))
    kerb = normalized_text(edge_data.get("kerb"))
    incline = parse_incline_percent(edge_data.get("incline"))
    width = parse_width_meters(edge_data.get("width"))

    checked_values = [
        edge_data.get("wheelchair"),
        edge_data.get("surface"),
        edge_data.get("smoothness"),
        edge_data.get("incline"),
        edge_data.get("kerb"),
        edge_data.get("width"),
    ]
    known_count = sum(value not in (None, "", []) for value in checked_values)
    total_count = len(checked_values)

    if known_count < total_count:
        reasons.append("접근성 정보 일부 미확인")

    # 명백한 차단 조건
    if highway == "steps" or "steps" in (edge_data.get("highway") or []):
        blocked = True
        reasons.append("계단")

    if wheelchair in {"no", "private"}:
        blocked = True
        reasons.append("휠체어 접근 불가 표시")

    # 긍정 정보
    if wheelchair in {"yes", "designated"}:
        multiplier *= 0.85
        reasons.append("휠체어 접근 가능 표시")

    # 노면
    good_surfaces = {"asphalt", "concrete", "concrete:plates", "paving_stones", "sett"}
    moderate_surfaces = {"compacted", "fine_gravel", "wood", "metal", "bricks"}
    bad_surfaces = {
        "gravel", "ground", "dirt", "earth", "sand", "grass", "mud",
        "pebblestone", "rock",
    }

    if surface in good_surfaces:
        multiplier *= 0.95
    elif surface in moderate_surfaces:
        multiplier *= 1.35
        warning = True
        reasons.append(f"주의 노면: {surface}")
    elif surface in bad_surfaces:
        multiplier *= 2.5
        warning = True
        reasons.append(f"불리한 노면: {surface}")
    elif not surface:
        multiplier *= 1.10

    # 평탄도
    if smoothness in {"excellent", "good"}:
        multiplier *= 0.95
    elif smoothness in {"intermediate"}:
        multiplier *= 1.20
        warning = True
        reasons.append("보통 수준의 평탄도")
    elif smoothness in {"bad", "very_bad", "horrible", "very_horrible", "impassable"}:
        multiplier *= 2.5
        warning = True
        reasons.append(f"불량 평탄도: {smoothness}")
    elif not smoothness:
        multiplier *= 1.08

    # 경사도
    if incline is not None:
        if incline > 12:
            multiplier *= 4.0
            warning = True
            reasons.append(f"매우 급한 경사: {incline:g}%")
        elif incline > 8:
            multiplier *= 2.5
            warning = True
            reasons.append(f"급한 경사: {incline:g}%")
        elif incline > 5:
            multiplier *= 1.6
            warning = True
            reasons.append(f"경사 주의: {incline:g}%")
    else:
        multiplier *= 1.05

    # 턱
    if kerb in {"raised", "yes", "regular", "high"}:
        multiplier *= 2.0
        warning = True
        reasons.append(f"턱 주의: {kerb}")
    elif kerb in {"lowered", "flush", "no"}:
        multiplier *= 0.95
    elif not kerb:
        multiplier *= 1.05

    # 폭
    if width is not None:
        if width < 0.9:
            multiplier *= 3.0
            warning = True
            reasons.append(f"통행 폭 협소: {width:g}m")
        elif width < 1.2:
            multiplier *= 1.6
            warning = True
            reasons.append(f"통행 폭 주의: {width:g}m")
    else:
        multiplier *= 1.03

    warning = warning or blocked
    return {
        "multiplier": multiplier,
        "blocked": blocked,
        "warning": warning,
        "known_count": known_count,
        "total_count": total_count,
        "reasons": reasons,
    }


def add_accessibility_costs(graph):
    """각 edge에 wheelchair_cost와 접근성 진단 정보를 추가합니다."""
    for _, _, _, edge_data in graph.edges(keys=True, data=True):
        length = float(edge_data.get("length", 1.0))
        profile = edge_accessibility_profile(edge_data)

        edge_data["wheelchair_blocked"] = profile["blocked"]
        edge_data["accessibility_warning"] = profile["warning"]
        edge_data["accessibility_known_count"] = profile["known_count"]
        edge_data["accessibility_total_count"] = profile["total_count"]
        edge_data["accessibility_reasons"] = profile["reasons"]

        if profile["blocked"]:
            # 완전 제거 대신 매우 큰 비용을 부여하고 아래에서 경로 후보에서 제외합니다.
            edge_data["wheelchair_cost"] = length * 1_000_000
        else:
            edge_data["wheelchair_cost"] = length * profile["multiplier"]

    return graph


def graph_for_mode(graph, route_mode):
    """
    경로 모드에 맞는 그래프와 최적화 weight를 반환합니다.

    휠체어 친화 모드에서는 명백한 접근 불가 구간만 완전히 제거합니다.
    - highway=steps
    - wheelchair=no/private

    접근성 태그가 없는 길은 제거하지 않고 비용만 높입니다.
    """
    if route_mode == "wheelchair":
        wheelchair_graph = graph.copy()

        blocked_edges = [
            (u, v, key)
            for u, v, key, data in wheelchair_graph.edges(keys=True, data=True)
            if data.get("wheelchair_blocked", False)
        ]
        wheelchair_graph.remove_edges_from(blocked_edges)

        isolated_nodes = list(nx.isolates(wheelchair_graph))
        wheelchair_graph.remove_nodes_from(isolated_nodes)

        return wheelchair_graph, "wheelchair_cost"

    return graph, "length"


def get_candidate_nodes(graph, place, candidate_count=10):
    """
    장소 주변의 가까운 접근 가능 노드를 반환합니다.
    """
    if graph.number_of_nodes() == 0:
        return []

    node_ids = []
    latitudes = []
    longitudes = []

    for node_id, node_data in graph.nodes(data=True):
        if graph.degree(node_id) == 0:
            continue
        if "x" not in node_data or "y" not in node_data:
            continue

        node_ids.append(node_id)
        longitudes.append(float(node_data["x"]))
        latitudes.append(float(node_data["y"]))

    if not node_ids:
        return []

    latitudes = np.asarray(latitudes)
    longitudes = np.asarray(longitudes)

    target_latitude = float(place["latitude"])
    target_longitude = float(place["longitude"])

    latitude_distance = (latitudes - target_latitude) * 111_000
    longitude_distance = (longitudes - target_longitude) * 88_000
    squared_distance = latitude_distance ** 2 + longitude_distance ** 2

    count = min(candidate_count, len(node_ids))
    nearest_indexes = np.argpartition(squared_distance, count - 1)[:count]

    sorted_indexes = nearest_indexes[np.argsort(squared_distance[nearest_indexes])]

    return [node_ids[index] for index in sorted_indexes]


def find_best_candidate_route(graph, origin_candidates, destination_candidates, weight):
    """
    여러 출발 후보와 도착 후보를 multi-source Dijkstra 한 번으로 비교합니다.
    """
    super_source = "__temporary_super_source__"
    while super_source in graph:
        super_source += "_"

    working_graph = graph.copy()
    working_graph.add_node(super_source)

    for origin_node in origin_candidates:
        working_graph.add_edge(super_source, origin_node, length=0.0, wheelchair_cost=0.0)

    try:
        distances, paths = nx.single_source_dijkstra(
            working_graph,
            source=super_source,
            weight=weight,
        )
    except nx.NetworkXNoPath:
        return None, None, None

    reachable_destinations = [node for node in destination_candidates if node in distances]

    if not reachable_destinations:
        return None, None, None

    best_destination = min(reachable_destinations, key=lambda node: distances[node])

    route = paths[best_destination][1:]

    if len(route) < 2:
        return None, None, None

    route_edges = ox.routing.route_to_gdf(graph, route, weight=weight)

    real_distance = float(route_edges["length"].sum())
    optimized_cost = float(route_edges[weight].sum())

    return route, real_distance, optimized_cost


def get_network_route(graph, origin_place, destination_place, weight, candidate_count=10):
    """
    장소 주변 후보 노드를 찾고 multi-source Dijkstra로 최적 연결을 구합니다.
    """
    origin_candidates = get_candidate_nodes(graph, origin_place, candidate_count=candidate_count)
    destination_candidates = get_candidate_nodes(
        graph, destination_place, candidate_count=candidate_count
    )

    if not origin_candidates or not destination_candidates:
        raise nx.NetworkXNoPath("장소 주변에서 접근 가능한 보행 노드를 찾지 못했습니다.")

    route, real_distance, optimized_cost = find_best_candidate_route(
        graph, origin_candidates, destination_candidates, weight
    )

    if route is None:
        raise nx.NetworkXNoPath(
            f"{origin_place['name']}에서 {destination_place['name']}까지 "
            "접근 가능한 우회 경로를 찾지 못했습니다."
        )

    return route, real_distance, optimized_cost


def get_or_calculate_segment(
    graph, origin_place, destination_place, weight, segment_cache, candidate_count=10
):
    """
    필요한 방향의 구간만 계산하고 캐시에 저장합니다.
    """
    pair_key = (origin_place["name"], destination_place["name"])

    if pair_key in segment_cache:
        return segment_cache[pair_key]

    route, real_distance, optimized_cost = get_network_route(
        graph, origin_place, destination_place, weight, candidate_count=candidate_count
    )

    segment_cache[pair_key] = {
        "route": route,
        "real_distance": real_distance,
        "optimized_cost": optimized_cost,
    }

    return segment_cache[pair_key]


def evaluate_place_order(graph, place_order, weight, segment_cache, candidate_count=10):
    """하나의 방문 순서에 실제로 필요한 방향의 구간만 계산합니다."""
    total_real_distance = 0.0
    total_optimized_cost = 0.0
    route_segments = []

    for index in range(len(place_order) - 1):
        origin_place = place_order[index]
        destination_place = place_order[index + 1]

        segment = get_or_calculate_segment(
            graph, origin_place, destination_place, weight, segment_cache,
            candidate_count=candidate_count,
        )

        route_segments.append(segment["route"])
        total_real_distance += segment["real_distance"]
        total_optimized_cost += segment["optimized_cost"]

    return {
        "places": place_order,
        "segments": route_segments,
        "real_distance": total_real_distance,
        "optimized_cost": total_optimized_cost,
    }


def find_best_route_lazy(graph, start_place, destination_places, weight, candidate_count=10):
    """
    출발지를 고정하고 나머지 장소의 모든 순열을 정확히 비교합니다.

    전체 장소가 n개라면 후보 방문 순서는 정확히 (n-1)!개입니다.
    각 후보 순서에서 필요한 방향의 구간만 계산하며,
    이미 계산한 동일 방향 구간은 캐시에서 재사용합니다.
    """
    segment_cache = {}
    destination_count = len(destination_places)
    total_orders = factorial(destination_count)

    candidate_orders = permutations(destination_places)

    best_result = None

    for destination_order in candidate_orders:
        place_order = [start_place] + list(destination_order)

        try:
            result = evaluate_place_order(
                graph, place_order, weight, segment_cache, candidate_count=candidate_count
            )
        except nx.NetworkXNoPath:
            continue

        if best_result is None or result["optimized_cost"] < best_result["optimized_cost"]:
            best_result = result

    optimization_method = f"출발지 고정 정확 최적화 ({total_orders:,}개 방문 순서 비교)"

    if best_result is None:
        return None, None, None, None, optimization_method, segment_cache

    return (
        best_result["places"],
        best_result["segments"],
        best_result["real_distance"],
        best_result["optimized_cost"],
        optimization_method,
        segment_cache,
    )


def get_route_edge(graph, start_node, end_node, weight):
    """평행 edge 중 현재 weight가 가장 작은 edge를 반환합니다."""
    edge_options = graph.get_edge_data(start_node, end_node)

    if not edge_options:
        return None

    return min(edge_options.values(), key=lambda edge: edge.get(weight, float("inf")))


def route_to_coordinates(graph, route, weight):
    coordinates = []

    for start_node, end_node in zip(route[:-1], route[1:]):
        edge = get_route_edge(graph, start_node, end_node, weight)

        if edge is None:
            continue

        geometry = edge.get("geometry")

        if geometry is not None:
            edge_coordinates = [
                [latitude, longitude] for longitude, latitude in geometry.coords
            ]
        else:
            edge_coordinates = [
                [graph.nodes[start_node]["y"], graph.nodes[start_node]["x"]],
                [graph.nodes[end_node]["y"], graph.nodes[end_node]["x"]],
            ]

        if coordinates and edge_coordinates:
            if coordinates[-1] == edge_coordinates[0]:
                edge_coordinates = edge_coordinates[1:]

        if edge_coordinates:
            start = graph.nodes[start_node]
            if abs(edge_coordinates[-1][0]-start["y"]) + abs(edge_coordinates[-1][1]-start["x"]) < abs(edge_coordinates[0][0]-start["y"]) + abs(edge_coordinates[0][1]-start["x"]):
                edge_coordinates.reverse()
        coordinates.extend(edge_coordinates)

    return coordinates


def analyze_selected_route(graph, route_segments, weight):
    """추천 경로의 접근성 정보 확인률과 주의 구간을 계산합니다."""
    traversed_edges = 0
    warning_edges = 0
    known_count = 0
    total_count = 0
    warning_details = []

    for route in route_segments:
        for start_node, end_node in zip(route[:-1], route[1:]):
            edge = get_route_edge(graph, start_node, end_node, weight)

            if edge is None:
                continue

            traversed_edges += 1
            known_count += int(edge.get("accessibility_known_count", 0))
            total_count += int(edge.get("accessibility_total_count", 0))

            if edge.get("accessibility_warning", False):
                warning_edges += 1

                for reason in edge.get("accessibility_reasons", []):
                    if reason not in warning_details:
                        warning_details.append(reason)

    information_rate = known_count / total_count * 100 if total_count else 0
    if known_count < total_count:
        warning_details.append("접근성 정보가 확인되지 않은 구간이 있습니다. 현장 통행 가능 여부를 확인하세요.")

    return {
        "edge_count": traversed_edges,
        "warning_count": warning_edges,
        "information_rate": information_rate,
        "warning_details": warning_details,
    }


def calculate_graph_area(selected_places):
    """selected_places: [{"latitude":..., "longitude":...}, ...]"""
    center_latitude = sum(p["latitude"] for p in selected_places) / len(selected_places)
    center_longitude = sum(p["longitude"] for p in selected_places) / len(selected_places)

    maximum_distance_km = 0

    for place in selected_places:
        distance_km = calculate_distance(
            center_latitude, center_longitude, place["latitude"], place["longitude"]
        )
        maximum_distance_km = max(maximum_distance_km, distance_km)

    radius_meters = int(max(3000, maximum_distance_km * 1000 + 2000))

    return center_latitude, center_longitude, radius_meters


def build_pair_cost_matrix(graph, places, weight, candidate_count=10):
    """
    장소 목록의 모든 순서쌍(A→B)에 대해 실제 도로망 구간을 한 번씩만 계산해
    조회 테이블로 만듭니다. 이후의 방문 순서 탐색(순열 비교든 2-opt든)은
    이 테이블만 보고 계산하므로, "도로망 탐색 시간"과 "방문 순서 탐색 시간"이
    분리됩니다.
    """
    segment_cache = {}
    pair_routes = {}
    pair_real_distances = {}
    pair_costs = {}

    for origin_place in places:
        for destination_place in places:
            if origin_place["name"] == destination_place["name"]:
                continue

            try:
                segment = get_or_calculate_segment(
                    graph, origin_place, destination_place, weight, segment_cache,
                    candidate_count=candidate_count,
                )
            except nx.NetworkXNoPath:
                continue

            pair_key = (origin_place["name"], destination_place["name"])
            pair_routes[pair_key] = segment["route"]
            pair_real_distances[pair_key] = segment["real_distance"]
            pair_costs[pair_key] = segment["optimized_cost"]

    return pair_routes, pair_real_distances, pair_costs, segment_cache


WALKING_SPEED_KMH = 3


def build_pair_time_matrix(graph, places, weight, route_mode, candidate_count=10):
    """
    build_pair_cost_matrix에 "이 구간은 도보가 빠른지, 대중교통이 빠른지"를 더해
    실제 예상 소요시간(분) 기준의 조회 테이블을 만듭니다. 방문 순서 탐색은
    거리/접근성 비용 대신 이 시간 표를 기준으로 이뤄집니다.

    배리어프리(휠체어) 모드에서는 대중교통 후보를 지하철로만 제한합니다.
    ODsay API가 저상버스 여부나 역 엘리베이터 유무까지는 확인해주지 않아서,
    검증되지 않은 버스를 접근성 경로에 포함시키지 않기 위함입니다.
    """
    pair_routes, pair_real_distances, pair_costs, segment_cache = build_pair_cost_matrix(
        graph, places, weight, candidate_count=candidate_count
    )

    subway_only = route_mode == "wheelchair"
    place_by_name = {p["name"]: p for p in places}

    pair_times = {}
    pair_mode = {}
    pair_transit = {}

    for pair_key, real_distance in pair_real_distances.items():
        origin_name, destination_name = pair_key
        walk_minutes = real_distance / 1000 / WALKING_SPEED_KMH * 60

        origin_place = place_by_name[origin_name]
        destination_place = place_by_name[destination_name]

        transit = get_transit_option(
            origin_place["latitude"], origin_place["longitude"],
            destination_place["latitude"], destination_place["longitude"],
            subway_only=subway_only,
        )

        transit_minutes = transit["total_time_minutes"] if transit else None

        if transit_minutes is not None and transit_minutes < walk_minutes:
            pair_times[pair_key] = transit_minutes
            pair_mode[pair_key] = "transit"
            pair_transit[pair_key] = transit
        else:
            pair_times[pair_key] = walk_minutes
            pair_mode[pair_key] = "walk"
            pair_transit[pair_key] = None

    return pair_routes, pair_real_distances, pair_times, pair_mode, pair_transit, segment_cache


def route_cost_from_places(place_order, pair_costs):
    """주어진 장소 순서의 총 최적화 비용을 계산합니다."""
    total_cost = 0.0

    for index in range(len(place_order) - 1):
        pair_key = (place_order[index]["name"], place_order[index + 1]["name"])

        if pair_key not in pair_costs:
            return float("inf")

        total_cost += pair_costs[pair_key]

    return total_cost


def nearest_neighbor_order(start_place, destination_places, pair_costs, first_step_rank=0, top_k=1, rng=None):
    """
    출발지에서 시작해 아직 방문하지 않은 장소 중 비용이 낮은 장소를 차례로 선택합니다.
    (참고: 여기서의 "비용"은 이미 접근성 가중치가 반영된 pair_costs이므로,
    휠체어 친화 모드에서는 이 함수 자체가 곧 "접근성 좋은 장소부터 선택"과 같습니다.)

    다양한 초기 경로를 만들기 위한 변형 파라미터:
    - first_step_rank: 첫 번째 선택만 몇 번째로 가까운 장소로 할지 (0=제일 가까운 곳, 1=두 번째, ...)
    - top_k>1: 두 번째 선택부터는 매 단계 가장 가까운 top_k개 후보 중 하나를 무작위로 선택
      (rng를 지정하지 않으면 파이썬 전역 random 모듈을 사용합니다)
    """
    rng = rng or random
    route = [start_place]
    remaining = destination_places.copy()
    step = 0

    while remaining:
        current_name = route[-1]["name"]

        reachable_places = [
            place for place in remaining
            if (current_name, place["name"]) in pair_costs
        ]

        if not reachable_places:
            return None

        reachable_places.sort(key=lambda place: pair_costs[(current_name, place["name"])])

        if step == 0 and first_step_rank > 0:
            next_place = reachable_places[min(first_step_rank, len(reachable_places) - 1)]
        elif top_k > 1:
            next_place = rng.choice(reachable_places[:min(top_k, len(reachable_places))])
        else:
            next_place = reachable_places[0]

        route.append(next_place)
        remaining.remove(next_place)
        step += 1

    return route


def multi_start_route_order(start_place, destination_places, pair_costs, restart_count=10, seed=0):
    """
    최근접 이웃은 첫 선택 하나가 나쁘면 2-opt로도 못 벗어나는 지역 최적해에 갇힐 수 있습니다.
    서로 다른 방식으로 만든 초기 경로 여러 개(기본 10개)에 각각 2-opt를 적용하고,
    그중 총 비용이 가장 낮은 결과를 선택해 이 문제를 완화합니다.
    """
    rng = random.Random(seed)
    initial_routes = [
        # 1) 기본 최근접 이웃 (항상 제일 가까운 곳부터)
        nearest_neighbor_order(start_place, destination_places, pair_costs),
        # 2) 두 번째로 가까운 장소부터 시작
        nearest_neighbor_order(start_place, destination_places, pair_costs, first_step_rank=1),
        # 3) 세 번째로 가까운 장소부터 시작
        nearest_neighbor_order(start_place, destination_places, pair_costs, first_step_rank=2),
        # 4) 완전 무작위 순서 (탐색 다양성 확보)
        _shuffled_order(start_place, destination_places, rng),
        _shuffled_order(start_place, destination_places, rng),
    ]

    # 5) 나머지는 매 단계 가까운 후보 3개 중 무작위 선택 (편향된 무작위 탐색)
    while len(initial_routes) < restart_count:
        initial_routes.append(
            nearest_neighbor_order(
                start_place, destination_places, pair_costs, top_k=3, rng=rng
            )
        )

    best_order, best_cost = None, float("inf")

    for initial_order in initial_routes:
        if initial_order is None:
            continue

        candidate_order, candidate_cost = improve_route_with_two_opt(initial_order, pair_costs)

        if candidate_cost < best_cost:
            best_order, best_cost = candidate_order, candidate_cost

    return best_order, best_cost


def _shuffled_order(start_place, destination_places, rng):
    shuffled = destination_places.copy()
    rng.shuffle(shuffled)
    return [start_place] + shuffled


def improve_route_with_two_opt(place_order, pair_costs):
    """
    출발지는 고정한 채 2-opt 방식으로 방문 순서를 반복 개선합니다.
    열린 경로이므로 마지막 장소에서 출발지로 돌아오지는 않습니다.
    """
    best_order = place_order.copy()
    best_cost = route_cost_from_places(best_order, pair_costs)

    improved = True

    while improved:
        improved = False

        # 인덱스 0은 출발지이므로 뒤집지 않습니다.
        for start_index in range(1, len(best_order) - 1):
            for end_index in range(start_index + 1, len(best_order)):
                candidate_order = (
                    best_order[:start_index]
                    + list(reversed(best_order[start_index:end_index + 1]))
                    + best_order[end_index + 1:]
                )

                candidate_cost = route_cost_from_places(candidate_order, pair_costs)

                if candidate_cost + 1e-9 < best_cost:
                    best_order = candidate_order
                    best_cost = candidate_cost
                    improved = True
                    break

            if improved:
                break

    return best_order, best_cost


def exact_route_order(start_place, destination_places, pair_costs):
    """장소 수가 적을 때 모든 방문 순서를 비교해 정확한 최적해를 찾습니다."""
    best_order = None
    best_cost = float("inf")

    for destination_order in permutations(destination_places):
        candidate_order = [start_place] + list(destination_order)
        candidate_cost = route_cost_from_places(candidate_order, pair_costs)

        if candidate_cost < best_cost:
            best_order = candidate_order
            best_cost = candidate_cost

    return best_order, best_cost


# 정확 최적화(순열 비교)를 쓰는 최대 장소 수. 이보다 많으면 근사 최적화로 전환합니다.
EXACT_OPTIMIZATION_PLACE_LIMIT = 8


def find_best_multimodal_route(graph, start_place, destination_places, weight, route_mode, candidate_count=10):
    """
    find_best_route_auto의 다중 교통수단 버전.

    거리/접근성 비용이 아니라 "구간별 예상 소요시간"(도보 vs 대중교통 중 빠른 쪽)을
    기준으로 방문 순서를 탐색합니다. 장소 수에 따른 정확/근사 최적화 자동 전환은 동일합니다.
    """
    pair_routes, pair_real_distances, pair_times, pair_mode, pair_transit, segment_cache = (
        build_pair_time_matrix(
            graph, [start_place] + destination_places, weight, route_mode,
            candidate_count=candidate_count,
        )
    )

    total_place_count = len(destination_places) + 1

    if total_place_count <= EXACT_OPTIMIZATION_PLACE_LIMIT:
        best_places, lowest_total_minutes = exact_route_order(start_place, destination_places, pair_times)
        optimization_method = "정확 최적화(순열 비교, 소요시간 기준)"
    else:
        best_places, lowest_total_minutes = multi_start_route_order(start_place, destination_places, pair_times)
        optimization_method = "근사 최적화(다중 시작 최근접 이웃 + 2-opt, 소요시간 기준)"

    if best_places is None or lowest_total_minutes == float("inf"):
        return None

    legs = []
    total_distance_m = 0.0

    for index in range(len(best_places) - 1):
        pair_key = (best_places[index]["name"], best_places[index + 1]["name"])

        if pair_key not in pair_times:
            return None

        mode = pair_mode[pair_key]
        legs.append({
            "from": best_places[index]["name"],
            "to": best_places[index + 1]["name"],
            "mode": mode,
            "minutes": pair_times[pair_key],
            "walk_distance_m": pair_real_distances.get(pair_key),
            "walk_route": pair_routes.get(pair_key) if mode == "walk" else None,
            "transit": pair_transit.get(pair_key),
        })

        if mode == "walk":
            total_distance_m += pair_real_distances[pair_key]

    return {
        "best_route": best_places,
        "legs": legs,
        "total_minutes": lowest_total_minutes,
        "total_distance_m": total_distance_m,
        "optimization_method": optimization_method,
    }


def benchmark_route_ordering(places, start_place_name, route_mode, max_places=None):
    """
    방문 순서 탐색 알고리즘의 계산 시간을 장소 수별로 측정합니다.

    도로망 구간 비용은 한 번만 계산해서 표로 만들어두고(측정 대상에서 제외),
    그 표 위에서 다음 두 가지 탐색 방식의 순수 계산 시간만 비교합니다.
    - 정확 최적화(모든 순열 비교): 장소 수가 늘어나면 (n-1)! 로 폭발적으로 증가
    - 근사 최적화(다중 시작 최근접 이웃 + 2-opt, 10회 재시도): 장소 수에 다항식 수준으로 증가

    반환: [{n_places, exact_time_ms, exact_cost, permutation_count,
            approx_time_ms, approx_cost, quality_gap_percent}, ...]
    """
    import time

    start_place = next(p for p in places if p["name"] == start_place_name)
    all_destinations = [p for p in places if p["name"] != start_place_name]

    if max_places is not None:
        all_destinations = all_destinations[: max_places - 1]

    center_latitude, center_longitude, radius_meters = calculate_graph_area(places)
    base_graph = load_walking_graph(
        round(center_latitude, 5), round(center_longitude, 5), int(radius_meters * 1.7)
    )
    graph, weight = graph_for_mode(base_graph, route_mode)

    # 구간 비용 표는 전체 장소 기준으로 한 번만 계산 (이후 재사용, 측정 대상 아님)
    pair_routes, pair_real_distances, pair_costs, _cache = build_pair_cost_matrix(
        graph, [start_place] + all_destinations, weight
    )

    results = []

    # 정확 최적화는 순열 수가 감당 가능한 범위(<= 8곳)까지만 측정합니다.
    # (예: 10곳이면 9! = 362,880개 순서를 매번 비교해야 해서 데모 목적에 맞지 않게 느려집니다.)
    EXACT_DEMO_LIMIT = 9

    for k in range(2, len(all_destinations) + 1):
        destinations = all_destinations[:k]
        permutation_count = factorial(k)

        exact_time_ms = None
        exact_cost = None
        if k + 1 <= EXACT_DEMO_LIMIT:
            t0 = time.perf_counter()
            _order, exact_cost = exact_route_order(start_place, destinations, pair_costs)
            exact_time_ms = (time.perf_counter() - t0) * 1000
            if exact_cost == float("inf"):
                exact_cost = None

        t0 = time.perf_counter()
        _approx_order, approx_cost = multi_start_route_order(start_place, destinations, pair_costs)
        if approx_cost == float("inf"):
            approx_cost = None
        approx_time_ms = (time.perf_counter() - t0) * 1000

        quality_gap_percent = None
        if exact_cost not in (None, 0) and approx_cost is not None:
            quality_gap_percent = (approx_cost - exact_cost) / exact_cost * 100

        results.append({
            "n_places": k + 1,
            "permutation_count": permutation_count,
            "exact_time_ms": exact_time_ms,
            "exact_cost": exact_cost,
            "approx_time_ms": approx_time_ms,
            "approx_cost": approx_cost,
            "quality_gap_percent": quality_gap_percent,
        })

    return results


def compute_best_route(places, start_place_name, route_mode):
    """
    엔진 최상위 진입점 (도보 + 대중교통 혼합).

    places: [{"name", "latitude", "longitude"}, ...] (2곳 이상)
    start_place_name: 출발지 이름 (places 중 하나)
    route_mode: "shortest" | "wheelchair"
      - "shortest": 구간별로 도보/버스/지하철 중 가장 빠른 수단을 자유롭게 선택
      - "wheelchair": 버스는 후보에서 제외(저상버스 여부 미확인), 도보 또는 지하철만 선택

    반환: dict (best_route, segments_coordinates, distance_m, total_minutes, legs,
                analysis, optimization_method)
          경로를 찾지 못하면 best_route가 None.
    """
    start_place = next(p for p in places if p["name"] == start_place_name)
    destination_places = [p for p in places if p["name"] != start_place_name]

    center_latitude, center_longitude, radius_meters = calculate_graph_area(places)

    # 원본과 동일하게 우회 탐색을 위해 반경을 최대 3단계로 넓힙니다.
    radius_multipliers = [1.0, 1.7, 2.5]

    for radius_multiplier in radius_multipliers:
        current_radius = int(radius_meters * radius_multiplier)

        base_graph = load_walking_graph(
            round(center_latitude, 5), round(center_longitude, 5), current_radius
        )
        current_graph, current_weight = graph_for_mode(base_graph, route_mode)

        try:
            multimodal = find_best_multimodal_route(
                current_graph, start_place, destination_places, current_weight, route_mode,
                candidate_count=10,
            )
        except nx.NetworkXNoPath:
            continue

        if multimodal is not None:
            walk_route_segments = [
                leg["walk_route"] for leg in multimodal["legs"] if leg["mode"] == "walk"
            ]

            if walk_route_segments:
                route_analysis = analyze_selected_route(
                    current_graph, walk_route_segments, current_weight
                )
            else:
                route_analysis = {
                    "edge_count": 0, "warning_count": 0,
                    "information_rate": 0, "warning_details": [],
                }

            coordinates = []
            for leg in multimodal["legs"]:
                if leg["mode"] == "walk":
                    coordinates.append(
                        route_to_coordinates(current_graph, leg["walk_route"], current_weight)
                    )
                else:
                    # 대중교통 구간의 실제 노선 좌표는 별도 API(노선 그래픽 데이터)가 필요해
                    # 지금은 지도에 그리지 않고 빈 좌표로 둡니다.
                    coordinates.append([])

            return {
                "best_route": [p["name"] for p in multimodal["best_route"]],
                "segments_coordinates": coordinates,
                "distance_m": multimodal["total_distance_m"],
                "total_minutes": multimodal["total_minutes"],
                "legs": multimodal["legs"],
                "optimization_method": multimodal["optimization_method"],
                "analysis": route_analysis,
                "used_radius_meters": current_radius,
            }

    return {
        "best_route": None,
        "segments_coordinates": None,
        "distance_m": None,
        "total_minutes": None,
        "legs": None,
        "optimization_method": None,
        "analysis": None,
        "used_radius_meters": None,
    }


# Deployment entry: bounded regional graph, fixed anchors, walking-only routing.
REGION_CENTER = (37.568, 126.982)
REGION_RADIUS = 4000
_REGION_LOCK = Lock()

def regional_graph():
    with _REGION_LOCK:
        if "region" not in _GRAPH_CACHE:
            cache = Path(__file__).parent / "data" / "seoul.graphml"
            if cache.exists():
                graph = ox.load_graphml(cache)
            else:
                ox.settings.requests_timeout = 90
                graph = ox.graph_from_point(REGION_CENTER, dist=REGION_RADIUS, network_type="walk", simplify=True, retain_all=True)
            _GRAPH_CACHE["region"] = add_accessibility_costs(graph)
        return _GRAPH_CACHE["region"]

def compute_walking_route(places, start_place_name, route_mode="wheelchair", end_name=None, mobility_profile="manual", avoid_steep=False):
    base = regional_graph()
    def allowed(u, v, k):
        d = base[u][v][k]
        if route_mode == "shortest":
            return True
        return not d.get("wheelchair_blocked") and not (avoid_steep and (parse_incline_percent(d.get("incline")) or 0) > 8)
    graph = nx.subgraph_view(base, filter_edge=allowed)
    weight = "length" if route_mode == "shortest" else "wheelchair_cost"
    if route_mode == "balanced":
        # A separate attribute preserves the shared graph for concurrent reads.
        for _, _, _, d in base.edges(keys=True, data=True):
            d["balanced_cost"] = (d["length"] + d["wheelchair_cost"]) / 2
        weight = "balanced_cost"
    anchors = {}
    snap = {}
    for p in places:
        candidates = get_candidate_nodes(graph, p, candidate_count=1)
        if not candidates:
            return {"found": False, "message": "주변 보행 노드를 찾지 못했습니다."}
        node = candidates[0]
        n = graph.nodes[node]
        gap = calculate_distance(p["latitude"], p["longitude"], n["y"], n["x"]) * 1000
        if gap > 150:
            return {"found": False, "message": p["name"] + " 주변 150m 안에 연결 가능한 보행로가 없습니다."}
        anchors[p["name"]] = node
        snap[p["name"]] = round(gap, 1)
    pair_paths, costs, distances = {}, {}, {}
    for p in places:
        source = anchors[p["name"]]
        lengths, paths = nx.single_source_dijkstra(graph, source, weight=weight)
        for q in places:
            if p is q or anchors[q["name"]] not in lengths:
                continue
            key = (p["name"], q["name"])
            route = paths[anchors[q["name"]]]
            pair_paths[key] = route
            costs[key] = lengths[anchors[q["name"]]]
            distances[key] = sum(get_route_edge(graph,u,v,weight)["length"] for u,v in zip(route[:-1],route[1:]))
    start = next(p for p in places if p["name"] == start_place_name)
    end = next((p for p in places if p["name"] == end_name), None)
    vias = [p for p in places if p is not start and p is not end]
    if len(places) <= 8:
        orders = ([start]+list(v)+([end] if end else []) for v in permutations(vias))
        method = "출발·도착 고정 정확 최적화" if end else "출발지 고정 정확 최적화"
        best = min(orders, key=lambda v: route_cost_from_places(v,costs))
    else:
        # Fixed endpoints with full directed path re-evaluation for every reversal.
        rng = random.Random(0)
        best, best_cost = None, float("inf")
        for trial in range(12):
            v = vias.copy()
            rng.shuffle(v)
            order = [start]+v+([end] if end else [])
            cost = route_cost_from_places(order,costs)
            improved = True
            while improved:
                improved = False
                for i in range(1,len(order)-(1 if end else 0)):
                    for j in range(i+1,len(order)-(1 if end else 0)):
                        candidate = order[:i]+order[i:j+1][::-1]+order[j+1:]
                        c = route_cost_from_places(candidate,costs)
                        if c+1e-9 < cost:
                            order,cost,improved = candidate,c,True
            if cost < best_cost:
                best,best_cost = order,cost
        method = "다중 시작 + 2-opt (근사)"
        if best is None:
            return {"found": False,"message":"방문 가능한 연결 경로를 찾지 못했습니다."}
    if route_cost_from_places(best,costs) == float("inf"):
        return {"found":False,"message":"설정한 조건으로 모든 장소를 연결할 수 없습니다. 조건이나 장소를 바꿔주세요."}
    keys = [(a["name"],b["name"]) for a,b in zip(best[:-1],best[1:])]
    routes = [pair_paths[k] for k in keys]
    analysis = analyze_selected_route(graph,routes,weight)
    analysis["warning_details"].append("장소 표시점과 도로 연결점 사이(최대 150m)는 경로·접근성 계산에서 제외됩니다.")
    analysis["warning_details"].append("OSM 태그 기반의 실험적 추천입니다. 현장 검증을 거친 통행 보장이 아닙니다.")
    speed = {"manual":3,"power":4,"stroller":3.5,"crutch":2.5}[mobility_profile]
    coords = []
    for route in routes:
        coords.append(route_to_coordinates(graph,route,weight) if len(route)>1 else [[graph.nodes[route[0]]["y"],graph.nodes[route[0]]["x"]]])
    return {"found":True,"order":[p["name"] for p in best],"segments_coordinates":coords,"distance_m":sum(distances[k] for k in keys),"estimated_minutes":round(sum(distances[k] for k in keys)/1000/speed*60),"warning_count":analysis["warning_count"],"information_rate":analysis["information_rate"],"warning_details":analysis["warning_details"],"optimization_method":method,"snap_distances_m":snap,"legs":[{"from_place":k[0],"to_place":k[1],"mode":"walk","minutes":distances[k]/1000/speed*60,"walk_distance_m":distances[k],"transit":None} for k in keys]}
