import os, atexit, json
from pathlib import Path

if "RWX_TYPED_OUT" in os.environ:
    import hook

    Path(os.environ["RWX_TYPED_OUT"], f"start-{os.getpid()}.json").write_text(
        json.dumps(os.environ.get("RWX_TYPED_NODE", ""))
    )
    hook.install(os.environ["RWX_TYPED_SOURCE"])

    @atexit.register
    def flush():
        Path(os.environ["RWX_TYPED_OUT"], f"{os.getpid()}.json").write_text(
            json.dumps({k: sorted(v) for k, v in hook.reads.items()})
        )

    # Real spawned workers persist across tests. Attach the current whole-test owner
    # to every task while preserving the original serialization and process pool.
    from concurrent.futures import ProcessPoolExecutor

    original_submit = ProcessPoolExecutor.submit

    def submit(pool, func, /, *args, **kwargs):
        node = hook.active or os.environ.get("RWX_TYPED_NODE", "")
        return original_submit(pool, hook.task, node, func, args, kwargs)

    ProcessPoolExecutor.submit = submit
