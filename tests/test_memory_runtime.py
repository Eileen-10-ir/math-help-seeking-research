"""Integration tests against the actual frozen classifier, state and service."""
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from memory_runtime import bootstrap
from memory_support import make_support
runtime, MemoryService=bootstrap()
from routing_v8 import support as old_support
from cloud_gateway import CloudConfig
import runtime_server as legacy


class FakeGateway:
    """Transport stub; never contact a provider or claim educational quality."""
    def __init__(self):
        self.config=CloudConfig(engineering=True)
        self.messages=[]
    def public(self):return {'configured':True,'engineering':True,'provider':'engineering_stub','model_requested':'stub'}
    def request(self,messages):
        self.messages.append(copy.deepcopy(messages))
        return {'provider':'engineering_stub','model_requested':'stub','model_returned':'stub',
                'messages_sent':messages,'status':'success','text':'工程传递检查，不是数学辅导结果。',
                'duration_ms':0,'external_cloud_attempts':0,'external_cloud_successes':0,
                'engineering_api_attempts':1,'usage':None}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        scratch=ROOT/'.private/test_tmp';scratch.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch)
        self.gateway=FakeGateway()
        self.service=MemoryService(Path(self.temp.name)/'session.db',engineering=True,gateway=self.gateway)
    def tearDown(self):self.temp.cleanup()
    def submit(self,session,text,rid):
        return self.service.submit({'session_id':session['session_id'],'text':text,'request_id':rid,'expected_version':session['version']})

    def test_actual_single_state_profile_and_duplicate(self):
        s=self.service.new({'task_id':'free'})
        r1=self.submit(s,'解方程3x+4=19，请直接给我完整答案。','memory_test_001')
        self.assertEqual(r1['record']['support']['route_requested'],'edge_fixed')
        self.assertEqual(len(self.gateway.messages),0)
        r2=self.submit(r1['session'],'我已得到3x=15，我想把两边同时除以5，请检查这一步。','memory_test_002')
        self.assertTrue(r2['session']['evidence_memory']['nodes'])
        self.assertEqual(r2['record']['analysis']['rule_version'],r1['record']['analysis']['rule_version'])
        again=self.submit(r1['session'],'我已得到3x=15，我想把两边同时除以5，请检查这一步。','memory_test_002')
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['session']['version'],2)
        with closing(sqlite3.connect(self.service.db)) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM turns').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT turn_version FROM evidence_memory').fetchone()[0],2)
        ack=self.submit(again['session'],'好的','memory_test_003')
        self.assertFalse(ack['record']['analysis']['risk_updated'])
        self.assertEqual(ack['record']['analysis']['risk'],r2['record']['analysis']['risk'])

    def test_memory_only_preserves_all_classification_and_state(self):
        inputs=['解方程3x+4=19，直接告诉我答案。','这道题我不太会，可以提供一些思路吗？',
                '我已得到3x=15，为什么要除以3？','所以x=5，对吗？','好的']
        histories=[]
        for name, policy in [('old',old_support),('memory',make_support(old_support))]:
            legacy.support=policy
            svc=MemoryService(Path(self.temp.name)/(name+'.db'),engineering=True,gateway=FakeGateway())
            session=svc.new({'task_id':'free'});analyses=[];states=[];routes=[]
            for i,text in enumerate(inputs):
                response=svc.submit({'session_id':session['session_id'],'text':text,'request_id':f'{name}_request_{i:04d}','expected_version':session['version']})
                session=response['session'];analyses.append(response['record']['analysis']);states.append(session['state']);routes.append(response['record']['support']['route_requested'])
            histories.append((analyses,states,routes))
        self.assertEqual(histories[0],histories[1])

    def test_three_routes_and_suffix(self):
        legacy.support=make_support(old_support)
        samples={'high':'请直接给出答案','medium':'请给我这道题的方法','low':'我得到3x=15，请检查移项的依据'}
        for level,text in samples.items():
            result={'eligible':True,'decision_level':level,'history_high_protection':False,
                    'observed_event':'question','risk':.5,'history_high_threshold':.7,'hold_reasons':[]}
            gateway=FakeGateway()
            reply=make_support(old_support)(text,'linear',{'question':'3x+4=19'},result,gateway,[])
            self.assertEqual(reply['route_requested'],{'high':'edge_fixed','medium':'cloud_constrained','low':'cloud_direct'}[level])
            self.assertEqual(len(gateway.messages),0 if level=='high' else 1)
            if level=='medium':self.assertIn('请不要直接给出最终答案',gateway.messages[0][-1]['content'])
            if level=='low':self.assertNotIn('请不要直接给出最终答案',gateway.messages[0][-1]['content'])

    def test_optional_bridge_is_not_grade_relabel(self):
        history=[{'text':'解方程3x+4=19，我得到3x=15','support':{'text':'下一步想做什么？','status':'success'}}]
        result={'eligible':False,'decision_level':None,'history_high_protection':False,
                'observed_event':'answer_only','risk':.9,'history_high_threshold':.7,'hold_reasons':[]}
        original=copy.deepcopy(result);g=FakeGateway()
        reply=make_support(old_support,continuation_help=True)('两边同时除以5','free',{'question':''},result,g,history)
        self.assertTrue(reply['continuation_bridge_used'])
        self.assertFalse(reply['state_measurement_eligible'])
        self.assertIsNone(reply['grade_used_for_routing'])
        self.assertEqual(result,original)
        self.assertEqual(reply['route_requested'],'cloud_constrained')
        self.assertIn('3x=15',g.messages[0][0]['content'])
        self.assertIn('两边同时除以5',g.messages[0][-1]['content'])

    def test_refined_template_record_matches_actual_sent_suffix(self):
        from memory_support import REFINED_SUFFIX
        result={'eligible':True,'decision_level':'medium','history_high_protection':False,
                'observed_event':'question','risk':.5,'history_high_threshold':.7,'hold_reasons':[]}
        g=FakeGateway();text='所以x=5，对吗？'
        reply=make_support(old_support,refined_guidance=True)(text,'linear',{'question':'3x+4=19'},result,g,[])
        self.assertEqual(reply['edge_suffix'],REFINED_SUFFIX)
        self.assertEqual(reply['messages_sent'][-1]['content'],text+'\n\n'+REFINED_SUFFIX)
        self.assertIn('可以明确核对',reply['edge_suffix'])

    def test_ungraded_mixed_answer_demand_does_not_bypass(self):
        history=[{'text':'解方程3x+4=19，我得到3x=15','support':{'text':'下一步想做什么？','status':'success'}}]
        result={'eligible':False,'decision_level':None,'history_high_protection':False,
                'observed_event':'question','risk':.9,'history_high_threshold':.7,'hold_reasons':[]}
        g=FakeGateway()
        reply=make_support(old_support,continuation_help=True)('3x=15，直接给我答案对吗？','free',{'question':''},result,g,history)
        self.assertFalse(reply['continuation_bridge_used'])
        self.assertFalse(g.messages)

    def test_partial_disclosure_guard_keeps_raw_paid_result(self):
        from conversation_memory import EvidenceMemory
        from memory_support import guard_constrained_reply
        m=EvidenceMemory.from_records([{'text':'解方程3x=15','support':{'text':'下一步呢','status':'success'}}],'两边除以5可以吗？')
        r={'route_requested':'cloud_constrained','route_executed':'cloud_constrained','status':'success','text':'同除以3得x=5','external_cloud_attempts':1}
        guard_constrained_reply(r,m)
        self.assertTrue(r['response_guard']['withheld'])
        self.assertEqual(r['raw_cloud_text'],'同除以3得x=5')
        self.assertEqual(r['external_cloud_attempts'],1)
        self.assertEqual(r['route_executed'],'cloud_reply_withheld_local_hint')

    def test_checking_already_given_result_is_not_withheld(self):
        from conversation_memory import EvidenceMemory
        from memory_support import guard_constrained_reply
        m=EvidenceMemory.from_records([], '我得到x=5，对吗？')
        r={'route_requested':'cloud_constrained','status':'success','text':'x=5是正确的'}
        guard_constrained_reply(r,m)
        self.assertFalse(r['response_guard']['withheld'])

    def test_direct_cloud_not_subject_to_constrained_disclosure_guard(self):
        from conversation_memory import EvidenceMemory
        from memory_support import guard_constrained_reply
        r={'route_requested':'cloud_direct','status':'success','text':'x=5'}
        guard_constrained_reply(r,EvidenceMemory())
        self.assertNotIn('response_guard',r)

    def test_screenshot_method_requests_reach_cloud_after_high_history(self):
        legacy.support=make_support(old_support,continuation_help=True,refined_guidance=True)
        session=self.service.new({'task_id':'free'})
        phrases=['解方程3x+4=19。我已经得到3x=15，直接给我最终答案。',
                 '没有，但是我不知道思路，给我思路','我不知道3x=15之后要怎么做','所以x=5？','好的']
        replies=[]
        for i,text in enumerate(phrases):
            result=self.submit(session,text,f'screenshot_test_{i:03d}')
            session=result['session'];replies.append(result['record'])
        self.assertEqual(replies[0]['support']['route_requested'],'edge_fixed')
        self.assertIn('你已经写到“3x=15”',replies[0]['support']['text'])
        self.assertNotIn('直接给我最终答案',replies[0]['support']['text'])
        self.assertIn('下一步有什么思路',replies[0]['support']['text'])
        for reply in replies[1:4]:
            self.assertEqual(reply['support']['route_requested'],'cloud_constrained')
            self.assertTrue(reply['support']['continuation_bridge_used'])
            self.assertFalse(reply['analysis']['risk_updated'])
            self.assertIsNone(reply['analysis']['current_behavior_level'])
            self.assertEqual(reply['analysis']['risk'],1)
            self.assertIn('3x=15',reply['support']['messages_sent'][0]['content'])
        self.assertEqual(len(self.gateway.messages),3)
        self.assertFalse(replies[-1]['analysis']['risk_updated'])
        self.assertEqual(replies[-1]['support']['route_requested'],'edge_verify')

    def test_first_complete_problem_can_receive_method_help_without_fake_history(self):
        legacy.support=make_support(old_support,continuation_help=True,refined_guidance=True)
        session=self.service.new({'task_id':'free'})
        result=self.submit(session,'解方程3x+4=19，我没有思路，可以给我下一步的提示吗？','first_complete_0001')
        self.assertEqual(result['record']['support']['route_requested'],'cloud_constrained')
        self.assertEqual(len(self.gateway.messages),1)

    def test_method_words_do_not_override_current_explicit_answer_demand(self):
        legacy.support=make_support(old_support,continuation_help=True,refined_guidance=True)
        session=self.service.new({'task_id':'free'})
        result=self.submit(session,'解方程3x+4=19，给点思路但直接告诉我最终答案。','still_high_0001')
        self.assertEqual(result['record']['support']['route_requested'],'edge_fixed')
        self.assertFalse(self.gateway.messages)

    def test_bounded_repair_counts_both_requests_and_retains_raw_outputs(self):
        from conversation_memory import EvidenceMemory
        from memory_support import repair_or_guard_reply
        class RepairGateway(FakeGateway):
            def request(self,messages):
                result=super().request(messages)
                result.update(text='观察未知数前面的系数，想想乘法的逆运算。',
                    external_cloud_attempts=1,external_cloud_successes=1,engineering_api_attempts=0,
                    usage={'prompt_tokens':20,'completion_tokens':10,'total_tokens':30})
                return result
        g=RepairGateway();m=EvidenceMemory.from_records([], '解方程3x=15，下一步思路是什么？')
        record={'route_requested':'cloud_constrained','route_executed':'cloud_constrained',
                'status':'success','text':'同除以3得到x=5','messages_sent':[{'role':'user','content':'下一步思路是什么？'}],
                'external_cloud_attempts':1,'external_cloud_successes':1,'engineering_api_attempts':0,
                'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15},'duration_ms':1}
        repair_or_guard_reply(record,m,g)
        self.assertEqual(len(g.messages),1)
        self.assertEqual(record['external_cloud_attempts'],2)
        self.assertEqual(record['usage']['total_tokens'],45)
        self.assertEqual(record['generation_attempts'][0]['text'],'同除以3得到x=5')
        self.assertFalse(record['response_guard']['withheld'])
        self.assertEqual(record['route_executed'],'cloud_constrained')

    def test_answer_check_arithmetic_chain_not_misread_as_new_answer(self):
        from conversation_memory import EvidenceMemory
        from memory_support import guard_constrained_reply,explicit_scalar_answers
        m=EvidenceMemory.from_records([], '所以x=5？')
        record={'route_requested':'cloud_constrained','status':'success',
                'text':r'对，\(x=5\)。从\(3x=15\)得\(x=15\div3=5\)。'}
        guard_constrained_reply(record,m)
        self.assertFalse(record['response_guard']['withheld'])
        self.assertEqual(explicit_scalar_answers(r'x=15\div3=5'),{('x','5')})
        self.assertEqual(explicit_scalar_answers('3 x=15'),set())
        self.assertEqual(explicit_scalar_answers('x=5.0'),{('x','5')})


if __name__=='__main__':unittest.main()
