"""Exercise the production commit step with dirty bootstrap CSVs and remote edits."""
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


def git(cwd,*args):
    result = subprocess.run(['git',*args],cwd=cwd,text=True,capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class WorkflowCommitTests(unittest.TestCase):
    def test_dirty_csv_and_disjoint_remote_commit_are_preserved(self):
        workflow = Path(__file__).resolve().parents[1]/'.github/workflows/seoul-apartment-history.yml'
        block = workflow.read_text().split('      - name: Commit successful monthly results\n',1)[1].split('      - name:',1)[0]
        script = textwrap.dedent(block.split('        run: |\n',1)[1])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);remote = root/'remote.git';runner = root/'runner';other = root/'other'
            git(root,'init','--bare','--initial-branch=main',str(remote))
            git(root,'clone',str(remote),str(runner))
            for workspace in (runner,):
                git(workspace,'config','user.name','test');git(workspace,'config','user.email','test@example.invalid')
            base = runner/'seoul-apartment-collector';base.mkdir()
            for name in ('r2_manifest.json','state.json','status.json','backfill_progress.json','gyeonggi_backfill_progress.json'):
                (base/name).write_text('{}\n')
            for directory in ('updates','recoveries'):
                (base/directory).mkdir();(base/directory/'.gitkeep').write_text('')
            seed = base/'data/sale/2026/11110/202610.csv.gz'
            seed.parent.mkdir(parents=True);seed.write_bytes(b'old bootstrap data')
            git(runner,'add','.');git(runner,'commit','-m','baseline');git(runner,'push','origin','main')
            git(root,'clone',str(remote),str(other))
            git(other,'config','user.name','test');git(other,'config','user.email','test@example.invalid')
            (other/'README.md').write_text('concurrent independent update\n')
            git(other,'add','.');git(other,'commit','-m','unrelated update');git(other,'push','origin','main')
            seed.write_bytes(b'new data already uploaded to R2')
            (base/'state.json').write_text(json.dumps({'daily_requests':4657})+'\n')
            (base/'updates/2026').mkdir();(base/'updates/2026/10.jsonl').write_text('{"event_id":"example"}\n')
            (base/'recoveries/receipt.json').write_text('{"verified":true}\n')
            result = subprocess.run(['bash','-e','-c',script],cwd=runner,text=True,capture_output=True)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            self.assertEqual(4657,json.loads(git(remote,'show','main:seoul-apartment-collector/state.json'))['daily_requests'])
            self.assertEqual('concurrent independent update',git(remote,'show','main:README.md'))
            self.assertEqual('old bootstrap data',git(remote,'show','main:seoul-apartment-collector/data/sale/2026/11110/202610.csv.gz'))
            self.assertEqual(b'new data already uploaded to R2',seed.read_bytes())
            self.assertEqual('{"verified":true}',git(remote,'show','main:seoul-apartment-collector/recoveries/receipt.json'))
            self.assertTrue(git(runner,'status','--porcelain').startswith('M seoul-apartment-collector/data/'))


if __name__=='__main__':unittest.main(verbosity=2)
