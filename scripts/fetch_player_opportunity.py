#!/usr/bin/env python3
"""Publish measured NFL player opportunity using nflverse weekly data."""
import csv, io, json, os, re, unicodedata, urllib.request
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
def name_key(name):
 value=unicodedata.normalize('NFKD',str(name or '')).encode('ascii','ignore').decode().lower()
 parts=re.findall(r'[a-z0-9]+',value)
 while parts and parts[-1] in ('jr','sr','ii','iii','iv','v'):parts.pop()
 return ''.join(parts)
def team_key(team):
 value=str(team or '').upper()
 return {'JAC':'JAX','LA':'LAR','WSH':'WAS'}.get(value,value)
def resolve(row,gsis,by_name):
 pid=gsis.get(str(row.get('player_id') or row.get('gsis_id') or ''))
 if pid:return pid,'gsis'
 pos=str(row.get('position') or '').upper()
 key=(name_key(row.get('player_display_name') or row.get('player_name')),pos)
 choices=by_name.get(key,[])
 if len(choices)==1:return choices[0][0],'name'
 team=team_key(row.get('recent_team') or row.get('team'))
 matching=[pid for pid,t in choices if t and t==team]
 if len(matching)==1:return matching[0],'name_team'
 return None,None
def main():
 with open('league_snapshot.json') as f:league=json.load(f)
 season=int(league['nfl_state']['season']);week=int(league['nfl_state']['week'])
 players=json.loads(fetch('https://api.sleeper.app/v1/players/nfl'))
 gsis={str(p['gsis_id']):str(pid) for pid,p in players.items() if isinstance(p,dict) and p.get('gsis_id')}
 pfr={str(p['pfr_id']):str(pid) for pid,p in players.items() if isinstance(p,dict) and p.get('pfr_id')}
 by_name=defaultdict(list)
 for pid,p in players.items():
  if isinstance(p,dict) and p.get('position') in ('QB','RB','WR','TE'):
   name=p.get('full_name') or ' '.join(str(p.get(k) or '') for k in ('first_name','last_name'))
   if name_key(name):by_name[(name_key(name),p['position'])].append((str(pid),team_key(p.get('team'))))
 games=defaultdict(dict);match_methods=defaultdict(set);unmatched=set()
 for row in csvdata(f'{BASE}/stats_player/stats_player_week_{season}.csv'):
  w=int(field(row,'week') or 0)
  if not 1<=w<week or row.get('season_type') not in ('REG','regular',''):continue
  pid,method=resolve(row,gsis,by_name)
  if not pid:
   unmatched.add(row.get('player_display_name') or row.get('player_name') or 'unknown')
   continue
  if players[pid].get('position') not in ('QB','RB','WR','TE'):continue
  match_methods[method].add(pid)
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
 print('Player mapping:',len(result),'methods:',{m:len(v) for m,v in match_methods.items()},'unmatched:',len(unmatched),flush=True)
 if len(result)<100:raise RuntimeError(f'Only {len(result)} mapped players after GSIS and name matching; unmatched samples: {sorted(unmatched)[:12]}')
 os.makedirs('projections',exist_ok=True)
 doc={'updated_at':datetime.now(timezone.utc).isoformat(),'season':season,'week':week,
  'source':'nflverse stats_player weekly + PFR snap counts; Sleeper GSIS/PFR player crosswalk',
  'snap_source':snap_status,'snap_rows':snap_rows,'mapped_players':len(result),'mapping_methods':{m:len(v) for m,v in match_methods.items()},
  'route_share_status':'Not sourced: route share is not inferred from snaps','players':result}
 with open('projections/player_opportunity.json','w') as f:json.dump(doc,f,separators=(',',':'))
 print('Published opportunity data:',len(result),'players;',snap_rows,'snaps')
if __name__=='__main__':main()
