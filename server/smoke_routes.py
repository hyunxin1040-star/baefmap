import json,time
from pathlib import Path
from routing_engine import compute_walking_route
cases=[[("서울역",37.5547,126.9707),("서울시립미술관",37.5641,126.9738)],[("광화문광장",37.572,126.9769),("경복궁",37.5762,126.9769),("인사동길",37.574,126.985)]]
results=[]
for case in cases:
    p=[dict(name=n,latitude=a,longitude=b) for n,a,b in case]
    for mode in ["shortest","wheelchair","balanced"]:
        t=time.perf_counter();r=compute_walking_route(p,p[0]["name"],mode)
        results.append(dict(case=[x[0] for x in case],mode=mode,seconds=round(time.perf_counter()-t,3),result=r))
        print(case[0][0],mode,r.get("found"),r.get("distance_m"),flush=True)
Path("smoke-results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf8")
