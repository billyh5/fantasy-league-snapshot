#!/usr/bin/env python3
"""Free start/sit context: upcoming game totals/spreads + optional nflverse defensive PPR allowed."""
import csv, io, json, os, re, sys, urllib.request
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from statistics import median
from urllib.parse import urlencode
API='https://api.prop-line.com/v1/sports/football_nfl'
ABBR={'ARIZONA CARDINALS':'ARI','ATLANTA FALCONS':'ATL','BALTIMORE RAVENS':'BAL','BUFFALO BILLS':'BUF','CAROLINA PANTHERS':'CAR','CHICAGO BEARS':'CHI','CINCINNATI BENGALS':'CIN','CLEVELAND BROWNS':'CLE','DALLAS COWBOYS':'DAL','DENVER BRONCOS':'DEN','DETROIT LIONS':'DET','GREEN BAY PACKERS':'GB','HOUSTON TEXANS':'HOU','INDIANAPOLIS COLTS':'IND','JACKSONVILLE JAGUARS':'JAX','KANSAS CITY CHIEFS':'KC','LAS VEGAS RAIDERS':'LV','LOS ANGELES CHARGERS':'LAC','LOS ANGELES RAMS':'LAR','MIAMI DOLPHINS':'MIA','MINNESOTA VIKINGS':'MIN','NEW ENGLAND PATRIOTS':'NE','NEW ORLEANS SAINTS':'NO','NEW YORK GIANTS':'NYG','NEW YORK JETS':'NYJ','PHILADELPHIA EAGLES':'PHI','PITTSBURGH STEELERS':'PIT','SAN FRANCISCO 49ERS':'SF','SEATTLE SEAHAWKS':'SEA','TAMPA BAY BUCCANEERS':'TB','TENNESSEE TITANS':'TEN','WASHINGTON COMMANDERS':'WAS'}
def norm(team):
 s=re.sub(r'[^A-Z0-9 ]','',str(team).upper()).strip()
 return ABBR.get(s,s if s in ABBR.values() else None)
def fetch_json(path,key,**params):
 url=API+path+'?'+urlencode({'apiKey':key,**params})
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ShakeNBakeStartSit/1.0','Accept':'application/json'}),timeout=35) as r:return json.load(r)
def pick_med(values):return round(median(values),2) if values else None
def games_feed(key):
 raw=fetch_json('/events',key)
 events=raw if isinstance(raw,list) else raw.get('events',raw.get('data',[]))
 now=datetime.now(timezone.utc)
 valid=[]
 for e in events:
  try:t=datetime.fromisoformat(e['commence_time'].replace('Z','+00:00'))
  except (KeyError,ValueError,TypeError,AttributeError):continue
  if now-timedelta(hours=5)<=t<=now+timedelta(days=10):valid.append((t,e))
 valid.sort(key=lambda x:x[0])
 games=[];opponents={};implied={};errors=[]
 for t,e in valid[:18]:
  home=norm(e.get('home_team'));away=norm(e.get('away_team'))
  if not home or not away:continue
  try:data=fetch_json('/events/'+str(e['id'])+'/odds',key,markets='totals,spreads')
  except Exception as ex:
   errors.append('Odds unavailable: '+type(ex).__name__)
   data={}
  totals=[];home_spreads=[]
  for book in data.get('bookmakers',[]) if isinstance(data,dict) else []:
   for market in book.get('markets',[]):
    if market.get('line_type') not in (None,'main'):continue
    if market.get('key')=='totals' and not market.get('team'):
     for out in market.get('outcomes',[]):
      if out.get('name')=='Over':
       try:totals.append(float(out['point']))
       except (KeyError,TypeError,ValueError):pass
    if market.get('key')=='spreads':
     for out in market.get('outcomes',[]):
      if norm(out.get('name'))==home:
       try:home_spreads.append(float(out['point']))
       except (KeyError,TypeError,ValueError):pass
  total=pick_med(totals);spread=pick_med(home_spreads)
  h=round((total-spread)/2,2) if total is not None and spread is not None else None
  a=round((total+spread)/2,2) if h is not None else None
  games.append(dict(home=home,away=away,total=total,home_spread=spread,home_implied=h,away_implied=a,commence_time=t.isoformat()))
  opponents[home]={'opponent':away,'home':True,'kickoff':t.isoformat()}
  opponents[away]={'opponent':home,'home':False,'kickoff':t.isoformat()}
  if h is not None:implied[home]=h;implied[away]=a
 return games,opponents,implied,errors
def defense_feed(season,current_week):
 # nflverse published player-week CSV includes PPR points, position, opponent and week.
 url=f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ShakeNBakeStartSit/1.0'}),timeout=70) as r:payload=r.read()
 reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
 sums=defaultdict(float); seen=defaultdict(set)
 for row in reader:
  try:
   week=int(row.get('week') or 0)
   if not 1<=week<current_week:continue
   if row.get('season_type') not in ('REG','regular','') and row.get('season_type') is not None:continue
   defense=norm(row.get('opponent_team'))
   pos=(row.get('position') or '').upper()
   pts=float(row['fantasy_points_ppr'])
   if defense is None or pos not in ('QB','RB','WR','TE'):continue
   sums[defense,pos]+=pts;seen[defense,pos].add(week)
  except (ValueError,KeyError,TypeError):pass
 return {d:{p:round(sums[d,p]/len(seen[d,p]),2) for p in ('QB','RB','WR','TE') if seen[d,p]} for d in sorted(set(k[0] for k in sums))}
def main():
 with open('league_snapshot.json') as f:l=json.load(f)
 key=os.environ.get('PROPLINE_API_KEY','').strip()
 if not key:sys.exit('Missing secret PROPLINE_API_KEY')
 season=int(l['nfl_state']['season']);week=int(l['nfl_state']['week'])
 games,opponents,implied,errors=games_feed(key)
 try:dvp=defense_feed(season,week)
 except Exception as ex:
  dvp={};errors.append('Defense data unavailable: '+type(ex).__name__+' '+str(ex)[:120])
 if not games:sys.exit('No upcoming NFL events. '+str(errors[:3]))
 doc={'updated_at':datetime.now(timezone.utc).isoformat(),'week':week,'games':games,'opponents':opponents,'team_implied':implied,'defense_vs_position':dvp,'defense_source':'nflverse player-week PPR through previous week' if dvp else 'unavailable','errors':errors[:10]}
 os.makedirs('odds',exist_ok=True)
 with open('odds/start_sit_context.json','w') as f:json.dump(doc,f,separators=(',',':'))
 print('Context feed:',len(games),'games,',len(implied),'team totals,',len(dvp),'defenses')
 if errors:print('Warnings: '+str(errors))
if __name__=='__main__':main()
