"""Validate official test catalog and maintain integer-millisecond durations."""
from decimal import Decimal
import json
from pathlib import Path


def load_catalog(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    tests = payload['tests']
    if not isinstance(tests, list) or not tests:
        raise ValueError('Catalog must contain a nonempty tests array')
    ids, durations = {}, {}
    for position, test in enumerate(tests):
        number = test['number']
        if isinstance(number, bool) or number != position:
            raise ValueError('Test numbers must be consecutive integers from zero')
        if not isinstance(test['id'], str) or test['id'] in ids:
            raise ValueError('Test IDs must be unique strings')
        seconds = Decimal(str(test['seconds']))
        if not seconds.is_finite() or seconds < 0:
            raise ValueError('Invalid test duration')
        millis = seconds * 1000
        if millis != millis.to_integral_value():
            raise ValueError('Official durations must have millisecond precision')
        ids[test['id']] = number
        durations[number] = int(millis)
    return tests, ids, durations
