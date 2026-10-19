"""Interactive local-only setup, avoiding secrets in command history."""
from getpass import getpass
from api_config import KEY_FILE

if __name__=='__main__':
    key=getpass('粘贴小组授权使用的DeepSeek密钥（不回显）：').strip()
    if not key or '\n' in key or '\r' in key:raise SystemExit('未保存：请提供一行非空密钥。')
    KEY_FILE.parent.mkdir(parents=True,exist_ok=True)
    KEY_FILE.write_text(key+'\n',encoding='utf-8')
    print('已保存到本机Git忽略目录。运行 python -s -X utf8 scripts/check_api.py 检查配置。')
