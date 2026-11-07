# Copyright (c) 2026 Metrum AI, Inc. All rights reserved.
import json,pathlib,subprocess,tempfile,shutil
p=pathlib.Path(__file__).resolve().parent.parent
raw=json.loads((p/'data/tracker.json').read_text());policy=json.loads((p/'data/policy.json').read_text());ref=(p/'skills/intelligence-arbitrage/reference.md').read_text();skill=(p/'skills/intelligence-arbitrage/SKILL.md').read_text()
assert len(raw['rows'])==44
assert [e['model'] for e in policy['tiers']['workhorse']]==['GPT-6.1 Terra','Claude Sonnet 5.5','GPT-6.1 Sol','Kimi K3.1 Pro','Claude Opus 5.5','GPT-6 Astra','Claude Fable 5.1']
assert len(policy['tiers']['subtask'])==5
assert ref.count('\n### ')==44
for m in raw['rows']:
 assert f"### {m['model']} —" in ref,m['model']
 for r in m['routes']:
  if r.get('model_id'):assert f"`{r['model_id']}`" in ref,r['model_id']
for tier in policy['tiers'].values():
 for e in tier:
  assert e['score']>=30
  if e['route_kind']=='openrouter':assert e['pi']=='openrouter/'+e['model_id'] and e['pi'].endswith(':nitro')
  assert abs(e['blended']-(3*e['in']+e['out'])/4)<.0001
for text in [skill,(p/'extensions/arbitrage.ts').read_text()]:assert 'architecture, concurrency or security' in text
files=['data/policy.json','skills/intelligence-arbitrage/SKILL.md','skills/intelligence-arbitrage/reference.md','settings.snippet.json']
before={f:(p/f).read_bytes() for f in files}
subprocess.run(['python3','scripts/build_snapshot.py'],cwd=p,check=True)
assert all((p/f).read_bytes()==before[f] for f in files)
with tempfile.TemporaryDirectory(prefix='arb-rebuild-fixed-') as d:
 c=pathlib.Path(d)/'package';shutil.copytree(p,c,ignore=shutil.ignore_patterns('node_modules','package-lock.json','.git'))
 subprocess.run(['python3','scripts/build_snapshot.py','--blend','1:1','--floor','45'],cwd=c,check=True)
 tiers=json.loads((c/'data/policy.json').read_text())['tiers'];assert [len(tiers[k]) for k in ['workhorse','subtask','frontier']]==[5,7,3]
 subprocess.run(['python3','scripts/build_snapshot.py'],cwd=c,check=True)
 assert all((c/f).read_bytes()==before[f] for f in files)
print('PASS: exact workhorse ranking, 44 model sections, every route ID, Nitro selectors, score floors, pricing math, consistent rules, deterministic builds and retune/default restoration.')
