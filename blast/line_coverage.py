"""Build-time, per-test line reachability using Python 3.13 monitoring.

Locations disable themselves after their first hit; restart at each test boundary.
Unavailable monitoring means no line-based exclusion, not missing coverage.
"""
import sys
import os

_owners = {}


class LineMonitor:
    def __init__(self, relative, record):
        # Linux pools may fork while the parent's monitor is installed. Clear
        # only our inherited hooks before installing this child's own monitor.
        for owner in list(_owners.values()):
            if owner.pid != os.getpid():
                owner.close()
        self.pid = os.getpid()
        self.relative = relative
        self.record = record
        self.tool = None
        self.codes = set()
        self.paths = {}
        self.monitoring = getattr(sys, 'monitoring', None)
        if self.monitoring is None:
            return
        for tool in (5, 4, 3):
            try:
                self.monitoring.use_tool_id(tool, 'rwx-baseline-lines')
            except ValueError:
                continue
            self.tool = tool
            _owners[tool] = self
            self.monitoring.register_callback(tool, self.monitoring.events.LINE, self.hit)
            break

    @property
    def enabled(self):
        return self.tool is not None

    def observe_code(self, code, path):
        if self.enabled and code not in self.codes:
            self.codes.add(code)
            self.paths[code] = path
            self.monitoring.set_local_events(self.tool, code, self.monitoring.events.LINE)

    def hit(self, code, line):
        self.record(self.paths[code], line)
        return self.monitoring.DISABLE

    def restart(self):
        if self.enabled:
            self.monitoring.restart_events()

    def close(self):
        if self.enabled:
            for code in self.codes:
                self.monitoring.set_local_events(self.tool, code, 0)
            self.monitoring.register_callback(self.tool, self.monitoring.events.LINE, None)
            self.monitoring.free_tool_id(self.tool)
            if _owners.get(self.tool) is self:
                _owners.pop(self.tool)
            self.tool = None
