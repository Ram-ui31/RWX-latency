"""Identity of a baseline-only deterministic native reference cache."""

import hashlib
import os
from pathlib import Path
import re
import time

from research.observations.capsule_env import fingerprint


def environment():
    return dict(
        runtime=fingerprint(), timezone=list(time.tzname), TZ=os.environ.get("TZ")
    )


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def volatile(sql):
    return bool(
        re.search(
            r"\b(CURRENT_DATE|CURRENT_TIME|CURRENT_TIMESTAMP|CURRENT_USER|SESSION_USER|LOCALTIME|LOCALTIMESTAMP|NOW|RAND|RANDOM|UUID|UUID_STRING|NEXTVAL|CURRVAL)\b",
            sql,
            re.I,
        )
    )
