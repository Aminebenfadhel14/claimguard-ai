from claimguard.models import Hit

def rrf(rankings: list[list[Hit]], k=60):
    if k < 1: raise ValueError('RRF k must be positive')
    scores, chunks = {}, {}
    for ranking in rankings:
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            cid = hit.chunk.chunk_id
            if cid in seen: continue
            seen.add(cid)
            scores[cid] = scores.get(cid,0.0) + 1/(k+rank)
            chunks[cid] = hit.chunk
    return [Hit(chunk=chunks[cid],score=scores[cid],stage='rrf')
            for cid in sorted(scores,key=lambda x:(-scores[x],x))]
