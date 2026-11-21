"""Independent implementation of published SCORING.md, not the official scorer."""
import json
import math
from .scheduling import schedule_cost

MAX_STDOUT_BYTES=2*1024*1024


class Rejected(ValueError):
    pass


def decode_predictions(raw, commits, durations):
    if len(raw)>MAX_STDOUT_BYTES:
        raise Rejected('stdout exceeds 2 MB')
    try:
        text=raw.decode('utf-8')
    except UnicodeError as e:
        raise Rejected('not_utf8') from e
    lines=text.split('\n')
    if lines[-1]=='': lines.pop()
    if text=='': lines=[]
    found={}
    def bad_constant(value):
        raise Rejected('not_json: nonfinite literal')
    def unique_pairs(pairs):
        obj={}
        for k,v in pairs:
            if k in obj: raise Rejected('Duplicate JSON key')
            obj[k]=v
        return obj
    for line in lines:
        try:
            obj=json.loads(line,parse_constant=bad_constant,object_pairs_hook=unique_pairs)
        except (ValueError,TypeError) as e:
            raise Rejected('not_json') from e
        if not isinstance(obj,dict) or set(obj)!={'commit','workers'} or not isinstance(obj['commit'],str) or not isinstance(obj['workers'],list):
            raise Rejected('wrong_shape')
        name=obj['commit']
        if name not in commits: raise Rejected('unknown_commit')
        if name in found: raise Rejected('repeated_commit')
        workers=[]; seen=set()
        for worker in obj['workers']:
            if not isinstance(worker,list): raise Rejected('wrong_shape')
            clean=[]
            for n in worker:
                if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n!=int(n):
                    raise Rejected('wrong_shape')
                n=int(n)
                if n not in durations: raise Rejected('unknown_test')
                if n in seen: raise Rejected('repeated_test')
                seen.add(n); clean.append(n)
            if clean: workers.append(clean)
        if len(workers)>8: raise Rejected('too_many_workers')
        found[name]=workers
    if set(found)!=set(commits): raise Rejected('missing_commit')
    return found


def evaluate(predictions, answers, durations):
    details=[]
    for name,workers in sorted(predictions.items()):
        if name not in answers: raise ValueError('Missing sample answer: '+name)
        failing=set(answers[name]['failing'])
        if not failing.issubset(durations): raise ValueError('Sample answers reference unknown tests')
        selected={n for worker in workers for n in worker}
        missing=sorted(failing-selected)
        base=schedule_cost(workers,durations)
        cost=base+(300000 if missing else 0)
        details.append(dict(commit=name,selected_tests=len(selected),workers=len(workers),base_ms=base,miss=bool(missing),missed_tests=missing,cost_ms=cost))
    return dict(simulated_ms=sum(x['cost_ms'] for x in details),misses=sum(x['miss'] for x in details),commits=len(details),details=details)
