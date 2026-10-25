import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import networkx as nx
import pytest
from shapely.geometry import LineString
from fastapi.testclient import TestClient
import routing_engine as r
from main import app

@pytest.fixture
def graph(monkeypatch):
    g=nx.MultiDiGraph(crs="epsg:4326")
    for i,(x,y) in enumerate([(126.98,37.56),(126.981,37.56),(126.98,37.561),(126.982,37.56)]):g.add_node(i,x=x,y=y)
    for u,v,d,attrs in [(0,1,10,{"highway":"steps"}),(0,2,80,{}),(2,1,80,{}),(1,3,30,{})]:
        g.add_edge(u,v,length=d,**attrs);g.add_edge(v,u,length=d,**attrs)
    r.add_accessibility_costs(g)
    monkeypatch.setattr(r,"regional_graph",lambda:g)
    return g

def places(graph,ids=(0,1,3)):
    return [{"id":str(i),"name":str(i),"latitude":graph.nodes[i]["y"],"longitude":graph.nodes[i]["x"]} for i in ids]

def test_stairs_and_fixed_destination(graph):
    p=places(graph)
    short=r.compute_walking_route(p,"0","shortest",end_name="3")
    safe=r.compute_walking_route(p,"0","wheelchair",end_name="3")
    assert short["distance_m"]==40
    assert safe["distance_m"]==190
    assert safe["order"]==["0","1","3"]
    assert safe["information_rate"]==0
    assert any("확인되지" in w for w in safe["warning_details"])

def test_disconnected_fails(graph):
    graph.remove_edges_from(list(graph.edges(2,keys=True)))
    assert not r.compute_walking_route(places(graph),"0","wheelchair")["found"]

def test_steep_constraint(graph):
    for _,_,_,d in graph.edges(keys=True,data=True):d["incline"]="10%"
    assert not r.compute_walking_route(places(graph),"0","wheelchair",avoid_steep=True)["found"]

def test_same_anchor_zero_distance(graph):
    p=places(graph,(0,1));p[1].update(latitude=p[0]["latitude"],longitude=p[0]["longitude"])
    result=r.compute_walking_route(p,"0","wheelchair")
    assert result["found"] and result["distance_m"]==0

def test_reversed_geometry(graph):
    graph[0][2][0]["geometry"]=LineString([(126.98,37.561),(126.98,37.56)])
    coords=r.route_to_coordinates(graph,[0,2],"length")
    assert coords[0]==[37.56,126.98]

def test_units_and_blocking():
    assert r.parse_width_meters("90cm")==0.9
    assert 12 < r.parse_incline_percent("8°") < 15
    assert r.edge_accessibility_profile({"highway":["footway","steps"]})["blocked"]
    assert r.edge_accessibility_profile({"wheelchair":"no"})["blocked"]

def test_request_validation_and_health(graph):
    c=TestClient(app)
    assert c.get("/health").status_code==200
    p=places(graph)
    assert c.post("/route",json={"places":p,"start_place_id":"0","route_mode":"wheelchair"}).json()["found"]
    assert c.post("/route",json={"places":p+[p[0]],"start_place_id":"0"}).status_code==422
    p[0]["latitude"]=0
    assert c.post("/route",json={"places":p,"start_place_id":"0"}).status_code==422

def test_compare(graph):
    c=TestClient(app)
    result=c.post("/route/compare",json={"places":places(graph),"start_place_id":"0","end_place_id":"3"}).json()
    assert result["accessible"]["distance_m"] > result["shortest"]["distance_m"]
