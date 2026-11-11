from pathlib import Path
import json,os
from installer import install
from installer.sources import WheelFile
from installer.destinations import SchemeDictionaryDestination
root=Path('/tmp/wheelpaths-corpus-stage');root.mkdir(exist_ok=True)
scheme={'purelib':'/venv/lib/python3.12/site-packages','platlib':'/venv/lib/python3.12/site-packages','scripts':'/venv/bin','data':'/venv','headers':'/venv/include'}
plan=json.load(open('/tmp/wheelpaths-corpus/plan.json'))
destination=SchemeDictionaryDestination(scheme,interpreter='/venv/bin/python',script_kind='posix',destdir=str(root))
for wheel in json.load(open('/tmp/wheelpaths-corpus/sources.json')):
 with WheelFile.open(wheel['path']) as source:install(source,destination,{})
missing=[]
for claim in plan['claims']:
 p=root/claim['target'].lstrip('/')
 if not p.exists():missing.append(claim)
 if claim['kind']=='generated-script':assert p.is_file() and os.access(p,os.X_OK)
assert not missing,missing
print('INSTALLER AGREEMENT all',len(plan['claims']),'projected paths exist;10wheels staged,0overwrite refusals;2generatedcommands executable')
print('No package imports or dependency resolution. Not a usability/safety guarantee.')
