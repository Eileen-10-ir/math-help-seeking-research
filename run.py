"""Common project CLI. No member-package or document-production entry points."""
from pathlib import Path
import argparse,subprocess,sys,json,uuid,shutil,importlib.util

ROOT=Path(__file__).resolve().parent
CORE=ROOT/'src/frozen_core'
WORK=ROOT/'.private/workspace'
CURRENT='数学共同主线定版20261018'

def sync_sources():
    if not (WORK/'release_manifest.json').exists():
        raise SystemExit('先运行 python -s -X utf8 scripts/restore_private.py --archive <私有共享ZIP>')
    manifest=json.loads((ROOT/'project_manifest.json').read_text(encoding='utf-8'))
    for path in manifest['core_sources']:
        source=CORE/path;dest=WORK/path
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    for source in (ROOT/'web').rglob('*'):
        if source.is_file():
            dest=WORK/CURRENT/'app'/source.relative_to(ROOT/'web')
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)

def execute(path,*args):
    subprocess.run([sys.executable,'-s','-X','utf8',str(path),*map(str,args)],cwd=WORK,check=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description='数学AI求助研究：共用流程入口')
    sub=p.add_subparsers(dest='mode',required=True)
    sub.add_parser('check',help='冻结契约、识别复算、状态/HTTP、四组离线验收')
    s=sub.add_parser('serve',help='启动本机连续交互网页');s.add_argument('--port',type=int,default=8771)
    s=sub.add_parser('compare',help='四组系统回复对照，默认离线');s.add_argument('--real',action='store_true')
    sub.add_parser('train',help='在新目录复现当前识别比较，不自动替换运行模型')
    sub.add_parser('generate',help='在新目录复现联合数据生成与结构审核')
    sub.add_parser('budget',help='容量先验核查＋0/45/91合成数量实验，只运行一次防止覆盖')
    a=p.parse_args()
    assert sys.flags.no_user_site,'请使用 python -s -X utf8 run.py ...'
    if a.mode in ['serve','compare']:
        from scripts.api_config import load_api_key
        load_api_key()
    sync_sources()
    if a.mode in ['check','serve','compare']:
        args=[a.mode]
        if a.mode=='serve':args+=['--port',str(a.port)]
        if a.mode=='compare' and a.real:args+=['--real']
        execute(WORK/CURRENT/'code/run_mainline.py',*args)
    elif a.mode=='budget':
        folder=WORK/'合成数量学习曲线20261018'
        if (folder/'results/summary.json').exists():raise SystemExit('预算实验已有结果；请在独立工作副本复现，禁止覆盖。')
        execute(folder/'code/check_capacity.py');execute(folder/'code/run_budget.py')
    else:
        dest=WORK/'交付结果'/(a.mode+'_'+uuid.uuid4().hex[:10])
        if a.mode=='generate':
            execute(WORK/'统一数据与交接准备20261014/code/prepare_data.py','--output-dir',dest)
        else:
            # The frozen runner's OUT is redirected, while its ROOT and input metadata remain unchanged.
            source=WORK/CURRENT;dest.mkdir(parents=True)
            for name in ['code','data','results']:(dest/name).mkdir()
            shutil.copy2(source/'01_执行前协议.md',dest/'01_执行前协议.md')
            shutil.copy2(source/'code/route_models.py',dest/'code/route_models.py')
            sys.path.insert(0,str(source/'code'))
            spec=importlib.util.spec_from_file_location('recognition_reproduction',source/'code/run_recognition.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.OUT=dest;module.main()
        print(json.dumps({'output_directory':str(dest),'runtime_model_changed':False},ensure_ascii=False))
