"""Read public source URLs again; record availability without copying full articles."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]

def check(source):
    result={'id':source['id'],'url':source['url']}
    request=Request(source['url'],headers={'User-Agent':'MindGeoTutorAI source-verification/1.0'})
    try:
        with urlopen(request,timeout=25) as response:
            body=response.read()
            result.update(status=response.status,final_url=response.url,sha256_html=hashlib.sha256(body).hexdigest())
    except HTTPError as error:result.update(status=error.code,error=error.reason)
    except (URLError,TimeoutError,OSError) as error:result.update(status=None,error=str(error))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,help='Optional JSON audit output; never overwrites lesson files.')
    parser.add_argument('--limit',type=int,help='Verify only the first N sources.')
    args=parser.parse_args()
    if args.limit is not None and args.limit<1:parser.error('--limit must be positive')
    sources=json.loads((ROOT/'knowledge/sources.json').read_text())['sources']
    if args.limit:sources=sources[:args.limit]
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(check,sources))
    failed=[r for r in results if r['status']!=200]
    print(f"Sources available: {len(results)-len(failed)}/{len(results)}")
    for result in failed:print(result['id'],result['status'],result.get('error',''))
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'checked_at_utc':datetime.now(timezone.utc).isoformat(),'sources':results},ensure_ascii=False,indent=2)+'\n')
    return bool(failed)

if __name__=='__main__':raise SystemExit(main())
