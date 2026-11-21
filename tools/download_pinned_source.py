#!/usr/bin/env python3
"""Build-only source download from SQLGlot's own immutable commit URL."""
import posixpath
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import urllib.request

PIN='eb11aec4be8cb2122afe713a4816662c3f0fb2fa'
URL='https://github.com/tobymao/sqlglot/archive/'+PIN+'.tar.gz'

def extract_members(tar, members, destination, prefix):
    """Copy files and internal file-link contents without creating OS links."""
    files, links = {}, {}
    inventory = {member.name: member for member in members}
    for member in members:
        if member.isdir():
            continue
        relative = Path(member.name[len(prefix):])
        if not member.name.startswith(prefix) or relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe source archive path: ' + member.name)
        target_member = member
        seen = set()
        while target_member.issym():
            if target_member.name in seen:
                raise ValueError('Cyclic archive link: ' + member.name)
            seen.add(target_member.name)
            link = target_member.linkname
            if posixpath.isabs(link):
                raise ValueError('Absolute archive link: ' + member.name)
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(target_member.name), link))
            if not resolved.startswith(prefix) or resolved not in inventory:
                raise ValueError('Escaping or missing archive link: ' + member.name)
            target_member = inventory[resolved]
        if not target_member.isfile():
            raise ValueError('Unsupported source archive member: ' + member.name)
        if member.issym():
            links[relative.as_posix()] = member.linkname
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = tar.extractfile(target_member).read()
        target.write_bytes(content)
        files[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    return files, links


def main():
    destination=Path(sys.argv[1]).resolve()
    if destination.exists() and any(destination.iterdir()): raise SystemExit('Destination is not empty')
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        archive=Path(temp)/'source.tar.gz'
        with urllib.request.urlopen(URL,timeout=60) as response,archive.open('wb') as f:
            shutil.copyfileobj(response,f)
        archive_hash=hashlib.sha256(archive.read_bytes()).hexdigest()
        with tarfile.open(archive) as tar:
            members=tar.getmembers()
            prefix='sqlglot-'+PIN+'/'
            files, links = extract_members(tar, members, destination, prefix)
        (destination/'.source-origin.json').write_text(json.dumps(dict(source_commit=PIN,url=URL,archive_sha256=archive_hash,files=files,materialized_links=links),sort_keys=True))
    print('Pinned source downloaded and file hashes recorded.')

if __name__=='__main__':main()
