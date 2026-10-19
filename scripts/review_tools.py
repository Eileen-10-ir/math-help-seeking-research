"""Validate independent review returns and summarize agreement without editing labels.

Inputs: two reviewer XLSX files (or directories of CSV files) and a private
schema-only review contract distributed with the forms. Outputs: JSON validation
or paired agreement summaries. No API, hidden target access, or automatic scoring.
"""
from pathlib import Path
import argparse, csv, json, re, zipfile, xml.etree.ElementTree as ET

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

def read_tables(path):
    path=Path(path)
    if path.is_dir():
        result={}
        for p in sorted(path.glob('*.csv')):
            with p.open(encoding='utf-8-sig',newline='') as f:
                result[p.stem]=list(csv.DictReader(f))
        return result
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(t.text or '' for t in si.findall('.//s:t',NS))
                     for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result={}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            target=rels[sh.attrib['{'+NS['r']+'}id']]
            name=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows=[]
            for row in ET.fromstring(z.read(name)).findall('s:sheetData/s:row',NS):
                values={}
                for cell in row.findall('s:c',NS):
                    if cell.find('s:f',NS) is not None:raise ValueError('Review fields must contain values, not formulas')
                    letters=re.match('[A-Z]+',cell.attrib['r']).group();idx=0
                    for ch in letters:idx=idx*26+ord(ch)-64
                    kind=cell.attrib.get('t');v=cell.find('s:v',NS)
                    value='' if v is None else v.text or ''
                    if kind=='s':value=strings[int(value)]
                    elif kind=='inlineStr':value=''.join(n.text or '' for n in cell.findall('.//s:t',NS))
                    values[idx-1]=value
                if values:rows.append(values)
            if not rows:result[sh.attrib['name']]=[];continue
            header=[rows[0].get(i,'') for i in range(max(rows[0])+1)]
            assert len(set(header))==len(header),'Duplicate column headers'
            result[sh.attrib['name']]=[{h:row.get(i,'') for i,h in enumerate(header)} for row in rows[1:] if any(row.values())]
        return result

def validate(tables,contract,allow_incomplete=False):
    issues=[];coverage={}
    for name,spec in contract['sheets'].items():
        rows=tables.get(name,[]);by={r.get('审核ID'):r for r in rows}
        if len(by)!=len(rows) or set(by)!=set(spec['readonly']):
            issues.append({'sheet':name,'issue':'Missing/duplicate/extra review IDs'});continue
        complete=0
        for rid,expected in spec['readonly'].items():
            row=by[rid]
            if set(row)!=set(spec['columns']):issues.append({'sheet':name,'id':rid,'issue':'Changed column headers'})
            if any(str(row.get(k,''))!=str(v) for k,v in expected.items()):
                issues.append({'sheet':name,'id':rid,'issue':'Read-only source content changed'})
            missing=[k for k in spec['required'] if str(row.get(k,'')).strip()=='']
            if missing and not allow_incomplete:issues.append({'sheet':name,'id':rid,'issue':'Missing required ratings','fields':missing})
            if not missing:complete+=1
            for k,allowed in spec['allowed'].items():
                v=str(row.get(k,'')).strip()
                if v and v not in allowed:issues.append({'sheet':name,'id':rid,'issue':'Invalid code','field':k})
            if any(str(row.get(k,''))=='0' for k in spec.get('score_fields',[])) and not str(row.get('问题或NA原因','')).strip():
                issues.append({'sheet':name,'id':rid,'issue':'Score 0 requires NA reason'})
            if name=='后续回应' and row.get('等级建议') not in ('', 'NA') and row.get('可判断等级')!='是':
                issues.append({'sheet':name,'id':rid,'issue':'Do not assign a grade when evidence is insufficient'})
        coverage[name]={'expected':len(spec['readonly']),'complete':complete}
    return {'passed':not issues,'coverage':coverage,'issues':issues,'labels_written':0}

def agreement(a,b,contract):
    from sklearn.metrics import cohen_kappa_score
    results=[]
    for name,spec in contract['sheets'].items():
        aa={r['审核ID']:r for r in a[name]};bb={r['审核ID']:r for r in b[name]}
        for field,allowed in spec['allowed'].items():
            scored=field in spec.get('score_fields',[]);pairs=[]
            for rid in spec['readonly']:
                x=str(aa[rid].get(field,'')).strip();y=str(bb[rid].get(field,'')).strip()
                excluded={'','0'} if scored else {'','NA','无法判断'}
                if x not in excluded and y not in excluded:pairs.append((x,y))
            same=sum(x==y for x,y in pairs);distinct={v for p in pairs for v in p};kappa=None
            if pairs and len(distinct)>1:
                order=[str(i) for i in range(1,6)] if scored else [v for v in allowed if v not in {'NA','无法判断'}]
                val=float(cohen_kappa_score([x for x,y in pairs],[y for x,y in pairs],labels=order,weights='linear' if scored else None))
                if val==val:kappa=val
            results.append({'sheet':name,'field':field,'valid_pairs':len(pairs),'excluded_pairs':len(spec['readonly'])-len(pairs),
                'agreement':None if not pairs else same/len(pairs),'kappa':kappa,'weighted':'linear' if scored else 'none',
                'kappa_note':'undefined with no pairs or a single shared category' if kappa is None else ''})
    return {'agreement':results,'raw_ratings_changed':False,'note':'Coverage/purposeful sample audit, not a population defect estimate or learning-effect measure.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['validate','agreement']);p.add_argument('--contract',required=True)
    p.add_argument('--input',required=True);p.add_argument('--other');p.add_argument('--allow-incomplete',action='store_true');p.add_argument('--out',required=True)
    a=p.parse_args();contract=json.loads(Path(a.contract).read_text(encoding='utf-8'));tables=read_tables(a.input)
    result=validate(tables,contract,a.allow_incomplete)
    if a.mode=='agreement':
        assert a.other,'Need the independent second return';other=read_tables(a.other);check=validate(other,contract)
        assert result['passed'] and check['passed'],'Both final returns must pass validation before agreement'
        result=agreement(tables,other,contract)
    out=Path(a.out);assert not out.exists(),'Preserve old results: use a new output path'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'written':str(out),'passed':result.get('passed'),'labels_written':0},ensure_ascii=False))
    if result.get('passed') is False:raise SystemExit(1)
