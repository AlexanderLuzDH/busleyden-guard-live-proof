#!/usr/bin/env python3
"""History-grounded evidence-state audit using original upstream fix commits.

BugsInPy deliberately strips test-file changes from bug_patch.txt. Therefore
this instrument uses bug_patch.txt only for isolated source paths, and queries
the original GitHub fixed commit to recover test-file change status.
"""
from __future__ import annotations
import argparse, csv, json, math, os, random, re, shlex, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TEST_DIRS={"test","tests","testing","spec","specs"}
STOP={"src","source","lib","test","tests","testing","spec","core","main","utils","util","base","module","modules","python"}

def norm(s:str)->str:
    s=s.strip().strip("'\"").replace("\\","/")
    while s.startswith("./"): s=s[2:]
    return PurePosixPath(s).as_posix()

def is_test(s:str)->bool:
    p=PurePosixPath(norm(s)); parts=[x.lower() for x in p.parts]; n=p.name.lower()
    return any(x in TEST_DIRS for x in parts[:-1]) or n.startswith("test_") or n.endswith("_test.py")

def is_source(s:str)->bool:
    return PurePosixPath(norm(s)).suffix.lower() in {".py",".pyx"} and not is_test(s)

def shell_info(p:Path)->dict[str,str]:
    out={}
    for raw in p.read_text(encoding="utf-8",errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1)
        try: x=shlex.split(v); out[k.strip()]=" ".join(x) if x else ""
        except ValueError: out[k.strip()]=v.strip("'\"")
    return out

def test_paths(text:str)->set[str]:
    return {norm(x.split("::",1)[0]) for x in re.findall(r"[A-Za-z0-9_./-]+\.(?:py|pyx)(?:::)?",text)}

def patch_paths(text:str)->list[str]:
    return [norm(m.group(2)) for line in text.splitlines() if (m:=re.match(r"diff --git a/(.*?) b/(.*)$",line))]

