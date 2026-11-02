"""Project-authored retrieval labels, frozen before experiments; NOT DRIP-R gold decisions.
No private simulator fields are used in queries. Original cases remain evaluation-only.
"""
import hashlib
import json
from pathlib import Path
from claimguard.datasets.drip_r import read_jsonl, write_jsonl, evaluation_sample, query_for

# Explicit source-section judgments after reading the 50 selected visible requests.
# These labels are provisional, model-authored, and require independent human review.
RELEVANT = [
 ['1.1','1.8'], ['1.1','1.8'], ['1.1','1.8'], ['1.1','1.6','1.8'], ['1.1','1.8'],
 ['1.8','1.13','2.9'], ['1.1','1.8','2.8'], ['1.1','1.8','1.14','1.20'], ['1.15','1.8'], ['1.8'],
 ['1.15','1.8'], ['1.8'], ['1.15','1.8','1.1'], ['1.15','1.8','1.1'], ['1.15','1.8','1.11'],
 ['1.8','1.7'], ['1.8','1.1'], ['1.1','1.8'], ['1.1','1.8'], ['1.1','1.8'],
 ['1.1','1.8'], ['1.13','1.8','1.1'], ['1.20','1.8'], ['1.8','1.1'], ['1.8','1.1'],
 ['1.8','1.1'], ['1.1','1.8'], ['1.14','1.20','1.8'], ['1.8','1.1'], ['1.1','1.6'],
 ['1.1','1.8'], ['1.12','1.8'], ['1.14','1.8'], ['1.8','1.1'], ['1.5','1.8','1.1'],
 ['1.8'], ['1.15','1.8'], ['1.1','1.8'], ['1.1','1.8'], ['1.1','1.8'],
 ['1.1','1.8'], ['1.1','1.8'], ['1.1','1.8'], ['1.6','1.8'], ['1.1','1.8'],
 ['1.13','1.8'], ['1.1','1.8'], ['1.1','1.8'], ['1.15','1.8'], ['1.8'],
]

