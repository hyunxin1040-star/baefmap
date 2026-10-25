"""BaefMap walking route API. No credentials or database required."""
import logging
import os
from threading import Lock
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from routing_engine import compute_walking_route

app = FastAPI(title="배프맵 경로 API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=[v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:8081,http://localhost:4173").split(",")], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
_lock = Lock()

class PlaceIn(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=37.535, le=37.600, allow_inf_nan=False)
    longitude: float = Field(ge=126.942, le=127.020, allow_inf_nan=False)

class RouteRequest(BaseModel):
    places: list[PlaceIn] = Field(min_length=2, max_length=10)
    start_place_id: str
    end_place_id: str | None = None
    route_mode: Literal["shortest", "wheelchair", "balanced"] = "wheelchair"
    mobility_profile: Literal["manual", "power", "stroller", "crutch"] = "manual"
    avoid_steep: bool = False

    @model_validator(mode="after")
    def check_places(self):
        ids = [p.id for p in self.places]
        names = [p.name for p in self.places]
        if len(set(ids)) != len(ids) or len(set(names)) != len(names):
            raise ValueError("중복 장소는 선택할 수 없습니다.")
        if self.start_place_id not in ids or (self.end_place_id and self.end_place_id not in ids):
            raise ValueError("출발지·도착지는 장소 목록에 포함되어야 합니다.")
        if self.end_place_id == self.start_place_id:
            raise ValueError("출발지와 도착지를 다르게 선택하세요.")
        return self

@app.get("/")
def index():
    return {"service":"BaefMap", "docs":"/docs", "health":"/health", "region":"서울 종로·중구", "data_source":"OpenStreetMap contributors"}

@app.get("/health")
def health():
    return {"status":"ok", "version":"0.2.0"}

def calculate(req):
    by_id = {p.id:p for p in req.places}
    return compute_walking_route([p.model_dump() for p in req.places], by_id[req.start_place_id].name, req.route_mode, by_id[req.end_place_id].name if req.end_place_id else None, req.mobility_profile, req.avoid_steep)

@app.post("/route")
def route(req: RouteRequest):
    if not _lock.acquire(blocking=False):
        raise HTTPException(429, "다른 경로를 계산 중입니다. 잠시 후 다시 시도하세요.")
    try:
        return calculate(req)
    except Exception:
        logging.exception("Route calculation failed")
        raise HTTPException(503, "지도 데이터를 불러오지 못했습니다. 잠시 후 다시 시도하세요.")
    finally:
        _lock.release()

@app.post("/route/compare")
def compare(req: RouteRequest):
    if not _lock.acquire(blocking=False):
        raise HTTPException(429, "다른 경로를 계산 중입니다. 잠시 후 다시 시도하세요.")
    try:
        accessible = calculate(req.model_copy(update={"route_mode":"wheelchair"}))
        shortest = calculate(req.model_copy(update={"route_mode":"shortest"}))
        return {"accessible":accessible,"shortest":shortest,"note":"각 모드의 최적 방문순서를 비교합니다. 경로 거리에는 장소와 도로 사이 연결 구간이 제외됩니다."}
    except Exception:
        logging.exception("Route comparison failed")
        raise HTTPException(503, "지도 데이터를 불러오지 못했습니다.")
    finally:
        _lock.release()
