"""Local reply candidate applied after the existing B3 route decision."""
import re
from fractions import Fraction

def local_revision(ctx, prompt, route):
    if route not in ('edge_verify','edge_fixed'):
        return None
    p=ctx.parameters
    t=prompt.translate(str.maketrans({'−':'-','－':'-','（':'(','）':')'}))
    if ctx.math_kind=='quadratic' and p['a']==1:
        pair=re.search(r'(?:我选|我选择|我找到)\s*(-?\d+)\s*(?:和|与)\s*(-?\d+)',t)
        if pair and route=='edge_verify':
            u,v=map(int,pair.groups())
            match=u+v==p['b'] and u*v==p['c']
            verdict='两项都符合，可以把这两个数分别写进两个因式。' if match else '这组数还不符合条件，请对照一次项系数和常数项重新选。'
            return '核验因数对', f'{u} 与 {v} 的和是 {u+v}，积是 {u*v}。本题要求和为 {p["b"]}、积为 {p["c"]}。{verdict}'
        if '为什么' in t and ('负数' in t or '取负' in t) and p['c']>0 and p['b']<0:
            return '解释符号',f'两个数的积为 {p["c"]}，所以它们同号。如果都取正数，和也一定是正数，无法得到 {p["b"]}；因此两个数都要取负号。试着用你列出的因数对检查它们的和。' if any('列出' in h['text'] for h in ctx.history if h.get('question')==ctx.question) else f'积为 {p["c"]} 说明两个数同号，和为 {p["b"]} 又排除了两个正数，因此两数都为负。'
        if '下一步' in t and route=='edge_verify':
            m=re.search(r'\(x([+-]\d+)\)\s*\*?\s*\(x([+-]\d+)\)',t)
            if m:
                u,v=map(int,m.groups())
                if u+v==p['b'] and u*v==p['c']:
                    return '核验并推进','你的分解正确，展开后的一次项系数和常数项都与原式相符。现在两因式的乘积等于零，请分别令每个因式等于零，写出两个一次方程。'
    if ctx.math_kind=='triangle_area' and '为什么' in t and ('除以2' in t or '除以二' in t):
        return '解释面积公式','两个全等三角形可以拼成同底同高的平行四边形。底乘高得到的是两个三角形的总面积，取其中一个就要除以2。'
    if ctx.math_kind=='same_denominator_fraction':
        d=p['d']; num=p['a']+p['b']; expected=Fraction(num,d)
        prior=[]
        for h in ctx.history:
            if h.get('task_id')==ctx.task_id and h.get('question')==ctx.question:
                for n,b in re.findall(r'(\d+)/(\d+)',h['text']):
                    if int(b)>0 and Fraction(int(n),int(b))==expected:
                        prior.append((int(n),int(b)))
        if route=='edge_verify' and '约分' in t and ('为什么' in t or '怎么约' in t):
            m=re.search(r'(?:得到|写成|等于)\s*(\d+)/(\d+)',t)
            if m and int(m[2])>0:
                n,b=map(int,m.groups());u,v=prior[-1] if prior else (num,d)
                if Fraction(n,b)==expected and v>b and v%b==0:
                    k=v//b
                    return '核验并解释约分',f'对，{u}/{v} 约成 {n}/{b} 是正确的。分子和分母同时除以公因数 {k}，两数的比值保持不变，所以分数的值也不变。'
        if '总结' in t and '同分母先加分子' in t and '再检查能否约分' in t and prior:
            return '承接已完成的计算','你总结的顺序正确：同分母时保留分母、合并分子，最后检查能否约分。你刚才的算式用到了这个方法。'
        if route=='edge_verify' and re.search(r'(?:先加分子|先把分子相加)对吗',t) and not re.search(r'\d+/\d+',t):
            return '核验本题方法',f'对，这两个分数的单位都是 1/{d}，可以先把分子 {p["a"]} 和 {p["b"]} 相加，分母保留 {d}。请写出相加后的分数。'
    return None
