"""Policy-authored narratives; never reads DRIP-R scenario/private fields for examples."""
import json
from pathlib import Path
from claimguard.settings import ROOT, file_hash
from claimguard.datasets.drip_r import read_jsonl, write_jsonl
from claimguard.ingestion.pipeline import parse_with_sidecar
from claimguard.corpora import paths

# Independent authored situations, bilingual variants share one group.
# Labels are provisional relevance judgments, not refund/eligibility decisions.
DEV = [
 ('1.1', 'My kitchen scale was delivered 18 days ago. Before I send it back, I need the usual deadline and the conditions for receiving a refund.', 'Ma balance de cuisine a été livrée il y a 18 jours. Avant de la renvoyer, je cherche le délai habituel et les conditions du remboursement.'),
 ('1.8', 'I have returns from two different orders. Can I pack them together? One is a tablet with my photos still saved on it.', 'Je renvoie des articles de deux commandes différentes. Puis-je les mettre dans un seul colis ? Une tablette contient encore mes photos.'),
 ('1.5', 'The listing said final sale, but the lamp arrived broken. I am not returning it because I changed my mind. Who should I contact?', 'La lampe était en vente définitive, mais elle est arrivée cassée. Ce n’est pas un changement d’avis. Qui dois-je contacter ?'),
 ('1.12', 'I missed the return-by date by ten days. The product is intact. What late fee could apply?', 'J’ai dépassé de dix jours la date limite indiquée pour le renvoi. Le produit est intact. Quels frais de retard sont prévus ?'),
 ('1.15', 'My aunt gave me a present. I want a replacement and I have the packing slip. What order identifier do I need and how does a gift exchange work?', 'Ma tante m’a offert un cadeau. Je souhaite le remplacer et j’ai le bordereau. Quel numéro faut-il et comment procéder pour un échange ?'),
 ('1.20', 'I bought a discounted savings bundle of three items. I want to keep two. Is a partial bundle refund described?', 'J’ai acheté un lot promotionnel de trois articles et je veux en garder deux. Un remboursement partiel du lot est-il prévu ?'),
 ('1.13', 'My parcel weighs 62 pounds and I cannot carry it to a drop-off point. What collection arrangements and fees might apply?', 'Mon colis pèse 62 livres et je ne peux pas le porter au point de dépôt. Quelles modalités de collecte et quels frais sont prévus ?'),
 ('1.16', 'My purchase came from the Global Store and no prepaid label was offered. I paid 27 dollars to ship it back. What postage reimbursement and processing times are documented?', 'Mon achat vient du Global Store, sans étiquette prépayée. J’ai payé 27 dollars pour le renvoyer. Quels remboursements de port et délais sont documentés ?'),
 ('2.3', 'An independent seller ships its own orders. It offers neither a US return address nor a prepaid label. What return options must it offer?', 'Un vendeur indépendant expédie lui-même ses commandes. Il ne propose ni adresse de retour aux États-Unis ni étiquette prépayée. Quelles options doit-il offrir ?'),
 ('2.5', 'I am sending a 140-dollar purchase back to a marketplace seller. Do I need tracked, insured shipping or a signature?', 'Je renvoie un achat de 140 dollars à un vendeur de la marketplace. Faut-il un suivi, une assurance ou une signature ?'),
 ('1.18', 'I bought a used device and want to register its warranty. I am asking about manufacturer coverage, not the return window.', 'J’ai acheté un appareil d’occasion et je veux enregistrer sa garantie. Je cherche la couverture du fabricant, pas le délai de retour.'),
 ('1.19', 'I accidentally put my own headphones in a return parcel. What should I do, and is recovery or compensation guaranteed?', 'J’ai glissé par erreur mon casque personnel dans un colis de retour. Que faire, et sa récupération ou une indemnisation est-elle garantie ?'),
]

