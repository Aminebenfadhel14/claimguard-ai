import math

def metrics(ranked, relevant):
    # Evaluate sections, not duplicate chunks from the same section.
    ranked=list(dict.fromkeys(ranked)); relevant=set(relevant)
    if not relevant: raise ValueError('Unanswerable questions require separate abstention evaluation')
    result={}
    for k in (1,3,5,10):
        result[f'recall@{k}']=len(set(ranked[:k]) & relevant)/len(relevant)
        result[f'precision@{k}']=len(set(ranked[:k]) & relevant)/k
    result['mrr@10']=next((1/r for r,s in enumerate(ranked[:10],1) if s in relevant),0.)
    dcg=sum(1/math.log2(i+2) for i,s in enumerate(ranked[:10]) if s in relevant)
    ideal=sum(1/math.log2(i+2) for i in range(min(10,len(relevant))))
    result['ndcg@10']=dcg/ideal
    return result
