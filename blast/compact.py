"""Pack baseline test-context sets into stable, catalog-independent bitsets."""


def pack_contexts(payload):
    if payload.get('context_encoding'):
        raise ValueError('Context sets are already encoded')
    ids = sorted(payload['collected'])
    positions = {value: i for i, value in enumerate(ids)}
    def bits(values):
        value = 0
        for context in values:
            value |= 1 << positions[context]
        return 'bits:' + format(value, 'x')
    for field in ('calls', 'lines'):
        payload[field] = {path: {line: bits(contexts) for line, contexts in rows.items()}
                          for path, rows in payload.get(field, {}).items()}
    for field in ('reads', 'module_users'):
        payload[field] = {path: bits(contexts) for path, contexts in payload.get(field, {}).items()}
    for field in ('line_tests', 'line_incomplete'):
        if field in payload:
            payload[field] = bits(payload[field])
    for record in payload.get('fixtures', {}).values():
        record['readers'] = {kind: bits(contexts) for kind, contexts in record['readers'].items()}
    payload['context_encoding'] = 'hex-v1'
    payload['context_ids'] = ids
    return payload
