"""Save a regional OSM graph in the deploy artifact (not runtime storage)."""
from pathlib import Path
import osmnx as ox
from routing_engine import REGION_CENTER, REGION_RADIUS
ox.settings.requests_timeout = 180
p = Path(__file__).parent / "data" / "seoul.graphml"
snapshot = Path(__file__).resolve().parents[1] / "seoul.graphml.gz"
if snapshot.exists():
    print("Using bundled OpenStreetMap snapshot (2026-10-25)")
elif not p.exists():
    g = ox.graph_from_point(REGION_CENTER, dist=REGION_RADIUS, network_type="walk", simplify=True, retain_all=True)
    p.parent.mkdir(exist_ok=True)
    ox.save_graphml(g,p)
    print("Saved",g.number_of_nodes(),"nodes",g.number_of_edges(),"edges")
