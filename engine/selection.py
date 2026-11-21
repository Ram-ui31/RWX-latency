"""Hybrid granularity: supported statement/reader evidence, broad initialization.

Does not implement or claim the full NameRTS algorithm. The existing source
index owns supported-region checks; this layer chooses a granularity, not a
failure posterior. No public outcomes enter its decisions.
"""

def adaptive_select(index,text):
    selected,reason=index.select(text,'impact')
    if reason=='module_or_class_level_change':
        selected,broad_reason=index.select(text,'hybrid')
        return selected,'initialization:'+broad_reason
    return selected,'fine:'+reason