TRAIN = [
 ('1.1', 'A mixer was delivered last week and I no longer need it. Please locate the general return and refund requirements.', 'Un mixeur a été livré la semaine dernière et je n’en ai plus besoin. Je cherche les conditions générales de retour et de remboursement.'),
 ('1.2', 'I purchased an Apple accessory during the holiday shopping period in November 2025. Which seasonal deadline applies?', 'J’ai acheté un accessoire Apple pendant les achats de fêtes en novembre 2025. Quelle échéance saisonnière est prévue ?'),
 ('1.3', 'The refund was issued to my credit card yesterday but my balance has not changed. What processing delay is listed?', 'Le remboursement sur ma carte bancaire a été émis hier mais le solde n’a pas changé. Quel délai de traitement est indiqué ?'),
 ('1.6', 'I checked the conditions and want to submit my return request online. Where is the button in my account?', 'J’ai vérifié les conditions et je veux déposer une demande de retour en ligne. Où est le bouton dans mon compte ?'),
 ('1.7', 'A shop on the marketplace delivered my order itself. Should the return go to Amazon or to that merchant?', 'Une boutique de la marketplace a livré elle-même ma commande. Le retour va-t-il à Amazon ou au commerçant ?'),
 ('1.8', 'The return box contains an electronic reader. Should I erase my account and include all its cables and manuals?', 'Le colis à renvoyer contient une liseuse. Dois-je effacer mon compte et joindre les câbles et les manuels ?'),
 ('1.9', 'My prescription order was bought through Amazon Pharmacy. Can I send it back for a refund?', 'Mon ordonnance a été achetée via Amazon Pharmacy. Puis-je la renvoyer pour un remboursement ?'),
 ('1.10', 'Our office uses a business account and bought through Custom Quote Spot Buy. Which special terms should we consult?', 'Notre bureau utilise un compte professionnel et a acheté via Custom Quote Spot Buy. Quelles conditions particulières consulter ?'),
 ('1.11', 'There is a problem with a Luxury Stores purchase. Where is the dedicated assistance resource?', 'J’ai un problème avec un achat Luxury Stores. Où trouver l’assistance dédiée ?'),
 ('1.12', 'I damaged the product myself and removed some parts. What deductions could be made when it is returned?', 'J’ai moi-même endommagé le produit et retiré des pièces. Quelles retenues sont prévues lors du retour ?'),
 ('1.14', 'A discount depended on my purchasing several qualifying goods. I am returning one of them. How is the refund adjusted?', 'Une réduction dépendait de l’achat de plusieurs articles éligibles. J’en renvoie un. Comment le remboursement est-il ajusté ?'),
 ('1.15', 'I received a gift but cannot find its order number. How can I obtain the required reference?', 'J’ai reçu un cadeau mais je ne trouve pas son numéro de commande. Comment obtenir la référence nécessaire ?'),
 ('1.17', 'The delivery team is assembling my furniture under Deluxe Delivery and Assembly. Can I return it immediately at delivery?', 'L’équipe monte mon meuble avec Deluxe Delivery and Assembly. Puis-je le retourner immédiatement lors de la livraison ?'),
 ('1.20', 'My order was explicitly sold as a Bundle with Savings. Which items must be sent back to receive the refund?', 'Ma commande a été vendue comme Bundle with Savings. Quels articles faut-il renvoyer pour recevoir le remboursement ?'),
 ('1.21', 'Support asks for a government photo ID during return processing. Does the policy mention extra documentation?', 'L’assistance demande une pièce d’identité avec photo pendant le traitement du retour. La politique mentionne-t-elle des justificatifs supplémentaires ?'),
 ('2.4', 'My marketplace return is a partially assembled computer desk. How should I prepare and package it?', 'Mon retour marketplace est un bureau informatique partiellement monté. Comment le préparer et l’emballer ?'),
 ('2.6', 'The independent seller has received my parcel. When should I expect refund processing and are original shipping fees always returned?', 'Le vendeur indépendant a reçu mon colis. Quand doit-il traiter le remboursement, et le port initial est-il toujours remboursé ?'),
 ('2.7', 'A marketplace refund is delayed after I mailed the wrong model without tracking. What reasons for delay are documented?', 'Un remboursement marketplace tarde après l’envoi du mauvais modèle sans suivi. Quelles causes de retard sont documentées ?'),
 ('2.8', 'The merchant parcel is oversized. I need the marketplace-specific size limits and available return labels.', 'Le colis du commerçant est hors gabarit. Je cherche les limites de taille propres à la marketplace et les étiquettes possibles.'),
 ('2.9', 'The seller is unresponsive after my compliant return. When can I seek A-to-z assistance?', 'Le vendeur ne répond plus après mon retour conforme. Quand puis-je demander l’assistance A-to-z ?'),
]

