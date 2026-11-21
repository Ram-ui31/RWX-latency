"""Fail early with the native component and CPU signal, instead of opaque 132."""
import platform,subprocess,sys
print('Native runtime:',platform.platform(),platform.machine(),flush=True)
checks=[('NumPy','import numpy as n; print(n.__version__); print(n.sum(n.arange(1000)))'),
        ('pandas','import pandas as p; print(p.__version__); print(p.DataFrame({"x":[1,2]}).sum())'),
        ('DuckDB','import duckdb; print(duckdb.__version__); print(duckdb.connect().execute("SELECT SUM(i) FROM range(1000) t(i)").fetchall())')]
for name,code in checks:
 print('Checking '+name,flush=True)
 p=subprocess.run([sys.executable,'-X','faulthandler','-c',code])
 if p.returncode:
  print(f'{name} failed with status {p.returncode}. '+('SIGILL: native CPU instruction failure; use a native amd64 runner to distinguish emulation from a package problem.' if p.returncode in (-4,132) else 'See output above.'),file=sys.stderr,flush=True)
  raise SystemExit(1)