def github_repo(url:str)->str|None:
    m=re.search(r"github\.com[/:]([^/]+)/([^/#]+?)(?:\.git)?$",url.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None

def candidates(src:str)->set[str]:
    p=PurePosixPath(norm(src)); stem=p.stem
    out={f"tests/test_{stem}.py",f"test/test_{stem}.py",str(p.with_name(f"test_{stem}.py")),f"tests/{stem}_test.py"}
    if p.parts and p.parts[0].lower() in {"src","lib","source"}:
        q=PurePosixPath(*p.parts[1:]); out|={str(PurePosixPath("tests")/q.with_name(f"test_{q.stem}.py")),str(PurePosixPath("tests")/q)}
    return {norm(x) for x in out}

def toks(text:str)->set[str]:
    return {x for x in re.findall(r"[a-z0-9]+",text.lower()) if len(x)>1 and x not in STOP}

@dataclass
class Meta:
    project:str; bug_id:str; repo:str; python_version:str; buggy_commit_id:str; fixed_commit_id:str
    benchmark_tests:list[str]; changed_sources:list[str]

@dataclass
class Record:
    project:str; bug_id:str; repo:str; python_version:str; buggy_commit_id:str; fixed_commit_id:str
    benchmark_tests:list[str]; changed_sources:list[str]; upstream_changed_files:list[str]; upstream_test_files:list[str]
    relevant_test_added:bool; relevant_test_modified:bool; relevant_test_changed:bool
    relevant_test_unchanged_proxy:bool; any_test_changed:bool; unrelated_test_change_only:bool
    same_stem_discoverable:bool; candidate_path_discoverable:bool; commit_api_status:str; commit_url:str|None

def load_meta(root:Path)->list[Meta]:
    out=[]
    for project in sorted((root/"projects").iterdir()):
        bugs=project/"bugs"; pi=project/"project.info"
        if not bugs.is_dir() or not pi.is_file(): continue
        repo=github_repo(shell_info(pi).get("github_url",""))
        if not repo: continue
        for bug in sorted((p for p in bugs.iterdir() if p.is_dir()),key=lambda p:(not p.name.isdigit(),int(p.name) if p.name.isdigit() else p.name)):
            ip,pp=bug/"bug.info",bug/"bug_patch.txt"
            if not ip.is_file() or not pp.is_file(): continue
            info=shell_info(ip); relevant=test_paths(info.get("test_file","")); rp=bug/"run_test.sh"
            if rp.is_file(): relevant|=test_paths(rp.read_text(encoding="utf-8",errors="replace"))
            src=sorted(p for p in patch_paths(pp.read_text(encoding="utf-8",errors="replace")) if is_source(p))
            fixed=info.get("fixed_commit_id","")
            if relevant and src and fixed: out.append(Meta(project.name,bug.name,repo,info.get("python_version",""),info.get("buggy_commit_id",""),fixed,sorted(relevant),src))
    return out

def fetch_commit(repo:str,sha:str,token:str)->dict:
    files=[]; commit_url=None
    for page in range(1,6):
        url=f"https://api.github.com/repos/{repo}/commits/{sha}?per_page=100&page={page}"
        headers={"Accept":"application/vnd.github+json","User-Agent":"autonomous-assurance-lab-v1","X-GitHub-Api-Version":"2022-11-28"}
        if token: headers["Authorization"]=f"Bearer {token}"
        last=""
        for attempt in range(4):
            try:
                with urlopen(Request(url,headers=headers),timeout=45) as r: data=json.load(r)
                last=""; break
            except (HTTPError,URLError,TimeoutError) as e:
                last=f"{type(e).__name__}:{getattr(e,'code','')}:{e}"; time.sleep(2**attempt)
        if last: return {"status":"error","error":last,"files":[],"url":commit_url}
        commit_url=data.get("html_url") or commit_url
        batch=data.get("files",[])
        for f in batch:
            files.append({"path":norm(f.get("filename","")),"status":f.get("status","unknown"),"previous":norm(f.get("previous_filename","")) if f.get("previous_filename") else None})
        if len(batch)<100: break
    return {"status":"ok","files":files,"url":commit_url}

def build(m:Meta,commit:dict)->Record:
    files=commit.get("files",[]); by_path={f["path"]:f for f in files}; relevant=set(m.benchmark_tests)
    added=any(t in by_path and by_path[t]["status"]=="added" for t in relevant)
    modified=any(t in by_path and by_path[t]["status"] in {"modified","renamed","copied","changed"} for t in relevant)
    changed=added or modified or any(f.get("previous") in relevant for f in files)
    all_paths=sorted(f["path"] for f in files); tests=sorted(p for p in all_paths if is_test(p)); any_test=bool(tests)
    same=any(PurePosixPath(s).stem.lower() in PurePosixPath(t).stem.lower().replace("test_","").replace("_test","") for s in m.changed_sources for t in relevant)
    exact=any(t in candidates(s) for s in m.changed_sources for t in relevant)
    return Record(m.project,m.bug_id,m.repo,m.python_version,m.buggy_commit_id,m.fixed_commit_id,m.benchmark_tests,m.changed_sources,all_paths,tests,added,modified,changed,not changed,any_test,any_test and not changed,same,exact,commit.get("status","error"),commit.get("url"))

def wilson(k:int,n:int,z:float=1.6448536269514722):
    if not n:return None
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]

def cluster90(rs:list[Record],field:str,seed:int=61062,reps:int=5000):
    ps=sorted({r.project for r in rs})
    if not ps:return None
    groups={p:[r for r in rs if r.project==p] for p in ps}; rng=random.Random(seed); vals=[]
    for _ in range(reps):
        sample=[r for p in (rng.choice(ps) for _ in ps) for r in groups[p]]
        vals.append(sum(bool(getattr(r,field)) for r in sample)/len(sample))
    vals.sort(); return [vals[int(.05*(reps-1))],vals[int(.95*(reps-1))]]

def rate(rs:list[Record],field:str):
    k=sum(bool(getattr(r,field)) for r in rs); n=len(rs)
    return {"successes":k,"total":n,"rate":k/n if n else None,"wilson90":wilson(k,n),"project_cluster_bootstrap90":cluster90(rs,field)}

