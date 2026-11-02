"""Audit without exporting raw PII. Training MUST NOT interpret resolutions as compliance labels."""
import argparse,csv,hashlib,json,re
from collections import Counter
from pathlib import Path

PII_COLUMNS={'Customer Name','Customer Email','Customer Age','Customer Gender'}
PLACEHOLDER=re.compile(r'\{[^{}]+\}|\[YOUR[^\]]*\]|<[^>]+>')
EMAIL=re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b')
PHONE=re.compile(r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)')

def audit(source,output):
    rows=list(csv.DictReader(source.open(encoding='utf-8-sig')))
    columns=list(rows[0])
    missing={k:sum(not r[k].strip() for r in rows) for k in columns}
    descriptions=[r.get('Ticket Description','') for r in rows]
    report={'source_url':'https://github.com/Nadjib23/AI-Engineering-Course/blob/2b0c4d78f992dce0a6349121e543ff8dddce94d4/labs/datasets/customer_support_tickets.csv',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':len(rows),'columns':columns,
        'missing':missing,'duplicate_rows':len(rows)-len({tuple(r.items()) for r in rows}),
        'duplicate_descriptions':len(rows)-len(set(descriptions)),
        'placeholder_descriptions':sum(bool(PLACEHOLDER.search(s)) for s in descriptions),
        'placeholder_token_count':sum(len(PLACEHOLDER.findall(s)) for s in descriptions),
        'product_placeholder_occurrences':sum(s.count('{product_purchased}') for s in descriptions),
        'description_length':{'min':min(map(len,descriptions)),'max':max(map(len,descriptions)),
                              'mean':sum(map(len,descriptions))/len(descriptions)},
        'distributions':{k:dict(Counter(r[k] for r in rows)) for k in ['Ticket Type','Ticket Priority','Ticket Status','Ticket Channel']},
        'privacy':'Direct identifiers removed; residual text PII requires manual review before external use.',
        'labels':'Ticket resolutions are not policy-compliance labels.'}
    output.mkdir(parents=True,exist_ok=True)
    (output/'ticket_audit.json').write_text(json.dumps(report,indent=2))
    sanitized=[]
    for r in rows:
        d={k:v for k,v in r.items() if k not in PII_COLUMNS}
        # Remove identifiers appearing inside arbitrary text, not only dedicated columns.
        secrets=[r.get('Customer Name',''),r.get('Customer Email','')]
        for k,v in d.items():
            for s in secrets:
                if s: v=re.sub(re.escape(s),'[REDACTED]',v,flags=re.I)
            v=EMAIL.sub('[EMAIL]',v)
            d[k]=PHONE.sub('[NUMBER_REVIEW]',v)
        d['placeholder_flag']=bool(PLACEHOLDER.search(d.get('Ticket Description','')))
        # Group repeated descriptions to prevent duplicate leakage in later classification experiments.
        d['description_group']=hashlib.sha256(d.get('Ticket Description','').encode()).hexdigest()
        sanitized.append(d)
    # Local only; excluded from deliverable until reviewed. No raw samples in report.
    (output/'sanitized_tickets.jsonl').write_text('\n'.join(json.dumps(r) for r in sanitized))
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,default=Path('var/audit'))
    a=p.parse_args();r=audit(a.source,a.output);print(json.dumps({k:r[k] for k in ['rows','duplicate_rows','duplicate_descriptions','placeholder_descriptions']},indent=2))
