#!/usr/bin/env python3
"""Fetch NFL player props using a secret; publish only key-free consensus data."""
import os, json, re, sys
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
from statistics import median
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError
API='https://api.prop-line.com/v1/sports/football_nfl'
MARKETS='player_rush_yds,player_reception_yds,player_receptions,player_pass_yds,player_pass_tds,player_anytime_td'
FIELDS={'player_rush_yds':'rush','player_reception_yds':'recyd','player_receptions':'recs','player_pass_yds':'pass','player_pass_tds':'passtd','player_anytime_td':'td'}
def fetch(path,key,**params):
    url=API+path+'?'+urlencode({**params,'apiKey':key})
    try:
        with urlopen(Request(url,headers={'Accept':'application/json','User-Agent':'TheLeagueGM/1.0'}),timeout=30) as res:
            return json.load(res)
    except HTTPError as e:
        raise RuntimeError('PropLine HTTP '+str(e.code)+' at '+path) from None
def norm(s):
    return re.sub('[^a-z]','',re.sub(r'\s*\([^)]*\)\s*$','',s).lower())
def probability(p):
    try:
        p=float(p)
        return 100/(p+100) if p>0 else -p/(-p+100) if p<0 else None
    except (ValueError,TypeError):return None
def main():
    key=os.getenv('PROPLINE_API_KEY','').strip()
    if not key:sys.exit('Missing repository secret PROPLINE_API_KEY')
    e=fetch('/events',key)
    events=e if isinstance(e,list) else e.get('events',e.get('data',[]))
    now=datetime.now(timezone.utc)
    upcoming=[]
    for evt in events:
        try:t=datetime.fromisoformat(evt['commence_time'].replace('Z','+00:00'))
        except (KeyError,TypeError,ValueError,AttributeError):continue
        if evt.get('id') is not None and now-timedelta(hours=4)<=t<=now+timedelta(days=9):upcoming.append((t,evt))
    upcoming.sort(key=lambda item:item[0])
    odds=[];errors=[]
    for _,event in upcoming[:18]:
        try:odds.append(fetch('/events/'+str(event['id'])+'/odds',key,markets=MARKETS))
        except Exception as ex:
            errors.append(str(ex))
            if any(x in str(ex) for x in ('HTTP 401','HTTP 403','HTTP 429')):break
    if errors and not odds:sys.exit('No odds fetched. '+errors[0])
    lines=defaultdict(lambda:defaultdict(list));names={}
    book_markets=defaultdict(lambda:defaultdict(set))
    for event in odds:
        for book in event.get('bookmakers') or []:
            book_name=str(book.get('key') or book.get('title') or book.get('name') or book.get('id') or 'unknown').strip()
            for market in book.get('markets') or []:
                field=FIELDS.get(market.get('key'))
                if not field:continue
                for out in market.get('outcomes') or []:
                    if out.get('name') not in ('Over','Yes'):continue
                    raw=out.get('description') or out.get('player') or ''
                    k=norm(raw)
                    if not k:continue
                    names[k]=re.sub(r'\s*\([^)]*\)\s*$','',raw).strip()
                    book_markets[book_name][field].add(k)
                    try:
                        v=probability(out.get('price'))*100 if field=='td' else float(out['point'])
                        if v is not None and 0<=v<=800:lines[k][field].append(v)
                    except (KeyError,ValueError,TypeError):pass
    players={k:{'name':names[k],**{f:round(median(vals),2) for f,vals in v.items()}} for k,v in lines.items()}
    coverage={book:{field:len(keys) for field,keys in fields.items()} for book,fields in sorted(book_markets.items())}
    result={'updated_at':now.isoformat(),'source':'PropLine free tier','games_checked':len(odds),'players_count':len(players),'partial_failures':len(errors),'bookmaker_coverage':coverage,'players':players}
    os.makedirs('odds',exist_ok=True)
    with open('odds/vegas_snapshot.json','w') as f:json.dump(result,f,separators=(',',':'))
    print('Wrote odds snapshot:',len(players),'players from',len(odds),'games')
if __name__=='__main__':main()
