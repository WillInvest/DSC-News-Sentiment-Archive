#!/usr/bin/env python3
import argparse, json, os, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

def main():
    p=argparse.ArgumentParser(); p.add_argument("--manifest",required=True); p.add_argument("--summarizer",required=True); p.add_argument("--output",required=True); args=p.parse_args()
    manifest=json.loads(Path(args.manifest).read_text()); target=Path(args.output); target.mkdir(parents=True,exist_ok=True); items=[]
    for entity in manifest["entities"]:
        path=target/f"{entity['slug']}.json"
        subprocess.run([sys.executable,args.summarizer,"--evidence",entity["evidence"],"--output",str(path),"--entity",entity["name"]],check=True,env=os.environ.copy())
        items.append(json.loads(path.read_text()))
    latest={"schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"window_days":30,"items":items}
    (target/"latest.json").write_text(json.dumps(latest,indent=2)+"\n")
if __name__=="__main__": main()
