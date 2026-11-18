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
    s=sub.add_parser('serve',help='启动需求感知B3支持网页，识别/状态保留冻结版');s.add_argument('--port',type=int,default=8771)
    s.add_argument('--policy',choices=['B3','revision'],default='B3',help='revision为连续支持候选，非质量已证实改进')
    s=sub.add_parser('serve-frozen',help='重现原三级支持网页');s.add_argument('--port',type=int,default=8773)
    m=sub.add_parser('serve-memory',help='独立候选网页：带来源的对话记忆，不替换共同模型')
    m.add_argument('--port',type=int,default=8772)
    m.add_argument('--mode',dest='memory_mode',choices=['recent','summary','graph'],default='graph')
    m.add_argument('--continuation-help',action='store_true',help='另启待核实步骤核对策略；不改变等级或状态')
    m.add_argument('--refined-guidance',action='store_true',help='使用允许核对已有结果的中类模板v11')
    s=sub.add_parser('compare',help='四组系统回复对照，默认离线');s.add_argument('--real',action='store_true')
    sub.add_parser('train',help='在新目录复现当前识别比较，不自动替换运行模型')
    sub.add_parser('generate',help='在新目录复现联合数据生成与结构审核')
    sub.add_parser('budget',help='容量先验核查＋0/45/91合成数量实验，只运行一次防止覆盖')
    study=sub.add_parser('study',help='复现20261118参数补充实验，不自动替换在线模型')
    study.add_argument('kind',choices=['selection','summarize','ablation','state','system','continuity'])
    study.add_argument('--name',default='参数完善实验20261118_复现');study.add_argument('--smoke',action='store_true');study.add_argument('--real',action='store_true')
    a=p.parse_args()
    assert sys.flags.no_user_site,'请使用 python -s -X utf8 run.py ...'
    if a.mode=='study':
        subprocess.run([sys.executable,'-s','-X','utf8',str(ROOT/'scripts/run_parameter_study.py'),a.kind,'--name',a.name,*(['--smoke'] if a.smoke else []),*(['--real'] if a.real else [])],cwd=ROOT,check=True)
        raise SystemExit(0)
    if a.mode=='serve':
        dest=ROOT/'.private/latest_runs'/uuid.uuid4().hex[:12]
        subprocess.run([sys.executable,'-s','-X','utf8',str(ROOT/'src/latest_runtime.py'),'--port',str(a.port),'--db',str(dest/'sessions.sqlite3'),'--policy',a.policy],cwd=ROOT,check=True)
        raise SystemExit(0)
    if a.mode=='serve-frozen':a.mode='serve'
    if a.mode=='serve-memory':
        dest=ROOT/'.private/memory_runs'/uuid.uuid4().hex[:12]
        dest.mkdir(parents=True)
        subprocess.run([sys.executable,'-s','-X','utf8',str(ROOT/'src/memory_runtime.py'),
            '--port',str(a.port),'--mode',a.memory_mode,'--db',str(dest/'sessions.sqlite3'),
            *(['--continuation-help'] if a.continuation_help else []),
            *(['--refined-guidance'] if a.refined_guidance else [])],cwd=ROOT,check=True)
        raise SystemExit(0)
    if a.mode in ['serve','compare']:
        from scripts.api_config import load_api_key
        load_api_key()
    sync_sources()
    if a.mode in ['check','serve','compare']:
        args=[a.mode]
        if a.mode=='serve':args+=['--port',str(a.port)]
        if a.mode=='compare' and a.real:args+=['--real']
        execute(WORK/CURRENT/'code/run_mainline.py',*args)
        if a.mode=='check':
            subprocess.run([sys.executable,'-s','-X','utf8','-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],cwd=ROOT,check=True)
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
