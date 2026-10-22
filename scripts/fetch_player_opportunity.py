#!/usr/bin/env python3
"""Publish measured NFL player opportunity using nflverse weekly data."""
import csv, io, json, os, urllib.request
from collections import defaultdict
from datetime import datetime,timezone
BASE='https://github.com/nflverse/nflverse-data/releases/download'
def fetch(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'TheLeagueGM/1.0'}),timeout=100) as response:return response.read()
def csvdata(url):return list(csv.DictReader(io.StringIO(fetch(url).decode('utf-8-sig'))))
def num(v):
 try:return float(v) if v not in (None,'') else None
 except (TypeError,ValueError):return None
def field(row,*keys):
 for key in keys:
  x=num(row.get(key))
  if x is not None:return x
 return None
def avg(rows,key):
 vals=[r[key] for r in rows if isinstance(r.get(key),(int,float))]
 return round(sum(vals)/len(vals),3) if vals else None
def main():
 with open('league_snapshot.json') as f:league=json.load(f)
 season=int(league['nfl_state']['season']);week=int(league['nfl_state']['week'])
 players=json.loads(fetch('https://api.sleeper.app/v1/players/nfl'))
 gsis={str(p['gsis_id']):str(pid) for pid,p in players.items() if isinstance(p,dict) and p.get('gsis_id')}
 pfr={str(p['pfr_id']):str(pid) for pid,p in players.items() if isinstance(p,dict) and p.get('pfr_id')}
 games=defaultdict(dict)
 for row in csvdata(f'{BASE}/stats_player/stats_player_week_{season}.csv'):
  w=int(field(row,'week') or 0)
  if not 1<=w<week or row.get('season_type') not in ('REG','regular',''):continue
  pid=gsis.get(str(row.get('player_id') or row.get('gsis_id') or ''))
  if not pid or players[pid].get('position') not in ('QB','RB','WR','TE'):continue
  games[pid][w]={'week':w,'team':row.get('team') or row.get('recent_team'),
   'targets':field(row,'targets'),'carries':field(row,'carries'),
   'receptions':field(row,'receptions'),'air_yards':field(row,'receiving_air_yards'),
   'target_share':field(row,'target_share'),'air_yards_share':field(row,'air_yards_share')}
 snap_status='unavailable';snap_rows=0
 try:
  for row in csvdata(f'{BASE}/snap_counts/snap_counts_{season}.csv'):
   w=int(field(row,'week') or 0)
   if not 1<=w<week:continue
   pid=pfr.get(str(row.get('pfr_player_id') or ''))
   if pid and w in games.get(pid,{}):
    pct=field(row,'offense_pct')
    if pct is not None and 0<=pct<=100:
     games[pid][w]['snap_share']=round(pct if pct<=1 else pct/100,3)
     snap_rows+=1
  snap_status='nflverse PFR snap counts'
 except Exception as e:snap_status='unavailable: '+type(e).__name__
 keys=['targets','carries','receptions','air_yards','target_share','air_yards_share','snap_share']
 result={}
 for pid,weeks in games.items():
  arr=[weeks[w] for w in sorted(weeks)]
  result[pid]={'position':players[pid].get('position'),'games':arr,
   'last3':{k:avg(arr[-3:],k) for k in keys},'season':{k:avg(arr,k) for k in keys},
   'route_share':None}
 if len(result)<100:raise RuntimeError(f'Only {len(result)} mapped players; refusing to publish')
 os.makedirs('projections',exist_ok=True)
 doc={'updated_at':datetime.now(timezone.utc).isoformat(),'season':season,'week':week,
  'source':'nflverse stats_player weekly + PFR snap counts; Sleeper GSIS/PFR player crosswalk',
  'snap_source':snap_status,'snap_rows':snap_rows,'mapped_players':len(result),
  'route_share_status':'Not sourced: route share is not inferred from snaps','players':result}
 with open('projections/player_opportunity.json','w') as f:json.dump(doc,f,separators=(',',':'))
 print('Published opportunity data:',len(result),'players;',snap_rows,'snaps')
if __name__=='__main__':main()
