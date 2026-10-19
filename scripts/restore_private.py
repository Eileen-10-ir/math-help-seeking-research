"""Restore the frozen private research archive outside tracked source directories."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'.private/workspace'
EXPECTED='76f0b9ddb20b319b60e7b6944d8c56629e90aefd9d780e0798799f099c1b7c9f'
PREFIX='共享研究资料/研究工作区/'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
    assert hashlib.sha256(a.archive.read_bytes()).hexdigest()==EXPECTED,'请使用冻结内层共享ZIP，而非三部分外层ZIP'
    with zipfile.ZipFile(a.archive) as z:
        assert z.testzip() is None
        manifest_bytes=z.read(PREFIX+'release_manifest.json');manifest=json.loads(manifest_bytes.decode('utf-8'))
        pending=[]
        for relative,h in manifest['protected_files'].items():
            dest=(WORK/relative).resolve();assert dest.is_relative_to(WORK.resolve()) and '.git' not in Path(relative).parts
            content=z.read(PREFIX+relative);assert hashlib.sha256(content).hexdigest()==h
            if dest.exists():assert dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest()==h,('已有文件改动，停止恢复',relative)
            else:pending.append((dest,content))
        if (WORK/'release_manifest.json').exists():assert (WORK/'release_manifest.json').read_bytes()==manifest_bytes
        for dest,content in pending:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
        (WORK/'release_manifest.json').write_bytes(manifest_bytes)
    print(json.dumps({'protected_files_checked':len(manifest['protected_files']),'newly_restored':len(pending),
        'workspace':str(WORK),'student_data_tracked':False,'next':'python -s -X utf8 run.py check'},ensure_ascii=False))
