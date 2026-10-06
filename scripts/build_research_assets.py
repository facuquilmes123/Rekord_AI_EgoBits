"""Rebuild curated source copies and normalized research manifests from local crawl.

Usage from ZIP development workspace:
 python scripts/build_research_assets.py --crawl /path/to/research
The crawl is intentionally not included: TSV and source manifest already cover the kit.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OMIT = {
    ('ryan-voitiskis/reklawdbox', 'src/adapters/rekordbox/connection.rs'),
    ('dylanljones/pyrekordbox', 'docs/source/key.md'),
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--crawl',type=Path,required=True)
    a=ap.parse_args()
    crawl=a.crawl.resolve()
    inv=json.loads((crawl/'inventory.json').read_text())
    extra=json.loads((crawl/'extra_inventory.json').read_text())
    src=json.loads((crawl/'source_manifest.json').read_text())
    (ROOT/'research').mkdir(exist_ok=True)
    with (ROOT/'research/repos.tsv').open('w',newline='',encoding='utf-8') as f:
        out=csv.writer(f,delimiter='\t')
        out.writerow(['repo','category','revision','license_github','status','pushed_at','stars','fork','upstream_url'])
        for x in inv:
            out.writerow([x['repo'],'mcp_or_ecosystem',x.get('sha',''),x.get('license') or 'not_recorded',x.get('status',''),x.get('pushed_at',''),x.get('stars',''),x.get('fork',''),f"https://github.com/{x['repo']}"])
        for x in extra:
            out.writerow([x['repo'],'adjacent','not_pinned',x.get('license') or 'not_recorded','metadata_only',x.get('pushed_at',''),x.get('stars',''),x.get('fork',''),f"https://github.com/{x['repo']}"])
    manifest=[]
    for entry in src:
        repo,path=entry['repo'],entry['path']
        if (repo,path) in OMIT: continue
        source=crawl/'source'/repo.replace('/','__')/path
        if not source.is_file():raise FileNotFoundError(source)
        target=ROOT/'upstream'/repo.replace('/','__')/path
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        manifest.append({'repo':repo,'path':path,'revision':entry['sha'],
                         'source_url':entry['url'],
                         'local_path':target.relative_to(ROOT).as_posix(),
                         'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                         'license':'MIT'})
    for repo in {x['repo'] for x in manifest}:
        if not any(x['repo']==repo and x['path'].upper()=='LICENSE' for x in manifest):
            raise RuntimeError(f'Falta LICENSE en paquete: {repo}')
    (ROOT/'research/upstream_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'{len(inv)} + {len(extra)} repositorios; {len(manifest)} archivos MIT')

if __name__=='__main__':main()
