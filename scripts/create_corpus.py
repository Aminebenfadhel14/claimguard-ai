"""Authored fictional corpus, with explicit source and machine-checkable reference annotations."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# Each tuple: policy id, title, category, department, three sections with held-out questions.
POLICIES=[
('RETURN-001','Returns and Exchanges','returns','Customer Service',[
('4.2','Defective product exchange','Defective products may be exchanged within 14 calendar days of purchase, subject to proof of purchase and verification of the product condition. Accidental damage and customer misuse are excluded. If eligibility is uncertain, request inspection; do not promise an exchange.',
 ['My phone arrived faulty and I bought it four days ago. What must be checked for an exchange?','Does a broken screen caused by dropping my phone qualify for a defect exchange?']),
('4.3','Change of mind','Unused products in original packaging may be returned within 14 calendar days of purchase with proof of purchase. Opened hygiene accessories and activated digital licences are excluded. This section does not override verified defect claims under section 4.2.',
 ['I changed my mind about unopened headphones purchased last week. What are the conditions?','Can I return an activated software licence just because I dislike it?']),
('4.4','Exchange stock unavailable','When an eligible defect exchange cannot be completed because the same product is out of stock, offer the customer a refund review under REFUND-001 section 3.1. Do not impose store credit without customer agreement.',
 ['The identical replacement device is unavailable. Can the shop force store credit?','What is the next step when an eligible replacement is out of stock?'])]),
('REFUND-001','Refund Policy','refunds','Finance',[
('3.1','Refund authorization','Refunds require an approved return, a duplicate payment verified by Finance, or a confirmed lost delivery. An agent proposes the refund; an authorized reviewer approves it. A complaint alone is not approval.',
 ['Does submitting a complaint automatically authorize my refund?','Who must approve reimbursement after a duplicate payment is verified?']),
('3.2','Refund processing','After approval, Finance initiates the refund to the original payment method within 5 business days. Bank processing may take additional time; do not guarantee a bank settlement date. Send a transaction reference after initiation.',
 ['My refund has been approved. When should Finance initiate it?','Can an agent guarantee exactly when my bank will show the money?']),
('3.3','Partial refund consent','A partial refund or store credit requires documented customer consent and supervisor approval. Never substitute a voucher for an approved monetary refund without consent.',
 ['Can the company replace my approved cash refund with a voucher without asking?','What approvals are needed before issuing a partial reimbursement?'])]),
('WARRANTY-001','Warranty Policy','warranty','Technical Support',[
('2.1','Warranty duration','NovaRetail commercial warranty lasts 12 months from purchase for manufacturing defects. Require proof of purchase and product serial number. This fictional commercial policy makes no statement about statutory consumer rights.',
 ['My device has a manufacturing problem eight months after purchase. Which documents are required?','How long does the NovaRetail commercial warranty last?']),
('2.2','Warranty exclusions','Commercial warranty excludes accidental impact, liquid damage and unauthorized repairs when they cause the failure. A technician must document the causal finding; an agent must not infer misuse solely from an allegation.',
 ['The technician suspects liquid damage but has not inspected the tablet. Can misuse be assumed?','Is a failure caused by an unauthorized repair covered by the commercial warranty?']),
('2.3','Repair delay','If an accepted warranty repair exceeds 20 business days after workshop receipt, escalate to the technical supervisor for an alternative resolution review. No automatic refund is implied by this delay.',
 ['My accepted repair has been in the workshop for 23 business days. What happens next?','Does a repair delay automatically mean I am entitled to a refund?'])]),
('DELIVERY-001','Delivery Policy','delivery','Logistics',[
('5.1','Missed delivery estimate','A delivery estimate is not proof of delivery. When the estimate is missed, verify the tracking record and open a carrier investigation. Give the customer the next update within 2 business days.',
 ['My package missed the estimated date. When should I receive an update?','Is the estimated delivery date enough to prove a parcel was delivered?']),
('5.2','Lost shipment','A shipment is confirmed lost only after carrier investigation and logistics validation. Offer replacement or refund review after confirmation. A delivered scan disputed by the customer requires investigation, not immediate rejection.',
 ['Tracking says delivered but I received nothing. Should the complaint be rejected?','Can a lost-parcel refund be proposed before logistics validates the investigation?']),
('5.3','Transport damage','For suspected transport damage, request photos of the packaging and product and record the delivery date. Keep the claim open while evidence is collected. Do not ask the customer to operate a visibly unsafe device.',
 ['The delivered monitor and its box are damaged. Which evidence is needed?','Should I switch on a visibly damaged and unsafe device to prove delivery damage?'])]),
('BILLING-001','Billing Policy','billing','Finance',[
('6.1','Duplicate charge','For a suspected duplicate charge, Finance compares order ID, payment references, amounts and settlement records. A pending authorization is not necessarily a settled duplicate. Mask payment account details.',
 ['Two charges appear but one is pending. Is that already a proven duplicate payment?','Which records should Finance compare for a suspected double charge?']),
('6.2','Invoice correction','Correct verified invoice errors through a traceable replacement invoice or credit note. Preserve the original record. Never alter settled transaction history silently.',
 ['The invoice contains a verified error. Should the original document be deleted?','How should a corrected invoice preserve an audit trail?']),
('6.3','Promotional price dispute','Verify the dated promotion, eligible product, channel and stated exclusions before deciding a price dispute. An expired promotion does not automatically apply to a later purchase. Escalate ambiguous advertising to a supervisor.',
 ['I bought a laptop after the sale ended. Must the old promotion automatically apply?','What evidence is needed to investigate a disputed advertised price?'])]),
('SERVICE-001','Customer Service Policy','service','Customer Service',[
('1.1','Acknowledgement','Acknowledge new complaints within 1 business day. Acknowledge the reported experience without presenting unverified allegations as established facts.',
 ['How soon must a new complaint be acknowledged?','Can the acknowledgement state that an employee definitely caused the reported problem?']),
('1.2','Accessible communication','Offer clear communication in French or English according to customer preference. Explain required evidence in plain language and offer an accessible contact channel when requested.',
 ['May I ask for complaint updates in French?','How should an agent explain the documents needed to a customer who needs an accessible channel?']),
('1.3','Status updates','While an investigation is open, provide a status update at least every 3 business days, including the next step and any missing evidence. Do not invent completion dates.',
 ['How often should customers hear about an ongoing investigation?','May the agent invent a completion date to reassure the customer?'])]),
('CONDUCT-001','Employee Conduct Policy','conduct','Human Resources',[
('7.1','Respectful treatment','Employees must treat customers respectfully and must not insult, threaten or discriminate. Record reported misconduct as an allegation until reviewed with available evidence. Refer alleged misconduct to a supervisor.',
 ['A salesperson insulted me while refusing an exchange. How is the conduct allegation treated?','Does a customer allegation alone establish that an employee breached conduct rules?']),
('7.2','Fair investigation','A supervisor reviews customer statements, employee accounts and lawfully available records. Limit access to the investigation team. Do not issue automatic disciplinary findings from AI output.',
 ['Can the AI automatically recommend a disciplinary finding against the employee?','Who may see the internal misconduct investigation evidence?']),
('7.3','Confidential personnel outcomes','Tell the customer the service resolution and next steps without disclosing confidential personnel sanctions. Personnel decisions remain with authorized human reviewers.',
 ['Can customer support disclose the exact disciplinary sanction against an employee?','Who makes personnel decisions after a conduct investigation?'])]),
('SAFETY-001','Security and Safety Policy','safety','Safety',[
('8.1','Unsafe battery','For smoke, overheating with swelling, or a suspected battery fire, advise the customer to stop using and charging the device and contact appropriate emergency services if there is immediate danger. Escalate immediately to the safety team. Do not request a powered-on demonstration.',
 ['My phone battery is swollen and smoking. Should I keep charging it for a diagnostic?','Who receives an urgent complaint about a potential battery fire?']),
('8.2','Recall check','Verify product model and serial number against the current authorized recall register. This document does not list recalled models. Do not declare a model recalled without a register entry.',
 ['Can this policy alone prove that my specific model has been recalled?','Which identifiers are needed for a product recall check?']),
('8.3','Suspected account compromise','For suspected unauthorized account access, route to Security, use the approved identity verification channel and never request passwords or full payment card numbers in complaint text.',
 ['Support asked for my account password after a suspected breach. Is that an approved step?','Where should an allegation of unauthorized account access be routed?'])]),
('ESCALATE-001','Complaint Escalation Policy','escalation','Operations',[
('9.1','Urgent escalation','Immediately escalate safety threats to Safety and suspected data exposure to Privacy and Security. Escalation is a review action, not proof of a breach or a promise of compensation.',
 ['Where should a suspected customer-data exposure be escalated?','Does escalation establish that a data breach actually happened?']),
('9.2','Unresolved complaint','Escalate a complaint unresolved after 5 business days to a customer service supervisor. Include the timeline, evidence, attempted actions and unresolved questions.',
 ['My complaint has remained unresolved for six business days. Who reviews it next?','What information belongs in an unresolved-complaint escalation?']),
('9.3','Human decision','An authorized employee records the final service decision, rationale and policy version used. AI outputs remain advisory. Never send a customer response or execute a refund solely on an AI recommendation.',
 ['Can an AI recommendation directly trigger a payment refund?','What must a human reviewer record when deciding a complaint?'])]),
('PRIVACY-001','Privacy Policy','privacy','Privacy',[
('10.1','Data minimization','Collect only evidence necessary for the complaint. Mask payment numbers and remove unnecessary personal identifiers from analysis copies. Do not request passwords.',
 ['Should all personal identifiers be included in the AI analysis copy?','Is requesting a password acceptable as complaint evidence?']),
('10.2','Access and retention','Restrict complaint records to authorized staff assigned to the case. Retain closed complaint records for 180 days unless a documented legal hold applies, then delete or irreversibly anonymize according to the retention process.',
 ['How long are closed complaints retained when no legal hold exists?','Can any employee browse complaint records belonging to another team?']),
('10.3','Privacy requests','Route access or deletion requests to the Privacy team for identity verification and applicable obligation review. Do not promise immediate deletion before checking retention obligations and legal holds.',
 ['Can support promise immediate erasure without checking a legal hold?','Which team handles a customer request to access their personal data?'])])]

def main():
    policies=ROOT/'data/policies'; policies.mkdir(parents=True,exist_ok=True)
    evaluation=[]; train=[]; validation=[]; sections=[]
    for pid,title,category,department,items in POLICIES:
        meta=dict(document_id=pid+'-V2' if pid=='RETURN-001' else pid+'-V1',policy_id=pid,title=title,
                  category=category,department=department,version='2.0' if pid=='RETURN-001' else '1.0',
                  effective_date='2026-01-01',effective_until=None,language='en',access_level='internal',
                  source='NovaRetail fictional academic corpus; authored for ClaimGuard AI, not real legal policy')
        text=f'# {title}\n\nFictional academic policy — NovaRetail. Version {meta["version"]}.\n\n'
        for section,heading,body,questions in items:
            text+=f'## {section} — {heading}\n{body}\n\n'
            ref=f'{pid}@{meta["version"]}#{section}'
            sections.append((ref,heading,body))
            for question in questions:
                evaluation.append(dict(question_id=f'Q{len(evaluation)+1:03}',question=question,category=category,
                    relevant_sections=[ref],reference_answer=body,references=[{'policy_id':pid,'version':meta['version'],'section':section,'page':1}],
                    difficulty='exception' if len(evaluation)%2 else 'simple',incident_date='2026-11-02',
                    scenario_group=f'test-{ref}-{len(evaluation)}',annotation_status='author_reviewed_synthetic'))
        p=policies/(pid+'_'+meta['version']+'.md');p.write_text(text,encoding='utf-8')
        p.with_suffix('.md.json').write_text(json.dumps(meta,indent=2))
        if pid=='RETURN-001':
            old=meta|{'version':'1.0','document_id':pid+'-V1','effective_date':'2025-01-01','effective_until':'2026-01-01'}
            p=policies/(pid+'_1.0.md');p.write_text(text.replace('Version 2.0','Version 1.0').replace('14 calendar days','7 calendar days'),encoding='utf-8')
            p.with_suffix('.md.json').write_text(json.dumps(old,indent=2))
    extra=[
      ('A defective device was refused for exchange and the employee insulted me. Which rules need review?', ['RETURN-001@2.0#4.2','CONDUCT-001@1.0#7.1'],'multi'),
      ('How do the deadlines for acknowledging a complaint and updating an open case differ?', ['SERVICE-001@1.0#1.1','SERVICE-001@1.0#1.3'],'comparison'),
      ('What is the difference between the 14-day defect exchange window and the commercial warranty?', ['RETURN-001@2.0#4.2','WARRANTY-001@1.0#2.1'],'comparison'),
      ('What evidence confirms a duplicate charge, and who approves the resulting refund?', ['BILLING-001@1.0#6.1','REFUND-001@1.0#3.1'],'multi'),
      ('My replacement is out of stock. Can I be forced to accept a voucher instead of the approved refund?', ['RETURN-001@2.0#4.4','REFUND-001@1.0#3.3'],'multi'),
      ('What is the exchange window for a defective phone bought during November 2025?', ['RETURN-001@1.0#4.2'],'historical'),
      ('What is the exchange window for a defective phone bought during November 2026?', ['RETURN-001@2.0#4.2'],'temporal'),
      ('Quel est le délai pour un échange de produit défectueux et quelles preuves faut-il ?', ['RETURN-001@2.0#4.2'],'french')]
    lookup={r:b for r,h,b in sections}
    lookup['RETURN-001@1.0#4.2']=lookup['RETURN-001@2.0#4.2'].replace('14 calendar days','7 calendar days')
    for q,refs,kind in extra:
        evaluation.append(dict(question_id=f'Q{len(evaluation)+1:03}',question=q,category='mixed',relevant_sections=refs,
            reference_answer='\n'.join(lookup[r] for r in refs),references=refs,difficulty=kind,
            incident_date='2025-11-15' if kind=='historical' else '2026-11-02',scenario_group=f'test-extra-{len(evaluation)}',annotation_status='author_reviewed_synthetic'))
    for q in ['What is NovaRetail annual revenue?','What is the CEO private telephone number?',
              'What interest rate applies to a mortgage?', 'What exact amount of compensation will I receive?',
              'Is smartphone model NR-X9 currently recalled?', 'Which employee is guilty in my complaint?',
              'What is the customer account password?', 'What is the statutory return period under Tunisian law?']:
        evaluation.append(dict(question_id=f'Q{len(evaluation)+1:03}',question=q,category='unsupported',relevant_sections=[],
            reference_answer='Insufficient evidence; the corpus does not provide the requested determination.',references=[],
            difficulty='no_answer',incident_date='2026-11-02',scenario_group=f'test-unknown-{len(evaluation)}',annotation_status='author_reviewed_synthetic'))
    for i,(ref,heading,body) in enumerate(sections):
        negative=sections[(i+3)%len(sections)][2]
        for j,q in enumerate([f'Find the internal rule for {heading.lower()}.',f'I need staff guidance about {heading.lower()}.']):
            train.append(dict(query=q,positive=body,negative=negative,reference=ref,scenario_group=f'train-navigation-{i}-{j}'))
        validation.append(dict(query=f'Summarize NovaRetail requirements concerning {heading.lower()}.',positive=body,
                               negative=negative,reference=ref,scenario_group=f'validation-summary-{i}'))
    for name,rows,folder in [('questions',evaluation,'evaluation'),('train',train,'synthetic'),('validation',validation,'synthetic')]:
        (ROOT/f'data/{folder}/{name}.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
    print(json.dumps({'policy_versions':11,'sections_current':len(sections),'evaluation_questions':len(evaluation),'train':len(train),'validation':len(validation)}))
if __name__=='__main__':main()
