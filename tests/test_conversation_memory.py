import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from conversation_memory import EvidenceMemory, memory_messages, context_interpretation, persist_memory
from memory_support import make_support


def row(text, answer='请说明你准备怎样做。', status='success'):
    return {'text':text,'support':{'text':answer,'status':status}}


class MemoryTests(unittest.TestCase):
    def test_sources_and_roles(self):
        m=EvidenceMemory.from_records([row('解方程3x+4=19，我已得到3x=15。','请核对两边的运算。')],'两边同时除以5')
        self.assertFalse(m.validate())
        self.assertEqual(m.view()['latest_student']['text'],'两边同时除以5')
        self.assertTrue(all(n['role']=='student' for n in m.view()['student_contributions']))

    def test_idempotent_and_conflicting_event(self):
        m=EvidenceMemory();m.ingest('解方程3x=15','student',1)
        m.ingest('解方程3x=15','student',1)
        self.assertEqual(len(m.events),1)
        with self.assertRaises(ValueError):m.ingest('解方程3x=16','student',1)

    def test_failed_support_not_delivered(self):
        m=EvidenceMemory.from_records([row('解方程3x=15','x=5','network_error')],'为什么')
        self.assertIsNone(m.view()['latest_support'])

    def test_ack_does_not_establish_mastery(self):
        m=EvidenceMemory.from_records([row('解方程3x=15')],'好的')
        self.assertEqual(m.view()['mastery'],'not_inferred')
        self.assertEqual(m.view()['student_contributions'],[])
        self.assertEqual(context_interpretation(m,'好的')['kind'],'acknowledgement')

    def test_ack_with_followup_not_ack(self):
        m=EvidenceMemory.from_records([row('解方程3x=15')],'好的，但为什么要除以3？')
        self.assertEqual(m.view()['latest_student']['text'],'好的，但为什么要除以3？')

    def test_wrong_step_is_still_student_contribution(self):
        m=EvidenceMemory.from_records([row('解方程3x=15')],'我算出x=3，对吗？')
        self.assertTrue(m.view()['student_contributions'])
        self.assertEqual(m.view()['student_contributions'][-1]['status'],'reported_not_verified')

    def test_quoted_assistant_not_independent(self):
        m=EvidenceMemory.from_records([row('解方程3x=15','x=5')],'你刚才说x=5，对吗？')
        self.assertFalse(m.view()['student_contributions'])
        self.assertTrue(m.view()['quoted_support'])

    def test_literal_equation_copy_conservative(self):
        m=EvidenceMemory.from_records([row('解方程3x=15','x=5')],'x=5，对吗？')
        self.assertTrue(m.view()['quoted_support'])

    def test_switch_and_return(self):
        records=[row('解方程3x+4=19，我已得到3x=15。'),row('换一道题，解方程2y+1=9，我想先减1。')]
        m=EvidenceMemory.from_records(records,'回到上一题，刚才为什么要减4？')
        self.assertIn('3x+4=19',m.view()['active_problem']['text'])
        self.assertFalse(any('2y' in n['text'] for n in m.view()['student_contributions']))
        text,_=memory_messages(m,records,'回到上一题，刚才为什么要减4？')
        self.assertNotIn('2y',text)

    def test_unknown_return_not_silently_previous(self):
        m=EvidenceMemory.from_records([], '回到第5题，为什么？')
        self.assertIsNone(m.view()['active_problem'])
        self.assertTrue(m.flags)

    def test_revision_preserves_original(self):
        records=[row('解方程3x=15'),row('我算出x=3')]
        m=EvidenceMemory.from_records(records,'刚才算错了，改成x=5，对吗？')
        old=next(n for n in m.nodes if n['text']=='我算出x=3')
        self.assertFalse(old['active'])
        self.assertIn('我算出x=3',[e['text'] for e in m.events])
        self.assertTrue(any(e['relation']=='explicit_revision' for e in m.edges))

    def test_explicit_new_problem_without_switch_word(self):
        m=EvidenceMemory.from_records([row('解方程3x=15')],'解方程2y=8，可以给提示吗？')
        self.assertIn('2y=8',m.view()['active_problem']['text'])

    def test_tampered_source_detected(self):
        m=EvidenceMemory.from_records([], '解方程3x=15')
        m.nodes[-1]['evidence']['quote']='杜撰'
        self.assertTrue(m.validate())

    def test_budget_is_character_cap(self):
        r=[row('解方程3x=15')]+[row('我想'+str(i)+'，'+('这是长句'*50)) for i in range(15)]
        m=EvidenceMemory.from_records(r,'为什么')
        for mode in ('recent','summary','graph'):
            text,meta=memory_messages(m,r,'为什么',mode,800)
            self.assertLessEqual(len(text),800)
            self.assertEqual(meta['construction_api_calls'],0)

    def test_direct_answer_not_waived_by_prior_attempt(self):
        current='我想核对，但直接给我完整答案'
        m=EvidenceMemory.from_records([row('解方程3x=15，我试着除以3。')],current)
        self.assertEqual(context_interpretation(m,current)['kind'],'direct_answer_request')

    def test_four_histories_are_not_same_evidence(self):
        current='所以x=5，对吗？'
        histories=[[],[row('解方程3x=15，我想两边除以3。')],
                   [row('解方程3x=15','两边除以3得到x=5。')],
                   [row('解方程3x=15，我想两边除以3。'),row('换题，解方程2x=12')]]
        kinds=[context_interpretation(EvidenceMemory.from_records(h,current),current)['kind'] for h in histories]
        self.assertEqual(kinds[0],'result_check_process_not_established')
        self.assertEqual(kinds[1],'result_check_with_prior_student_process')
        self.assertEqual(kinds[2],'checking_reported_answer')
        self.assertEqual(kinds[3],'result_check_process_not_established')

    def test_followup_connection_points_to_same_problem_student_step(self):
        m=EvidenceMemory.from_records([row('解方程3x+4=19，我已经得到3x=15。')],'之后要怎么做？')
        connections=m.view()['connections']
        self.assertTrue(connections)
        lookup={n['id']:n for n in m.nodes}
        self.assertEqual(lookup[connections[-1]['target']]['source_event'],'u1')
        self.assertEqual(lookup[connections[-1]['target']]['role'],'student')
        content,_=memory_messages(m,[],'之后要怎么做？')
        self.assertIn('关系线索',content)
        self.assertFalse(m.validate())

    def test_persistence_does_not_overwrite_newer_version(self):
        m=EvidenceMemory.from_records([row('解方程3x=15')],'为什么')
        scratch=Path(__file__).resolve().parents[1]/'.private/test_tmp'
        scratch.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            db=Path(d)/'memory.db'
            persist_memory(db,'test',2,m);persist_memory(db,'test',1,EvidenceMemory())
            with closing(sqlite3.connect(db)) as c:
                version,graph=c.execute('SELECT turn_version,graph_json FROM evidence_memory').fetchone()
            self.assertEqual(version,2)
            self.assertEqual(json.loads(graph)['events'],m.events)


if __name__=='__main__':unittest.main()
