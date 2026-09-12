"""Reproduce D3 using immutable publisher source from the task-start commit.

Run with a fresh output directory inside this checkout. No checkout/reset is
performed; git show is read-only. All contenders are spawned processes and all
unsafe transitions are ordered by Events rather than probabilistic races.
"""
import sys, pathlib, multiprocessing as mp, json, time, importlib.util
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'components')] + [str(p) for p in (ROOT / 'components').glob('*/src')]
spec = importlib.util.spec_from_file_location('fixtures', ROOT / 'components/Grid81DeterministicCanonicalPublisher/tests/test_publisher.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
from elpis_grid81_application_executor import DurableApplicationLedger as Ledger
import subprocess, types
p = types.ModuleType("r0_publisher")
sys.modules[p.__name__] = p
BASE_HEAD = "0d64119896951aa1815a127b28b7b5a5989fab75"
source = subprocess.check_output(["git", "show", BASE_HEAD + ":components/Grid81DeterministicCanonicalPublisher/src/elpis_grid81_canonical_publisher/publisher.py"], cwd=ROOT)
exec(compile(source, "publisher_at_starting_HEAD.py", "exec"), p.__dict__)

def worker(root, candidate, db, cap, lock, reached, release, result, seam, attempted=None):
    if attempted is not None:
        from contextlib import contextmanager
        original_lock = p._exclusive_lock
        @contextmanager
        def entering(path):
            attempted.set()
            with original_lock(path):
                yield
        p._exclusive_lock = entering
    original = getattr(p, seam)
    def pause(*a, **kw):
        if seam == '_validate_successor':
            value = original(*a, **kw)
            reached.set(); assert release.wait(30)
            return value
        reached.set(); assert release.wait(30)
        return original(*a, **kw)
    setattr(p, seam, pause)
    with Ledger(db) as ledger:
        try:
            r = p.publish_candidate(project_root=root, candidate_root=candidate, ledger=ledger, promotion_capability=cap, lock_path=lock)
            result.send([r.status, r.resumed])
        except Exception as e:
            result.send([getattr(e, 'code', type(e).__name__), str(e)])

def trial(base, same_lock=False, same_candidate=False, same_head=False, alias=None):
    base.mkdir(); root=f._copy_root(base,'live'); db=base/'ledger.db'
    ctx=mp.get_context('spawn'); events=[ctx.Event() for _ in range(4)]
    a_ready,a_go,b_ready,b_go=events
    with Ledger(db) as ledger:
        ca=f._issue(root,ledger,artifact=f._h('a'))
        a,_=f._candidate(base,root,ca,'a')
        if same_head:
            cb=f._issue(root,ledger,approval='b',artifact=f._h('b'))
            b,_=f._candidate(base,root,cb,'b')
    ar,aw=ctx.Pipe(False); br,bw=ctx.Pipe(False)
    pa=ctx.Process(target=worker,args=(root,a,db,ca,base/'a.lock',a_ready,a_go,aw,'_validate_successor' if same_head else '_commit_exchange'))
    pa.start(); assert a_ready.wait(30)
    if not same_head:
        with Ledger(db) as ledger:
            cb=ca if same_candidate else f._issue(root,ledger,approval='b',artifact=f._h('b'))
            b=a if same_candidate else f._candidate(base,root,cb,'b')[0]
    broot=root
    if alias=='symlink':
        broot=base/'alias'; broot.symlink_to(root, target_is_directory=True)
    if alias=='dotdot': broot=root/'..'/'live'
    b_attempted=ctx.Event()
    pb=ctx.Process(target=worker,args=(broot,b,db,cb,base/('a.lock' if same_lock else 'b.lock'),b_ready,b_go,bw,'_commit_exchange' if same_candidate else '_validate_successor',b_attempted))
    pb.start()
    assert b_attempted.wait(30)
    if same_lock or alias=='symlink':
        entered=b_ready.wait(.3)
        a_go.set(); pa.join(30); b_go.set()
    else:
        assert b_ready.wait(30); entered=True
        if same_candidate:
            b_go.set(); pb.join(30); a_go.set()
        else:
            a_go.set(); pa.join(30); b_go.set()
    pa.join(30); pb.join(30)
    assert not pa.is_alive() and not pb.is_alive()
    with Ledger(db) as ledger:
        return dict(b_validated_before_a_visible=entered,a=ar.recv(),b=br.recv(),count=ledger.to_dict()['count'],valid=ledger.verify_chain(),generation=f.load_current_grid81(root).generation_number)

if __name__=='__main__':
    base=pathlib.Path(sys.argv[1]).resolve(); base.mkdir(parents=True)
    results={}
    for name,kw in [('same_lock',dict(same_lock=True)),('same_lock_same_head',dict(same_lock=True,same_head=True)),('different_locks_same_head',dict(same_head=True)),('ledger_ahead',{}),('same_candidate',dict(same_candidate=True)),('dotdot',dict(alias='dotdot')),('symlink',dict(alias='symlink'))]:
        results[name]=trial(base/name,**kw); print(name,results[name],flush=True)
    assert results['same_lock']['b'][0] == 'STALE_CANONICAL_HEAD'
    assert results['same_lock_same_head']['b'][0] == 'STALE_CANONICAL_HEAD'
    assert results['different_locks_same_head']['b_validated_before_a_visible']
    assert results['different_locks_same_head']['b'][0] == 'STALE_LEDGER_HEAD'
    assert results['ledger_ahead']['a'][0] == results['ledger_ahead']['b'][0] == 'COMMITTED'
    assert results['ledger_ahead']['count'] == results['dotdot']['count'] == 2
    assert results['same_candidate']['count'] == 1
    assert results['same_candidate']['a'][0] == 'ATOMIC_EXCHANGE_FAILED'
    assert results['same_candidate']['b'] == ['COMMITTED', True]
    assert results['symlink']['b'][0] == 'CANONICAL_READER_REJECTED'
    (base/'results.json').write_text(json.dumps(results,indent=2)+'\n')
