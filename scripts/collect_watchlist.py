#!/usr/bin/env python3
"""Build one free, attributable 30-day evidence file per watchlist entity."""
import argparse, json, subprocess, sys, tempfile, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = (("Cointelegraph", "https://cointelegraph.com/rss", 30), ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml", 25), ("Ethereum Foundation", "https://blog.ethereum.org/feed.xml", 20))
TRUSTED_REDDIT = ("/r/bitcoin/", "/r/bitcoinmarkets/", "/r/cryptocurrency/", "/r/ethereum/", "/r/ethfinance/", "/r/ethtrader/", "/r/solana/", "/r/solanatech/", "/r/defi/")

def date(value):
    try: return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        try: return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception: return None

def feed(source, url, maximum, cutoff):
    req=urllib.request.Request(url,headers={"User-Agent":"DSC-sentiment-MVP/1.0"})
    root=ET.fromstring(urllib.request.urlopen(req,timeout=25).read()); rows=[]
    for item in root.iter():
        if item.tag.rsplit("}",1)[-1].lower() not in {"item","entry"}: continue
        fields={}; link=""
        for child in item:
            key=child.tag.rsplit("}",1)[-1].lower(); fields.setdefault(key,(child.text or "").strip())
            if key=="link" and child.attrib.get("href"): link=child.attrib["href"]
        published=fields.get("pubdate") or fields.get("published") or fields.get("updated")
        if not fields.get("title") or (date(published) and date(published)<cutoff): continue
        rows.append({"source":source,"title":fields["title"],"url":link or fields.get("link",""),"published_at":published,"summary":fields.get("description") or fields.get("summary") or ""})
        if len(rows)>=maximum: break
    return rows

def main():
    p=argparse.ArgumentParser(); p.add_argument("--engine",required=True); p.add_argument("--watchlist",required=True); p.add_argument("--output",required=True); args=p.parse_args()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True); now=datetime.now(timezone.utc); cutoff=now-timedelta(days=30)
    rss=[]; rss_status={}
    for source,url,maximum in FEEDS:
        try: rss.extend(feed(source,url,maximum,cutoff)); rss_status[source.lower().replace(" ","_")+"_rss"]="ok"
        except Exception as error: rss_status[source.lower().replace(" ","_")+"_rss"]=f"error: {type(error).__name__}"
    entities=json.loads(Path(args.watchlist).read_text()); manifest=[]
    for entity in entities:
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp); plan={"intent":"opinion","freshness_mode":"strict_recent","cluster_mode":"story","subqueries":[{"label":entity["name"],"search_query":entity["topic"],"ranking_query":f"What recent community, developer, and market evidence supports positive or negative sentiment about {entity['name']}?","sources":["reddit","youtube","hackernews","polymarket","github","grounding"],"weight":1.0}]}
            plan_path=temp/"plan.json"; plan_path.write_text(json.dumps(plan)); community_path=temp/"community.json"
            command=[sys.executable,args.engine,entity["topic"],"--emit=json","--json-profile=agent","--quick","--lookback-days=30","--max-results=12","--search=reddit,youtube,hackernews,polymarket,github,grounding",f"--subreddits={','.join(entity['subreddits'])}","--web-backend=keyless","--no-browser-cookies",f"--plan={plan_path}"]
            completed=subprocess.run(command,text=True,capture_output=True)
            try: community=json.loads(completed.stdout) if completed.returncode==0 else {"results":[],"source_status":{"last30days":f"error: {completed.returncode}"}}
            except json.JSONDecodeError: community={"results":[],"source_status":{"last30days":"invalid-json"}}
        aliases=entity["aliases"]; matching=[x for x in rss if any(alias in ((x["title"]+" "+x["summary"]).lower()) for alias in aliases)][:10]
        community_rows=[]
        for item in community.get("results",[]):
            source=item.get("source"); url=(item.get("url") or "").lower()
            if source=="reddit" and not any(part in url for part in TRUSTED_REDDIT): continue
            if source in {"reddit","youtube","hackernews","polymarket","github"}: community_rows.append(item)
        evidence={"query":entity["topic"],"window_days":30,"generated_at":now.isoformat().replace("+00:00","Z"),"source_status":rss_status | community.get("source_status",{}),"results":matching+community_rows[:8]}
        path=out/f"{entity['slug']}.json"; path.write_text(json.dumps(evidence,indent=2)+"\n"); manifest.append({"name":entity["name"],"slug":entity["slug"],"evidence":str(path)})
    (out/"manifest.json").write_text(json.dumps({"generated_at":now.isoformat().replace("+00:00","Z"),"entities":manifest},indent=2)+"\n")
if __name__=="__main__": main()
