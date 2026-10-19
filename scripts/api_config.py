"""Local API credential loading; no credential is stored in tracked files."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
KEY_FILE=ROOT/'.private/deepseek_api_key.txt'

def load_api_key():
    if os.environ.get('MATH_DEEPSEEK_API_KEY','').strip():return 'environment'
    if KEY_FILE.exists():
        key=KEY_FILE.read_text(encoding='utf-8-sig').strip()
        if key:
            if '\n' in key or '\r' in key:raise ValueError('本机密钥文件只能包含一行密钥')
            os.environ['MATH_DEEPSEEK_API_KEY']=key
            return 'local_private_file'
    return 'not_configured'
