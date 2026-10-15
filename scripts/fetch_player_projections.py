#!/usr/bin/env python3
"""Refresh league-independent PPR points for active and unrostered NFL players."""
import json,os,time
from datetime import datetime, timezone
from urllib.request import urlopen,Request
BASE="https://api.sleeper.app/v1"
def fetch(path):
 with urlopen(Request(BASE+path,headers={"User-Agent":"ShakeNBakeGM/1.0","Accept":"application/json"}),timeout=35) as f:return json.load(f)
def mapping(o):
 if isinstance(o,list):return {str(v["player_id"]):v for v in o if isinstance(v,dict) and v.get("player_id")}
 if isinstance(o,dict) and isinstance(o.get("data"),(dict,list)):return mapping(o["data"])
 return o if isinstance(o,dict) else {}
def extract(o):
 if not isinstance(o,dict):return None
 x=o.get("stats") if isinstance(o.get("stats"),dict) else o
 for key in ("pts_ppr","fantasy_points_ppr","ppr"):
  v=x.get(key)
  if isinstance(v,(int,float)) and not isinstance(v,bool):return round(float(v),2)
 weight={"pass_yd":.04,"pass_td":4,"pass_int":-2,"rush_yd":.1,"rush_td":6,"rec":1,"rec_yd":.1,"rec_td":6,"fum_lost":-2,"pass_2pt":2,"rush_2pt":2,"rec_2pt":2}
 if not any(k in x for k in ("rush_yd","rec_yd","pass_yd","rec","rush_td","rec_td","pass_td")):return None
 return round(sum((x.get(k) or 0)*w for k,w in weight.items()),2)
def main():
 with open("league_snapshot.json") as f:league=json.load(f)
 season=str(league["nfl_state"]["season"]);week=min(18,max(1,int(league["nfl_state"]["week"])))
 history={};projections={};errors=[]
 for kind, weeks, target in [("stats",range(1,week),history),("projections",range(week,min(18,week+3)),projections)]:
  for w in weeks:
   try:
    raw=mapping(fetch(f"/{kind}/nfl/regular/{season}/{w}"))
    result={str(k):v for k,o in raw.items() if (v:=extract(o)) is not None}
    if result:target[str(w)]=result
    else:errors.append(f"{kind} week {w}: no usable PPR data")
   except Exception as e:errors.append(f"{kind} week {w}: {type(e).__name__}: {e}")
   time.sleep(.15)
 if not history and not projections:raise SystemExit("No usable Sleeper data. "+str(errors[:3]))
 os.makedirs("projections",exist_ok=True)
 with open("projections/player_weekly.json","w") as f:json.dump({"updated_at":datetime.now(timezone.utc).isoformat(),"season":season,"current_week":week,"source":"Sleeper weekly stats and projections","history":history,"projections":projections,"errors":errors[:25]},f,separators=(",",":"))
 print("History entries:",sum(map(len,history.values())),"Projection entries:",sum(map(len,projections.values())))
 if errors:print("Warnings:",*errors,sep="\n")
if __name__=="__main__":main()
