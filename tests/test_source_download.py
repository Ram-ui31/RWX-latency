import importlib.util,io,tarfile,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('download',ROOT/'tools/download_pinned_source.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class ArchiveLinks(unittest.TestCase):
 def archive(self,link):
  data=io.BytesIO()
  with tarfile.open(fileobj=data,mode='w') as tar:
   entry=tarfile.TarInfo('root/AGENTS.md');entry.size=4;tar.addfile(entry,io.BytesIO(b'test'))
   entry=tarfile.TarInfo('root/CLAUDE.md');entry.type=tarfile.SYMTYPE;entry.linkname=link;tar.addfile(entry)
  data.seek(0);return tarfile.open(fileobj=data,mode='r')
 def test_internal_link_is_materialized(self):
  with tempfile.TemporaryDirectory() as d,self.archive('AGENTS.md') as tar:
   files,links=m.extract_members(tar,tar.getmembers(),Path(d),'root/')
   self.assertEqual((Path(d)/'CLAUDE.md').read_bytes(),b'test');self.assertFalse((Path(d)/'CLAUDE.md').is_symlink())
   self.assertEqual(files['AGENTS.md'],files['CLAUDE.md']);self.assertEqual(links['CLAUDE.md'],'AGENTS.md')
 def test_escaping_and_absolute_links_rejected(self):
  for link in ('../../outside','/etc/passwd'):
   with tempfile.TemporaryDirectory() as d,self.archive(link) as tar:
    with self.assertRaises(ValueError):m.extract_members(tar,tar.getmembers(),Path(d),'root/')
 def test_cycles_rejected(self):
  with tempfile.TemporaryDirectory() as d,self.archive('CLAUDE.md') as tar:
   with self.assertRaises(ValueError):m.extract_members(tar,tar.getmembers(),Path(d),'root/')
if __name__=='__main__':unittest.main()
