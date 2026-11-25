"""XML eCFR -> Document -> chunks, without Qdrant or models."""
from claimguard.cfpb import parse_regulation_xml
from claimguard.ingest import chunk_id, date_int, load_documents, split_documents

XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<DIV8 N="1026.13"><HEAD>\xc2\xa7 1026.13 Billing error resolution.</HEAD>
<P>(a) <I>Definition of billing error.</I> For purposes of this section, the term billing error means:</P>
<P>(1) A reflection on a periodic statement of an extension of credit that is not made to the consumer.</P>
<P>(b) <I>Billing error notice.</I> A billing error notice is a written notice received no later than 60 days after the first periodic statement.</P>
<P>(c) <I>Time for resolution.</I> (1) The creditor shall mail written acknowledgment within 30 days.</P>
<P>(i) The creditor shall resolve the dispute within two complete billing cycles.</P>
<CITA>[76 FR 79772, Dec. 22, 2011]</CITA></DIV8>'''


def test_xml_paragraphs_keep_official_text():
    parsed = parse_regulation_xml(XML)
    assert [s['section'] for s in parsed['sections']] == ['a', 'b', 'c']  # roman (i) stays inside (c)
    assert parsed['lines'][0] == '§ 1026.13 Billing error resolution.'
    assert 'no later than 60 days' in parsed['lines'][3]
    assert parsed['lines'][-1] == 'Source: 76 FR 79772, Dec. 22, 2011'


def test_real_corpus_documents_and_stable_ids():
    documents = load_documents()
    assert len({d.metadata['source'] for d in documents}) == 11
    first = split_documents(documents, 1000, 100)
    second = split_documents(load_documents(), 1000, 100)
    assert [c.id for c in first] == [c.id for c in second]
    assert len({c.id for c in first}) == len(first)
    assert all(len(c.page_content) <= 1000 for c in first)
    for chunk in first[:20]:
        paragraph = next(d for d in documents if d.metadata['reference'] == chunk.metadata['reference'])
        start = chunk.metadata['start_index']
        assert paragraph.page_content[start:start + len(chunk.page_content)] == chunk.page_content
    assert chunk_id(first[0]) == first[0].id


def test_version_dates_are_filterable_integers():
    assert date_int('2019-04-01') == 20190401
    assert date_int(None) == 99991231
    versions = [d.metadata for d in load_documents() if d.metadata['policy_id'] == 'REGZ-013']
    assert {(m['version'], m['version_date'], m['valid_until']) for m in versions} == {
        ('1.0', '2018-02-13', '2019-04-01'), ('2.0', '2019-04-01', None)}