# Three independently worded navigation questions per section: 2 train, 1 validation.
# They are authored for this project from policy text, not copied from benchmark scenarios.
POLICY_QUERIES = {
 '1.1': ['What general eligibility conditions govern an ordinary return?', 'When is a refund released after a returned purchase?', 'Explain the usual delivery-based deadline and the requirement to inspect returned goods.'],
 '1.2': ['Which seasonal extension applies to purchases made in November 2025?', 'What is the special holiday return deadline for Apple-branded goods?', 'How do holiday deadlines differ for Apple and other products?'],
 '1.3': ['How long does a credit-card refund take after it is issued?', 'Which refund method receives funds within hours?', 'Compare the financial processing times for gift cards and prepaid cards.'],
 '1.4': ['Where does the document list exceptions to the standard return period?', 'Which section lists alternative return windows without product mappings?', 'Does the return-window exception table identify which goods have 90 days?'],
 '1.5': ['Can final-sale merchandise normally be returned?', 'How should a defective non-returnable product be handled?', 'Where can I find excluded product types and the damaged-final-sale exception?'],
 '1.6': ['Where in my account can I initiate an eligible return?', 'How do I start a return request from my orders?', 'What button begins the return workflow?'],
 '1.7': ['Where is a seller-fulfilled purchase sent back?', 'Which three return arrangements must an independent seller offer?', 'Does a marketplace merchant have to accept a return at an American address?'],
 '1.8': ['What packaging and accessories should accompany a return?', 'May articles from different orders share a return package?', 'Which preparation and personal-data removal steps apply before shipping an electronic item back?'],
 '1.9': ['Are purchases from the pharmacy refundable?', 'Where does the policy direct pharmacy customers needing assistance?', 'Identify the separate restriction for Amazon Pharmacy purchases.'],
 '1.10': ['Does the retail return policy cover business accounts?', 'Where are special business purchasing program rules documented?', 'Which terms apply to a Custom Quote Spot Buy?'],
 '1.11': ['Where should I seek help for a Luxury Stores purchase?', 'Which section redirects customers with luxury-store return issues?', 'Identify the help resource for the Luxury Stores range.'],
 '1.12': ['What fee can follow a return after the stated return-by date?', 'What deductions can apply when returned goods show user-caused damage?', 'How do late-return fees compare during and after the first thirty days?'],
 '1.13': ['How does the main policy define a bulky item?', 'Can a large-item return require a specialty carrier collection?', 'Which weight and dimension thresholds govern standard heavy-item returns?'],
 '1.14': ['How is a discount-adjusted purchase refunded?', 'What happens to an offer when I return a qualifying discounted item?', 'Which rule reduces the refund to account for a discount qualification?'],
 '1.15': ['What reference number is needed to return a gift?', 'Can a gift be directly exchanged or must a new order be placed?', 'How should a gift recipient locate the order identifier?'],
 '1.16': ['Who pays postage for eligible Global Store returns?', 'What transit and refund times apply to Global Store merchandise?', 'How much international return postage is reimbursed automatically?'],
 '1.17': ['Which premium delivery services permit an instant return?', 'Can an item be returned at delivery when assembly was included?', 'Where are rules for Deluxe Delivery and Unpack described?'],
 '1.18': ['Who can provide manufacturer warranty coverage information?', 'Do used goods necessarily have manufacturer warranty coverage?', 'Where should product registration and warranty inquiries go?'],
 '1.19': ['What should I do if I mailed back the wrong item?', 'Does the policy guarantee compensation for an accidental extra item?', 'Can support guarantee recovery of goods mistakenly included in a return?'],
 '1.20': ['Can part of a Bundle with Savings receive a refund?', 'Must every item in a savings bundle be sent back?', 'What requirement governs refunds of Bundle with Savings purchases?'],
 '1.21': ['Can documentation be requested to verify a refund?', 'What measures may be taken when the return service is abused?', 'Does the return policy allow further identity evidence to be requested?'],
 '2.1': ['Who receives a return for a merchant that ships its own stock?', 'How does the seller-fulfilled return destination differ?', 'Where do third-party fulfilled items go when sent back?'],
 '2.2': ['Which online center starts a marketplace return?', 'How can I request a third-party seller return through Amazon?', 'Identify the entry point for a merchant return request.'],
 '2.3': ['What return methods should the seller provide?', 'Can a seller offer a refund without asking for the product?', 'Which choices meet the marketplace seller return-method requirement?'],
 '2.4': ['How should an assembled item be packed for a seller return?', 'Which personal information should be removed before returning to a merchant?', 'What are the marketplace packing and disassembly instructions?'],
 '2.5': ['When is insurance and a signature needed for a seller shipment?', 'How should I ship a return worth more than 35 dollars?', 'Can refusing delivery jeopardize A-to-z coverage?'],
 '2.6': ['How quickly does a seller normally process a received return?', 'Are original shipping charges always refunded by a merchant?', 'When should a seller issue a refund notification?'],
 '2.7': ['Which circumstances can delay a seller refund?', 'Does untracked shipping increase refund delays?', 'Why might returning a different item prevent prompt refund processing?'],
 '2.8': ['How are extra-large seller return parcels defined?', 'Which shipping labels can be offered for oversized merchant returns?', 'What weight and girth limits classify a third-party return as extra large?'],
 '2.9': ['When can I ask for A-to-z assistance with a nonresponsive seller?', 'What if a seller does not offer an approved damaged-item return method?', 'What follow-up is available when a compliant seller return has not been refunded?'],
}

