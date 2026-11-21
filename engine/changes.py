"""Exact semantic/fixture delta IR. No delta alone proves whole-test safety."""
from pathlib import PurePosixPath
from blast.patches import parse_patch,apply_change
from blast.fixture_contracts import normalize
from .core import semantic_edits,digest

def analyze(source,patch):
    records=[]
    for change in parse_patch(patch):
        path=change.old_path
        if not path or change.new_path!=path or '..' in PurePosixPath(path).parts or PurePosixPath(path).is_absolute():
            records.append({'status':'unknown','reason':'structural_or_path_edit'});continue
        file=source/path
        if file.is_symlink() or not file.is_file():
            records.append({'path':path,'status':'unknown','reason':'missing_source'});continue
        try:
            old=file.read_text();new=apply_change(old,change)
            item={'path':path,'status':'analyzed','before_sha256':digest(old.encode()),'after_sha256':digest(new.encode())}
            if path.endswith('.py'):item['semantic']=semantic_edits(old,new)
            if path.endswith('.sql'):
                item['reader_deltas']={}
                for kind in ('sql','pairs'):
                    try:
                        a,b=normalize(old,kind),normalize(new,kind)
                        delta=[]
                        for i in range(max(len(a),len(b))):
                            av=a[i] if i<len(a) else None;bv=b[i] if i<len(b) else None
                            if av!=bv:delta.append({'record':i,'before':av,'after':bv})
                        item['reader_deltas'][kind]={'changed':delta,'before_count':len(a),'after_count':len(b)}
                    except (IndexError,ValueError):item['reader_deltas'][kind]={'status':'unknown'}
            item['whole_test_nonimpact_proven']=False
            records.append(item)
        except (UnicodeError,ValueError):records.append({'path':path,'status':'unknown','reason':'invalid_context'})
    return records
