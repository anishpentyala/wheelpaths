import json,urllib.request,hashlib,sys
from pathlib import Path
from wheelpaths import audit, InvalidPlan
root=Path('/tmp/wheelpaths-corpus');sources=[]
for project in ['google-auth','google-api-core','google-cloud-core','pytest','trio','click','rich','pyee','packaging','typing-extensions']:
    d=json.load(urllib.request.urlopen('https://pypi.org/pypi/'+project+'/json'))
    w=next(x for x in d['urls'] if x['filename'].endswith('none-any.whl'))
    path=root/w['filename'];urllib.request.urlretrieve(w['url'],path)
    digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==w['digests']['sha256']
    sources.append({'project':project,'version':d['info']['version'],'url':w['url'],'path':str(path),'sha256':digest})
scheme={'purelib':'/venv/lib/python3.12/site-packages','platlib':'/venv/lib/python3.12/site-packages','scripts':'/venv/bin','data':'/venv'}
report=audit([x['path'] for x in sources],scheme)
(root/'sources.json').write_text(json.dumps(sources,indent=2));(root/'plan.json').write_text(json.dumps(report,indent=2))
print(report['status'],len(report['wheels']),'wheels',len(report['claims']),'claims',len(report['conflicts']),'conflicts')
print('GENERATED COMMANDS',[(x['wheel'],x['target']) for x in report['claims'] if x['kind']=='generated-script'])
print('GOOGLE CLAIMS',sum('/google/' in x['target'] for x in report['claims']))
