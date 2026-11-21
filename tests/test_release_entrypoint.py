import contextlib,hashlib,importlib.util,io,json,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.source_origin import verify
from blast.indexing import PINNED_COMMIT

class OriginTests(unittest.TestCase):
 def test_archive_origin_and_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'a.py').write_text('x=1\n');m={'source_commit':PINNED_COMMIT,'url':'https://github.com/tobymao/sqlglot/archive/'+PINNED_COMMIT+'.tar.gz','files':{'a.py':hashlib.sha256((p/'a.py').read_bytes()).hexdigest()}}
   (p/'.source-origin.json').write_text(json.dumps(m));verify(p)
   (p/'a.py').write_text('x=2\n')
   with self.assertRaises(ValueError):verify(p)

class ProtocolTests(unittest.TestCase):
 def test_stage_logs_do_not_pollute_stdout_and_failed_composition_uses_upstream(self):
  s=importlib.util.spec_from_file_location('candidate',ROOT/'run_candidate.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);tail=p/'research/tail_verifier';tail.mkdir(parents=True);cut=p/'research/incremental_executor';cut.mkdir(parents=True)
   (tail/'evaluate.py').write_text("import sys,json\nfrom pathlib import Path\np=Path(sys.argv[sys.argv.index('--predictions')+1]);p.write_text(json.dumps({'commit':'x','workers':[]})+'\\n');print('diagnostic-only')\n")
   (cut/'compose.py').write_text('raise SystemExit(1)\n');m.ROOT=p
   out=io.StringIO()
   with tempfile.TemporaryFile(mode='w+t') as err:
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):m.main()
   self.assertEqual(json.loads(out.getvalue()),{'commit':'x','workers':[]})
   self.assertNotIn('diagnostic',out.getvalue())
if __name__=='__main__':unittest.main()
