"""Real SentenceTransformer fine-tuning, fixed splits, validation-selected checkpoint.
Triplet loss with explicit negatives avoids in-batch false negatives for repeated policy positives.
"""
import argparse,copy,hashlib,json,os,random,time
from pathlib import Path
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from claimguard.runtime import BASE_MODEL, BASE_REVISION
from claimguard.corpora import paths as corpus_paths, CORPORA

def main(home,epochs=3,lr=2e-5,seed=42,corpus='novaretail'):
    torch.set_num_threads(min(4,os.cpu_count() or 1));torch.manual_seed(seed);random.seed(seed);np.random.seed(seed)
    locations=corpus_paths(home,corpus)
    paths=[locations['training']/'train.jsonl',locations['training']/'validation.jsonl',locations['evaluation']]
    datasets=[[json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()] for p in paths]
    train,val,test=datasets
    groups=[{r['scenario_group'] for r in ds} for ds in datasets]
    assert not(groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2])
    queries=[{r.get('query',r.get('question')).lower().strip() for r in ds} for ds in datasets]
    assert not(queries[0]&queries[1] or queries[0]&queries[2] or queries[1]&queries[2])
    model=SentenceTransformer(BASE_MODEL,device='cpu',revision=BASE_REVISION);model.max_seq_length=256
    optimizer=torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=.01)
    output=locations['model'];output.mkdir(parents=True,exist_ok=True)
    logs=[];best=float('inf');start=time.time()
    def loss(batch):
        embeddings=[]
        for key in ('query','positive','negative'):
            tokens=model.tokenize([r[key] for r in batch])
            embeddings.append(torch.nn.functional.normalize(model(tokens)['sentence_embedding'],dim=-1))
        a,p,n=embeddings
        return torch.relu(.25+(1-(a*p).sum(-1))-(1-(a*n).sum(-1))).mean()
    def validation():
        model.eval()
        with torch.no_grad(): return float(torch.stack([loss(val[i:i+8]) for i in range(0,len(val),8)]).mean())
    logs.append({'epoch':0,'validation_loss':validation()})
    for epoch in range(1,epochs+1):
        random.shuffle(train);model.train();losses=[]
        for i in range(0,len(train),8):
            optimizer.zero_grad();value=loss(train[i:i+8]);value.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step();losses.append(float(value.detach()))
        v=validation();record={'epoch':epoch,'train_loss':sum(losses)/len(losses),'validation_loss':v}
        logs.append(record);print(json.dumps(record),flush=True)
        if v<best:
            best=v;model.save(str(output));best_epoch=epoch
    manifest={'corpus':corpus,'base_model':BASE_MODEL,'base_revision':BASE_REVISION,'loss':'cosine triplet margin 0.25','seed':seed,'epochs':epochs,'batch_size':8,
        'learning_rate':lr,'weight_decay':.01,'max_seq_length':256,'device':'cpu','best_epoch':best_epoch,
        'training_seconds':time.time()-start,'sizes':dict(zip(['train','validation','test'],map(len,datasets))),
        'dataset_sha256':{str(p.relative_to(home)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'logs':logs,'limitations':['Small synthetic dataset','Train and validation are navigation/summary tasks; test uses complaint scenarios',
                                  'Shared policy corpus is intentional; no claim of unseen-policy generalization','No independent human annotation']}
    if corpus=='drip_r':
        manifest['original_benchmark_scenarios_in_training']=0
        manifest['limitations']+=['Training queries authored from DRIP-R policy text; not original scenario training',
          'Held-out DRIP-R scenarios share policy text; this is corpus adaptation, not unseen-policy generalization',
          'Original DRIP-R has no gold decision labels; results concern project retrieval annotations only']
    locations['reports'].mkdir(parents=True,exist_ok=True)
    (locations['reports']/'training_run.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'checkpoint':str(output),'best_epoch':best_epoch,'seconds':manifest['training_seconds']}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--home',type=Path,default=Path('.'));p.add_argument('--epochs',type=int,default=3)
    p.add_argument('--corpus',choices=CORPORA,default='novaretail')
    a=p.parse_args();main(a.home.resolve(),a.epochs,corpus=a.corpus)