def build(home):
    home=Path(home); root=home/'data/drip_r'; sections={}
    for p in sorted((root/'policies').glob('*.txt')):
        lines=p.read_text(encoding='utf-8').splitlines(keepends=True)
        for s in json.loads(p.with_suffix('.txt.sections.json').read_text(encoding='utf-8'))['sections']:
            sections[s['section']]={'reference': f'{p.stem}@1.0#{s["section"]}',
                'text': ''.join(lines[s['start_line']-1:s['end_line']]).strip(),
                'source_file':p.name, **s}
    rows=read_jsonl(home/'data/external/drip_r/scenarios.jsonl'); selected=evaluation_sample(rows)
    questions=[]
    for i,(r,refs) in enumerate(zip(selected,RELEVANT),1):
        citations=[sections[s] for s in refs]
        questions.append({'question_id':f'DRIP-Q{i:03d}', 'scenario_id':r['scenario_id'],
            'scenario_group':r['task_id'], 'question':query_for(r), 'category':'returns',
            'incident_date':'2026-11-02', 'date_basis':'technical snapshot query only; incident date unknown',
            'relevant_sections':[s['reference'] for s in citations],
            'reference_answer': 'Retrieve the cited provisions; check missing facts and exceptions before any recommendation. '
              'These passages support investigation, not an automatic eligibility or compliance verdict.',
            'reference_extracts':citations, 'difficulty':'multi_topic' if len(refs)>1 else 'single_topic',
            'annotation_status':'project_model_authored_needs_independent_review',
            'annotation_scope':'relevance to visible message and agent brief only; not a gold decision'})
    no_answer=[
        'What disciplinary penalty should a rude employee receive?',
        'What is the compensation amount for a delivery driver who insulted a customer?',
        'What is NovaRetail policy RETURN-001 section 4.2?',
        'What is the customer call recording retention period?',
        'Is this exact customer eligible for a guaranteed refund before inspection?',
        'What was the applicable return policy version on 1 January 2018?',
        'Which product categories correspond to each blank row of the return-window exception table?',
        'What are all the product types omitted after the restocking fee table heading?']
    for i,q in enumerate(no_answer,1):
        questions.append({'question_id':f'DRIP-NA{i:02d}','scenario_group':f'project-noanswer-{i}',
            'question':q,'category':'no_answer','incident_date':'2026-11-02','relevant_sections':[],
            'reference_answer':'The snapshot does not provide enough evidence to answer. State what is missing.',
            'difficulty':'no_answer','annotation_status':'project_model_authored_needs_independent_review',
            'source':'project-authored challenge, not an original DRIP-R scenario'})
    write_jsonl(root/'evaluation/questions.jsonl',questions)
    train=[]; validation=[]
    for i,(section,qs) in enumerate(POLICY_QUERIES.items()):
        # Explicit negative from another section; some near synonyms may remain false negatives.
        negative=list(POLICY_QUERIES)[(i+7)%len(POLICY_QUERIES)]
        for j,q in enumerate(qs):
            example={'query':q,'positive':sections[section]['text'],'negative':sections[negative]['text'],
                'positive_reference':sections[section]['reference'],
                'negative_reference':sections[negative]['reference'],
                'scenario_group':f'project-policy-{section}-{j}',
                'source':'project-authored from policy snapshot; excludes all original DRIP-R scenarios',
                'annotation_status':'model_authored_needs_review'}
            (train if j<2 else validation).append(example)
    write_jsonl(root/'training/train.jsonl',train);write_jsonl(root/'training/validation.jsonl',validation)
    manifest={'created_before_training':True,'method':'Explicit project-authored judgments on visible requests',
        'original_scenarios':len(selected),'task_groups':len({r['task_id'] for r in selected}),
        'personas':len({r['persona']['Persona_id'] for r in selected}), 'project_no_answer':len(no_answer),
        'train_policy_questions':len(train),'validation_policy_questions':len(validation),
        'benchmark_cases_used_for_training':0,'independent_human_review':False,
        'test_sha256':hashlib.sha256((root/'evaluation/questions.jsonl').read_bytes()).hexdigest(),
        'limitations':['No gold compliance labels; metrics concern retrieval only',
           'Small corpus of 2 policies / 30 local sections, many queries share general rules',
           '50 scenarios represent 40 tasks, not 50 independent problems',
           'Train/validation use the same policy corpus but separate authored questions',
           'Partial answers are allowed: missing live order facts must remain unknown']}
    (home/'reports/drip_r/annotation_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': build(Path(__file__).resolve().parents[1])
