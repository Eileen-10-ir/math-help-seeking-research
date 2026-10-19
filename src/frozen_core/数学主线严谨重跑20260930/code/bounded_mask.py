import re

def safe_mask(t):
    t=re.sub(r'图片','<IMAGE>',t)
    math_chars=r'[xXyY0-9+\-−－×✕÷*/^²(). \t]'
    t=re.sub(math_chars+r'+='+math_chars+r'+','<EQUATION>',t)
    t=re.sub(r'\d+(?:\s*[×÷*/+\-−]\s*\d+)+','<FORMULA>',t)
    t=re.sub(r'(?<![A-Za-z])[ABCD](?![A-Za-z])','<OPTION>',t)
    return re.sub(r'\d+(?:\.\d+)?','<NUM>',t)