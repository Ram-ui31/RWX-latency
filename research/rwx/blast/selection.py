"""Use baseline execution evidence conservatively; unknown changes select all tests."""
import ast
import gzip
import json
import hashlib
from functools import lru_cache
from pathlib import Path
from .indexing import PINNED_COMMIT, parse_source
from .patches import PatchError, apply_change, parse_patch
from .fixture_contracts import VERSION, EXPECTED_HELPER_FINGERPRINT, equivalent
from .semantics import changed_execution_lines, identical_code, docstrings_changed


class SourceIndex:
    def __init__(self, path, id_to_number):
        self.payload = None
        self.reason = 'index_missing'
        self.ids = id_to_number
        self.all = set(id_to_number.values())
        self.unobserved = set()
        if path is None or not Path(path).is_file():
            return
        try:
            with gzip.open(path,'rt',encoding='utf-8') as f:
                p = json.load(f)
            if p.get('format_version') != 1 or p.get('source_commit') != PINNED_COMMIT:
                self.reason = 'index_version_mismatch'; return
            if 'untraced' not in p:
                self.reason = 'legacy_index_without_lifecycle_guards'; return
            if p.get('context_encoding') not in (None,'hex-v1'):
                self.reason = 'unknown_context_encoding'; return
            if p.get('context_encoding') and sorted(p.get('context_ids',[])) != sorted(p.get('collected',[])):
                self.reason = 'invalid_context_inventory'; return
            partial = p.get('partial_allowed', False)
            if p.get('baseline_exit_code') != 0 and not partial:
                self.reason = 'baseline_suite_failed'; return
            if not set(id_to_number).issubset(set(p.get('collected',[]))) and not partial:
                self.reason = 'catalog_not_fully_collected'; return
            uncertain = {t for t in id_to_number if 'skipped' in p.get('outcomes',{}).get(t,[]) or 'failed' in p.get('outcomes',{}).get(t,[]) or not p.get('outcomes',{}).get(t)}
            uncertain.update(set(p.get('untraced',[])) & set(id_to_number))
            baseline_uncertain = {t for t in uncertain if t not in set(p.get('untraced',[]))}
            if baseline_uncertain and not partial:
                self.reason = 'catalog_baseline_incomplete'; return
            self.unobserved = {id_to_number[t] for t in uncertain}
            self.payload = p
            self.reason = 'usable'
        except (OSError, ValueError, KeyError, TypeError):
            self.reason = 'invalid_index'

    def map_ids(self, ids):
        if isinstance(ids,str):
            return set(self.decode_context_bits(ids))
        return {self.ids[t] for t in ids if t in self.ids}

    @lru_cache(maxsize=8192)
    def decode_context_bits(self, value):
        if not self.payload or self.payload.get('context_encoding') != 'hex-v1' or not value.startswith('bits:'):
            raise ValueError('Unsupported context bitset')
        bits=int(value[5:],16)
        contexts=self.payload['context_ids']
        if bits < 0 or bits.bit_length() > len(contexts):
            raise ValueError('Context bitset exceeds inventory')
        result=set()
        while bits:
            bit=bits & -bits
            context=contexts[bit.bit_length()-1]
            if context in self.ids:result.add(self.ids[context])
            bits-=bit
        return frozenset(result)

    def file_consumers(self,path):
        p = self.payload
        consumers = self.map_ids(p.get('reads',{}).get(path,[]))
        consumers.update(self.map_ids(p.get('module_users',{}).get(path,[])))
        for ids in p.get('calls',{}).get(path,{}).values():
            consumers.update(self.map_ids(ids))
        # Include tests located in a changed test module, including collection failures.
        consumers.update(n for t,n in self.ids.items() if t.split('::',1)[0] == path)
        return consumers

    def select(self, patch_text, mode='all'):
        if mode == 'all':
            return set(self.all), 'all_tests_baseline'
        if not self.payload:
            return set(self.all), self.reason
        p = self.payload
        try:
            changes = parse_patch(patch_text)
            selected = set(self.unobserved)
            fixture_only = all(c.old_path.endswith('.sql') and c.new_path == c.old_path for c in changes)
            for change in changes:
                path = change.old_path
                if change.binary or not path or path != change.new_path or not change.hunks:
                    return set(self.all), 'unsupported_or_structural_file_change'
                if path.startswith('tests/') and path.endswith('.py'):
                    # Edits to shared test helpers/conftest can affect every test.
                    # Limiting to the file is not safe without full fixture/import analysis.
                    return set(self.all), 'test_or_fixture_code_change'
                if not path.endswith('.py'):
                    if path in p.get('collection_reads',[]):
                        return set(self.all), 'collection_time_file_dependency'
                    readers = self.map_ids(p.get('reads',{}).get(path,[]))
                    if not readers:
                        return set(self.all), 'untracked_data_dependency'
                    fixture = p.get('fixtures',{}).get(path)
                    if mode == 'impact' and fixture_only and fixture and p.get('fixture_contract_version') == VERSION and p.get('fixture_helper_fingerprint') == EXPECTED_HELPER_FINGERPRINT:
                        old = fixture['source']
                        if hashlib.sha256(old.encode()).hexdigest() != fixture['sha256']:
                            return set(self.all), 'fixture_source_hash_mismatch'
                        new = apply_change(old,change)
                        kinds = fixture['readers']
                        attributed = set().union(*(self.map_ids(tests) for tests in kinds.values()))
                        if attributed == readers and equivalent(old,new,kinds):
                            # Unknown tests remain selected. This is a scoped
                            # baseline reader certificate, not a blanket SQL
                            # comment/whitespace exemption.
                            continue
                    selected.update(readers)
                    continue
                info = p.get('files',{}).get(path)
                if not info:
                    return set(self.all), 'source_file_not_indexed'
                changed = apply_change(info['source'],change)
                # Syntax errors can prevent importing an entire package/test module.
                parse_source(changed)
                if mode == 'impact':
                    if docstrings_changed(info['source'],changed):
                        return set(self.all), 'docstring_or_metadata_observers_unknown'
                    if identical_code(info['source'],changed,path):
                        selected.update(self.map_ids(p.get('reads',{}).get(path,[])))
                        continue
                before = [(x['name'],x['kind']) for x in info['scopes']]
                from .indexing import describe_source
                after = [(x['name'],x['kind']) for x in describe_source(changed)['scopes']]
                if before != after:
                    return set(self.all), 'scope_added_removed_or_renamed'
                removed, inserted = change.positions()
                positions = sorted(removed | inserted)
                if not positions:
                    return set(self.all), 'no_tracked_content_change'
                scopes = []
                module_change = False
                for line in positions:
                    containing = [s for s in info['scopes'] if s['start'] <= line <= s['end'] and s['kind']=='function']
                    if not containing:
                        module_change = True
                        continue
                    chosen = min(containing,key=lambda s:s['end']-s['start'])
                    if line <= chosen.get('header_end', chosen['start']):
                        module_change = True
                        continue
                    scopes.append(chosen)
                if module_change:
                    if mode != 'hybrid':
                        return set(self.all), 'module_or_class_level_change'
                    broader = self.file_consumers(path)
                    if not broader:
                        return set(self.all), 'module_change_without_evidence'
                    selected.update(broader)
                    continue
                line_targets = changed_execution_lines(info['source'],changed,{s['name'] for s in scopes}) if mode == 'impact' else None
                calls = p.get('calls',{}).get(path,{})
                consumers = self.map_ids(p.get('reads',{}).get(path,[]))
                for scope in scopes:
                    covered = set()
                    for firstline, test_ids in calls.items():
                        if scope['start'] <= int(firstline) <= scope['end']:
                            covered.update(self.map_ids(test_ids))
                    mapped = covered
                    if not mapped:
                        return set(self.all), 'changed_scope_without_test_evidence'
                    if line_targets and p.get('evidence_version') == 2 and not any(scope['start'] <= line <= scope['end'] for line in p.get('shared_function_lines',{}).get(path,[])):
                        complete = self.map_ids(p.get('line_tests',[])) - self.map_ids(p.get('line_incomplete',[]))
                        hit = set()
                        for line in line_targets:
                            if scope['start'] <= line <= scope['end']:
                                hit.update(self.map_ids(p.get('lines',{}).get(path,{}).get(str(line),[])))
                        mapped = (mapped - complete) | (mapped & hit)
                    consumers.update(mapped)
                if mode == 'module':
                    consumers.update(self.file_consumers(path))
                selected.update(consumers)
            if not selected:
                if mode == 'impact':
                    return set(), 'supported_nonimpact_empty'
                return set(self.all), 'empty_evidence_fallback'
            return selected, 'source_statement_and_reader_evidence' if mode == 'impact' else ('source_function_evidence' if mode=='coverage' else 'source_module_evidence')
        except (PatchError,SyntaxError,ValueError,KeyError,TypeError):
            return set(self.all), 'unparseable_patch_or_changed_source'