MULTI = [
 (['1.1','1.8'], 'I want to return a router delivered two weeks ago. I need the standard deadline, the required accessories and instructions for erasing my saved settings.', 'Je veux renvoyer un routeur livré il y a deux semaines. Je cherche le délai habituel, les accessoires requis et les consignes pour effacer mes réglages.'),
 (['1.15','1.8'], 'I am returning a gift with its receipt and cable. How do I identify the gift order, and what packaging and accessories should I send?', 'Je renvoie un cadeau avec son reçu et son câble. Comment identifier la commande cadeau et quels emballages et accessoires renvoyer ?'),
 (['1.1','1.12','1.8'], 'My purchase arrived 45 days ago and I also missed the return-by date. Please find the normal return period, possible late fees and preparation requirements.', 'Mon achat est arrivé il y a 45 jours et j’ai aussi dépassé la date limite de renvoi. Je cherche le délai normal, les frais de retard possibles et les consignes de préparation.'),
 (['1.20','1.14'], 'A promotional discount applied to a Bundle with Savings. I would like to send part of it back. What rules govern bundle completeness and discount-adjusted refunds?', 'Une réduction promotionnelle concernait un Bundle with Savings. Je veux en renvoyer une partie. Quelles règles concernent le lot complet et l’ajustement du remboursement lié à la réduction ?'),
 (['1.13','1.8'], 'My heavy printer needs collection and contains my address book. Which bulky-item collection rules and data-removal instructions apply?', 'Mon imprimante lourde nécessite une collecte et contient mon carnet d’adresses. Quelles règles de collecte des articles lourds et d’effacement des données sont prévues ?'),
 (['2.3','2.5'], 'The seller handles its own shipments. Which approved return methods must it offer, and what insurance or signature is needed for my expensive parcel?', 'Le vendeur gère ses propres expéditions. Quelles options de retour doit-il proposer et quelle assurance ou signature prévoir pour mon colis de valeur ?'),
 (['2.6','2.9'], 'The merchant received my returned goods but has not refunded me and no longer responds. What is the usual seller refund timing and the A-to-z escalation route?', 'Le commerçant a reçu les articles renvoyés, ne me rembourse pas et ne répond plus. Quel délai de remboursement vendeur est prévu et quel recours A-to-z existe ?'),
 (['1.5','1.18'], 'My final-sale electronic device arrived defective. I need the customer-service exception and the separate manufacturer warranty guidance; I am not claiming guaranteed coverage.', 'Mon appareil électronique en vente définitive est arrivé défectueux. Je cherche l’exception orientant vers l’assistance et les indications distinctes sur la garantie fabricant, sans supposer une couverture garantie.'),
]


def prepare(home=ROOT):
    home = Path(home)
    sections = {}
    source_hashes = {}
    for p in paths(home, 'drip_r')['policies'].glob('*.txt'):
        _, chunks = parse_with_sidecar(p)
        source_hashes[p.name] = file_hash(p)
        for chunk in chunks:
            sections.setdefault(chunk.reference(), []).append(chunk.text)
    def ref(section):
        return f'DRIP-{1 if section.startswith("1.") else 2:03d}@1.0#{section}'
    development, training = [], []
    for index, (section, en, fr) in enumerate(DEV, 1):
        for lang, text in [('en', en), ('fr', fr)]:
            development.append({'question_id': f'DEV-{index:03d}-{lang}', 'scenario_group': f'authored-dev-{index:03d}',
                'question': text, 'language': lang, 'incident_date': '2026-11-02', 'relevant_sections': [ref(section)],
                'difficulty': 'multi_topic' if index in (2, 5, 8) else 'single_topic',
                'annotation_status': 'project_authored_needs_independent_review', 'source': 'policy-authored; no benchmark scenarios'})
    for index, (sections_expected,en,fr) in enumerate(MULTI,1):
        for lang,text in [('en',en),('fr',fr)]:
            development.append({'question_id':f'DEV-MULTI-{index:03d}-{lang}', 'scenario_group':f'authored-dev-multi-{index:03d}',
                'question':text, 'language':lang, 'incident_date':'2026-11-02',
                'relevant_sections':[ref(s) for s in sections_expected], 'difficulty':'multi_topic',
                'annotation_status':'project_authored_needs_independent_review', 'source':'policy-authored; no benchmark scenarios'})
    for index, (en, fr) in enumerate([
        ('How many loyalty points will this return earn?', 'Combien de points de fidélité ce retour rapporte-t-il ?'),
        ('Which employee salary deduction follows a customer complaint?', 'Quelle retenue sur salaire suit une réclamation client ?')], 1):
        for lang, text in [('en', en), ('fr', fr)]:
            development.append({'question_id': f'DEV-NA-{index}-{lang}', 'scenario_group': f'authored-dev-na-{index}',
                'question': text, 'language': lang, 'incident_date': '2026-11-02', 'relevant_sections': [],
                'difficulty': 'no_answer', 'annotation_status': 'project_authored_needs_independent_review'})
    for index, (section, en, fr) in enumerate(TRAIN, 1):
        for lang, query in [('en', en), ('fr', fr)]:
            training.append({'query': query, 'language': lang, 'scenario_group': f'authored-train-{index:03d}',
                'relevant_sections': [ref(section)], 'annotation_status': 'project_authored_needs_independent_review'})
    # Development variants stay together. No original DRIP-R situation is used for training.
    root = home / 'data/drip_r/development'
    write_jsonl(root / 'questions.jsonl', development)
    write_jsonl(root / 'training.jsonl', training)
    manifest = {'source_policy_sha256': source_hashes, 'original_drip_scenarios_used': 0,
                'languages': ['en', 'fr'], 'training_examples': len(training), 'development_examples': len(development),
                'test_sha256': file_hash(paths(home, 'drip_r')['evaluation']),
                'status': 'Synthetic relevance annotations; independent human review required; not refund decisions.'}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__': prepare()