def summarize(all_records:list[Record])->dict:
    ok=[r for r in all_records if r.commit_api_status=="ok"]
    ev={f:rate(ok,f) for f in ["relevant_test_added","relevant_test_modified","relevant_test_changed","relevant_test_unchanged_proxy","any_test_changed","unrelated_test_change_only"]}
    mp={f:rate(ok,f) for f in ["same_stem_discoverable","candidate_path_discoverable"]}
    n=len(ok); pre=ev["relevant_test_unchanged_proxy"]["successes"]; no_any=[r for r in ok if not r.any_test_changed]
    return {"schema_version":2,"kind":"autonomous_assurance_upstream_commit_audit",
      "claim_boundary":"Original GitHub fixed-commit file statuses plus BugsInPy-selected tests. Historical evidence-state proxies, not full logical sufficiency or human usefulness.",
      "instrument_correction":"BugsInPy bug_patch.txt intentionally excludes test files; test-change state is recovered from original upstream fixed commits.",
      "dataset":{"metadata_cases":len(all_records),"api_success":n,"api_failures":len(all_records)-n,"projects":len({r.project for r in ok}),"project_counts":dict(sorted(Counter(r.project for r in ok).items()))},
      "evidence_states":ev,"mapping":mp,
      "policy_tournament":{
        "obligation_first":{"emissions":n,"changed_test_proxy_precision":ev["relevant_test_changed"]["rate"],"unchanged_test_proxy_false_obligations":pre},
        "suppress_if_any_test_changed":{"emissions":len(no_any),"changed_test_proxy_precision":sum(r.relevant_test_changed for r in no_any)/len(no_any) if no_any else None,"unchanged_test_proxy_false_obligations":sum(r.relevant_test_unchanged_proxy for r in no_any),"unrelated_test_suppressions":sum(r.unrelated_test_change_only for r in ok)},
        "evidence_first_oracle":{"states":["missing_before_fix_proxy","present_but_modified_proxy","present_existing_proxy"],"note":"Non-deployable upper bound using benchmark paths and future commit metadata."}},
      "hypotheses":{
        "H1_unchanged_relevant_test_at_least_25pct":{"observed":pre/n if n else None,"passed":bool(n) and pre/n>=.25},
        "H2_binary_any_test_inadequacy_at_least_10pct":{"observed":pre/n if n else None,"passed":bool(n) and pre/n>=.10},
        "H3_exact_filename_mapping_below_70pct":{"observed":mp["candidate_path_discoverable"]["rate"],"passed":bool(n) and mp["candidate_path_discoverable"]["rate"]<.70}}}

def markdown(s:dict)->str:
    pct=lambda x:"n/a" if x is None else f"{100*x:.1f}%"
    d=s["dataset"]; lines=["# Autonomous Assurance Lab v1 — corrected upstream-commit audit","",s["claim_boundary"],"",f"API-resolved cases: **{d['api_success']}** / **{d['metadata_cases']}** across **{d['projects']}** projects.","",f"> Instrument correction: {s['instrument_correction']}","","| Measure | Count | Rate |","|---|---:|---:|"]
    for group in (s["evidence_states"],s["mapping"]):
        for name,row in group.items(): lines.append(f"| {name} | {row['successes']}/{row['total']} | {pct(row['rate'])} |")
    lines += ["","## Preregistered hypotheses"]
    for name,r in s["hypotheses"].items(): lines.append(f"- **{name}:** {'PASS' if r['passed'] else 'FAIL'} — {pct(r['observed'])}")
    return "\n".join(lines)+"\n"

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--github-token",default=os.getenv("GH_TOKEN",os.getenv("GITHUB_TOKEN",""))); ap.add_argument("--workers",type=int,default=12); ap.add_argument("--json-output",type=Path,required=True); ap.add_argument("--markdown-output",type=Path,required=True); ap.add_argument("--csv-output",type=Path,required=True); a=ap.parse_args()
    meta=load_meta(a.root); keys={(m.repo,m.fixed_commit_id) for m in meta}; fetched={}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futures={ex.submit(fetch_commit,repo,sha,a.github_token):(repo,sha) for repo,sha in keys}
        for f in as_completed(futures): fetched[futures[f]]=f.result()
    records=[build(m,fetched[(m.repo,m.fixed_commit_id)]) for m in meta]; summary=summarize(records); payload={"summary":summary,"records":[asdict(r) for r in records]}
    for p in [a.json_output,a.markdown_output,a.csv_output]: p.parent.mkdir(parents=True,exist_ok=True)
    a.json_output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8"); a.markdown_output.write_text(markdown(summary),encoding="utf-8")
    with a.csv_output.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(records[0])) if records else []); w.writeheader()
        for r in records:
            row=asdict(r)
            for k,v in row.items():
                if isinstance(v,list): row[k]=json.dumps(v)
            w.writerow(row)
    print(json.dumps(summary,sort_keys=True)); return 0 if summary["dataset"]["api_success"]>=.95*len(meta) else 2
if __name__=="__main__": raise SystemExit(main())
