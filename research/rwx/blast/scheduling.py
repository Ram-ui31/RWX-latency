"""Minimize busiest-worker milliseconds plus 2000ms per active worker."""
import heapq

WORKER_COST_MS = 2000


def schedule_cost(workers, durations):
    active = [w for w in workers if w]
    return max((sum(durations[t] for t in w) for w in active), default=0) + WORKER_COST_MS * len(active)


def lpt(numbers, durations, count):
    bins = [[] for _ in range(count)]
    heap = [(0, i) for i in range(count)]
    heapq.heapify(heap)
    for test in sorted(numbers, key=lambda t: (-durations[t], t)):
        load, i = heapq.heappop(heap)
        bins[i].append(test)
        heapq.heappush(heap, (load + durations[test], i))
    return [w for w in bins if w]


def refine(workers, durations, rounds=8):
    """Bounded deterministic single-move and pair-swap improvement on small sets."""
    workers = [list(w) for w in workers]
    if len(workers) < 2 or sum(map(len, workers)) > 512:
        return workers
    loads = [sum(durations[t] for t in w) for w in workers]
    for _ in range(rounds):
        current = max(loads)
        heavy = max(range(len(loads)), key=lambda i: (loads[i], -i))
        # If several workers tie, a move may not reduce makespan immediately.
        # Keeping that plateau is intentional: refinement must never worsen cost.
        candidates = sorted(workers[heavy], key=lambda t: (-durations[t], t))[:32]
        best = None
        for other in range(len(workers)):
            if other == heavy:
                continue
            rest = max((v for i, v in enumerate(loads) if i not in (heavy, other)), default=0)
            for test in candidates:
                d = durations[test]
                newmax = max(rest, loads[heavy] - d, loads[other] + d)
                if newmax < current and (best is None or newmax < best[0]):
                    best = (newmax, other, test, None)
                for swap in sorted(workers[other], key=lambda t: (durations[t], t))[:32]:
                    delta = d - durations[swap]
                    newmax = max(rest, loads[heavy] - delta, loads[other] + delta)
                    if newmax < current and (best is None or newmax < best[0]):
                        best = (newmax, other, test, swap)
        if best is None:
            break
        _, other, test, swap = best
        workers[heavy].remove(test)
        workers[other].append(test)
        loads[heavy] -= durations[test]
        loads[other] += durations[test]
        if swap is not None:
            workers[other].remove(swap)
            workers[heavy].append(swap)
            loads[other] -= durations[swap]
            loads[heavy] += durations[swap]
    return [w for w in workers if w]


def optimize_schedule(numbers, durations, max_workers=8):
    numbers = sorted(set(numbers))
    if not numbers:
        return []
    total = sum(durations[t] for t in numbers)
    biggest = max(durations[t] for t in numbers)
    best, best_cost = None, None
    for count in range(1, min(max_workers, len(numbers)) + 1):
        bound = max(biggest, (total + count - 1) // count) + WORKER_COST_MS * count
        if best_cost is not None and bound >= best_cost:
            continue
        candidate = refine(lpt(numbers, durations, count), durations)
        cost = schedule_cost(candidate, durations)
        if best_cost is None or cost < best_cost:
            best, best_cost = candidate, cost
    return best
