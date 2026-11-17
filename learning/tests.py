import io
import os
import unittest.mock
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from fastapi.testclient import TestClient
from ai_service.main import app
from ai_service.providers import TutorResponse, LearningContent, ProviderUnavailable, tutor_reply
from .models import Profile, Material, LearningSession, KnowledgeGap, Quiz, QuizAttempt, DailyUsage

@override_settings(REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.TokenAuthentication'],'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated']})
class IntegratedTests(TransactionTestCase):
    def setUp(self):
        call_command('seed_learning',stdout=io.StringIO())
        self.student=User.objects.create_user('student',password='ComplexPass123!')
        self.other=User.objects.create_user('other',password='ComplexPass123!')
        self.teacher=User.objects.create_user('teacher',password='ComplexPass123!')
        self.admin=User.objects.create_user('admin',password='ComplexPass123!')
        for u,r in [(self.student,'student'),(self.other,'student'),(self.teacher,'educator'),(self.admin,'admin')]: Profile.objects.create(user=u,role=r)
        self.client=APIClient();self.client.force_authenticate(self.student)
        self.token=Token.objects.create(user=self.student).key
        self.ai=TestClient(app)
        self.headers={'Authorization':'Token '+self.token}
    def test_public_registration_cannot_escalate(self):
        self.client.force_authenticate(None)
        result=self.client.post('/api/v1/auth/register/',{'username':'newstudent','password':'ComplexPass123!','name':'Học sinh','grade':9,'role':'admin'})
        self.assertEqual(result.status_code,400)
        result=self.client.post('/api/v1/auth/register/',{'username':'newstudent','password':'ComplexPass123!','name':'Học sinh','grade':9})
        self.assertEqual(result.status_code,201)
        self.assertEqual(result.data['profile']['role'],'student')
    def test_profile_cannot_escalate(self):
        self.assertEqual(self.client.patch('/api/v1/auth/me/',{'role':'admin'}).status_code,400)
        self.assertEqual(self.client.patch('/api/v1/auth/me/',{'name':'Tên mới','grade':10}).status_code,200)
    def test_authentication_and_logout_revocation(self):
        self.assertEqual(self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'test'}).status_code,401)
        self.client.force_authenticate(None)
        login=self.client.post('/api/v1/auth/login/',{'username':'student','password':'ComplexPass123!'})
        self.assertEqual(login.status_code,200)
        self.client.credentials(HTTP_AUTHORIZATION='Token '+login.data['token'])
        self.assertEqual(self.client.post('/api/v1/auth/logout/').status_code,204)
        self.assertEqual(self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'test'},headers=self.headers).status_code,401)
    def test_student_denied_teacher_and_admin_operations(self):
        self.assertEqual(self.client.post('/api/v1/materials/',{}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/users/').status_code,403)
        self.assertEqual(self.client.get('/api/v1/statistics/').status_code,403)
        self.assertEqual(self.ai.post('/api/v1/rag/sync',headers=self.headers).status_code,403)
        self.assertEqual(self.ai.post('/api/v1/research/report',json={'concept_id':'trig'},headers=self.headers).status_code,403)
    def test_drafts_hidden_and_material_ownership(self):
        m=Material.objects.create(owner=self.teacher,title='Nháp',text='Nội dung',topic='Toán',status='Bản nháp')
        self.assertEqual(self.client.get(f'/api/v1/materials/{m.pk}/').status_code,404)
        self.client.force_authenticate(self.teacher)
        response=self.client.post('/api/v1/materials/',{'title':'Học liệu','text':'Nội dung','topic':'Toán','grade':9,'kind':'triangle','status':'Đã xuất bản'},format='json')
        self.assertEqual(response.status_code,201)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(f'/api/v1/materials/{m.pk}/',{'title':'Đã sửa'}).status_code,200)
    def test_prerequisite_cycle_and_duplicate_denied(self):
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post('/api/v1/edges/',{'source':'trig','target':'sides'}).status_code,400)
        self.assertEqual(self.client.post('/api/v1/edges/',{'source':'sides','target':'trig'}).status_code,400)
        self.assertEqual(self.client.post('/api/v1/edges/',{'source':'area','target':'sphere'}).status_code,200)
        self.assertEqual(self.client.delete('/api/v1/edges/',{'source':'area','target':'sphere'},format='json').status_code,200)
    def test_sessions_are_private(self):
        s=LearningSession.objects.create(user=self.other,title='Private')
        self.assertEqual(self.client.get(f'/api/v1/sessions/{s.pk}/').status_code,404)
        self.assertEqual(self.ai.post('/api/v1/tutor/socratic-ask',data={'session_id':str(s.pk),'prompt_question':'test'},headers=self.headers).status_code,404)
    def test_quiz_answers_are_hidden_then_scored_on_server(self):
        q=Quiz.objects.filter(kind='triangle',source='curated').first()
        public=self.client.get(f'/api/v1/quizzes/{q.pk}/').data
        self.assertNotIn('correct',public['questions'][0]);self.assertNotIn('explanation',public['questions'][0])
        response=self.client.post(f'/api/v1/quizzes/{q.pk}/submit/',{'answers':[0,1,3,1],'score':4,'seconds':20},format='json')
        self.assertEqual(response.status_code,200);self.assertEqual(response.data['result']['score'],3)
        self.assertEqual(KnowledgeGap.objects.get(user=self.student,concept_id='sides').errors,1)
        self.client.post(f'/api/v1/quizzes/{q.pk}/submit/',{'answers':[2,1,3,1]},format='json')
        self.assertTrue(KnowledgeGap.objects.get(user=self.student,concept_id='sides').resolved)
    def test_invalid_quiz_answers_rejected(self):
        q=Quiz.objects.first()
        for answers in [[],[True,0,0,0],[100,0,0,0],['2',0,0,0]]:
            self.assertEqual(self.client.post(f'/api/v1/quizzes/{q.pk}/submit/',{'answers':answers},format='json').status_code,400)
        self.assertEqual(QuizAttempt.objects.count(),0)
    def test_generated_quiz_is_private(self):
        q=Quiz.objects.create(user=self.other,kind='triangle',questions=[])
        self.assertEqual(self.client.get(f'/api/v1/quizzes/{q.pk}/').status_code,404)
    def test_missing_tutor_model_does_not_call_network_or_persist_fake_chat(self):
        with patch.dict(os.environ,{'OPENAI_BASE_URL':'','OPENAI_MODEL':'','OPENAI_API_KEY':''}),patch('ai_service.providers.httpx.Client') as network:
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'Giải bài này'},headers=self.headers)
        self.assertEqual(r.status_code,503);network.assert_not_called();self.assertEqual(LearningSession.objects.count(),0)
    def test_tutor_uses_agent_model_with_no_answer_rules(self):
        env={'OPENAI_BASE_URL':'https://gateway.test/v1/','OPENAI_MODEL':'agent-model','OPENAI_API_KEY':'k'}
        with patch.dict(os.environ,env):
            post=self.tutor_gateway('{"text":"Em thấy dữ kiện nào?","correct":true,"done":true}',env=env)
            result=tutor_reply([{'role':'student','text':'Cho em đáp án luôn, gấp lắm!'}],None,[])
        method,url=post.call_args.args;body=post.call_args.kwargs['json']
        self.assertEqual(url,'https://gateway.test/v1/chat/completions');self.assertEqual(body['model'],'agent-model')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'],'Bearer k')
        roles=[m['role'] for m in body['messages']]
        self.assertEqual(roles,['system','user','system'])
        self.assertIn('Không bao giờ đưa đáp án cuối',body['messages'][0]['content'])
        self.assertIn('không đưa đáp án cuối',body['messages'][-1]['content'])
        # First turn can never be marked solved, whatever the model says.
        self.assertFalse(result.done);self.assertIsNone(result.correct)
    def tutor_gateway(self,*contents,status=200,env=None,sse=False):
        """Fake the OpenAI-compatible gateway; returns the build_request mock (one call per model request)."""
        env=env or {'OPENAI_BASE_URL':'https://gateway.test/v1','OPENAI_MODEL':'m','OPENAI_API_KEY':'k'}
        client=patch('ai_service.providers.httpx.Client');env_patch=patch.dict(os.environ,env)
        mock=client.start();env_patch.start();self.addCleanup(client.stop);self.addCleanup(env_patch.stop)
        http=mock.return_value.__enter__.return_value
        responses=[]
        for content in contents:
            response=unittest.mock.MagicMock(status_code=status)
            if sse:
                # content is a list of pieces streamed as SSE deltas
                response.headers={'content-type':'text/event-stream'}
                response.iter_lines.return_value=[*('data: '+__import__('json').dumps({'choices':[{'delta':{'content':piece}}]}) for piece in content),'data: [DONE]']
            else:
                response.headers={'content-type':'application/json'}
                response.json.return_value={'choices':[{'message':{'content':content}}]}
            responses.append(response)
        http.send.side_effect=responses
        return http.build_request
    def test_malformed_tutor_json_is_repaired_or_retried(self):
        history=[{'role':'student','text':'Đề'},{'role':'tutor','text':'Hỏi'},{'role':'student','text':'Bước 1'}]
        # Unescaped LaTeX, prose around the JSON and unsupported geometry must not fail the turn.
        self.tutor_gateway('Đây: {"text":"Xét $\\frac{1}{2}\\cdot GH$","geometry":{"type":"square"},"highlight":"side","correct":"false","concept":"trig"} hết')
        result=tutor_reply(history,None,[{'id':'trig','title':'T'}])
        self.assertEqual(result.text,'Xét $\\frac{1}{2}\\cdot GH$');self.assertIs(result.correct,False);self.assertEqual(result.concept,'trig')
        self.assertIsNone(result.geometry)
        post=self.tutor_gateway('không phải json','{"text":"Thử lại được"}')
        self.assertEqual(tutor_reply(history,None,[]).text,'Thử lại được');self.assertEqual(post.call_count,2)
    def test_tutor_figure_kept_when_valid_and_dropped_when_unsafe(self):
        import json as _json
        figure={'title':'Tam giác','params':[{'name':'a','label':'a','min':1,'max':10,'step':0.5,'value':4}],
                'points':{'A':[0,0],'B':['a','0'],'C':['a/2','3']},'shapes':[{'type':'polygon','points':['A','B','C'],'fill':True}],
                'measures':[{'label':'Nửa đáy','expr':'a/2'}]}
        history=[{'role':'student','text':'Đề'},{'role':'tutor','text':'Hỏi'},{'role':'student','text':'Em muốn xem hình'}]
        self.tutor_gateway(_json.dumps({'text':'Kéo thử nhé','figure':figure}))
        self.assertEqual(tutor_reply(history,None,[]).figure.points['B'],['a','0'])
        for bad in [{**figure,'points':{'A':['__import__("os")','0']}},{**figure,'shapes':[{'type':'segment','points':['A','Z']}]},{**figure,'measures':[{'label':'x','expr':'2**3'}]}]:
            self.tutor_gateway(_json.dumps({'text':'Vẫn giữ lời gia sư','figure':bad}))
            result=tutor_reply(history,None,[])
            self.assertEqual(result.text,'Vẫn giữ lời gia sư');self.assertIsNone(result.figure)
    def test_tutor_stream_emits_status_text_and_result(self):
        from ai_service.providers import tutor_stream
        self.tutor_gateway(['{"te','xt":"Xét $\\','frac{1}{2}$ nhé','","figure":{"poi','nts":{}},"correct":null}'],sse=True)
        events=list(tutor_stream([{'role':'student','text':'Đề'},{'role':'tutor','text':'Hỏi'},{'role':'student','text':'Bước'}],None,[]))
        kinds=[k for k,_ in events]
        self.assertEqual(kinds[0:2],[('status'),('status')]);self.assertEqual(events[0][1],'thinking');self.assertEqual(events[1][1],'writing')
        self.assertEqual(''.join(v for k,v in events if k=='delta'),'Xét $\\frac{1}{2}$ nhé')
        self.assertIn(('status','figure'),events)
        self.assertEqual(events[-1][0],'result');self.assertEqual(events[-1][1].text,'Xét $\\frac{1}{2}$ nhé')
    def test_stream_endpoint_saves_turn_and_reports_errors(self):
        import json as _json
        def fake(messages,photo,concepts):
            yield 'status','thinking';yield 'delta','Em ';yield 'delta','thử nhé'
            yield 'result',TutorResponse(text='Em thử nhé')
        with patch('ai_service.main.tutor_stream',fake):
            r=self.ai.post('/api/v1/tutor/socratic-ask/stream',data={'prompt_question':'Đề bài'},headers=self.headers)
        events=[_json.loads(l) for l in r.text.splitlines()]
        self.assertEqual([e['type'] for e in events],['status','delta','delta','status','done'])
        self.assertEqual(events[-1]['session']['messages'][1]['text'],'Em thử nhé');self.assertEqual(LearningSession.objects.count(),1)
        def broken(messages,photo,concepts):
            yield 'status','thinking';raise ProviderUnavailable('Model gia sư đang quá tải')
        with patch('ai_service.main.tutor_stream',broken):
            r=self.ai.post('/api/v1/tutor/socratic-ask/stream',data={'prompt_question':'Đề bài'},headers=self.headers)
        last=_json.loads(r.text.splitlines()[-1])
        self.assertEqual((last['type'],last['status']),('error',503));self.assertEqual(LearningSession.objects.count(),1)
        # Validation errors stay normal HTTP errors before any streaming.
        self.assertEqual(self.ai.post('/api/v1/tutor/socratic-ask/stream',data={'prompt_question':''},headers=self.headers).status_code,422)
    def test_tutor_gateway_overload_is_explicit(self):
        self.tutor_gateway('{}',status=503)
        with self.assertRaisesRegex(ProviderUnavailable,'quá tải'):
            tutor_reply([{'role':'student','text':'x'}],None,[])
    def test_student_drawing_mid_session_is_stored_and_sent(self):
        from PIL import Image
        stream=io.BytesIO();Image.new('RGB',(5,5)).save(stream,format='PNG')
        session=LearningSession.objects.create(user=self.student,title='Bài',messages=[{'role':'student','text':'Đề','photo':{'name':'old.png','data':'data:image/png;base64,OLD'}},{'role':'tutor','text':'Hỏi'}])
        with patch('ai_service.main.tutor_reply',return_value=TutorResponse(text='Hình em vẽ đúng hướng.')) as tutor:
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'session_id':str(session.pk)},files={'photo':('ve.png',stream.getvalue(),'image/png')},headers=self.headers)
        self.assertEqual(r.status_code,200)
        sent=tutor.call_args.args[0][-1]
        self.assertTrue(sent['photo']['data'].startswith('data:image/png'));self.assertIn('kiểm tra',sent['text'])
        self.assertIn('photo',r.json()['session']['messages'][2])
        # Only the newest drawing is attached to the model request.
        post=self.tutor_gateway('{"text":"ok"}')
        tutor_reply(tutor.call_args.args[0],None,[])
        users=[m for m in post.call_args.kwargs['json']['messages'] if m['role']=='user']
        self.assertIsInstance(users[0]['content'],str);self.assertIn('ảnh cũ',users[0]['content'])
        self.assertEqual(users[-1]['content'][1]['type'],'image_url')
    def test_tutor_turn_persists_and_records_gap(self):
        with patch('ai_service.main.tutor_reply',return_value=TutorResponse(text='Cạnh nào đối diện góc vuông?',geometry={'type':'triangle','b':4,'h':3})):
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'Tam giác vuông'},headers=self.headers)
        self.assertEqual(r.status_code,200);sid=r.json()['session']['id']
        with patch('ai_service.main.tutor_reply',return_value=TutorResponse(text='Em thử kiểm tra lại cạnh huyền nhé.',correct=False,concept='sides')):
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'session_id':sid,'prompt_question':'AB'},headers=self.headers)
        self.assertEqual(r.status_code,200);self.assertEqual(len(r.json()['session']['messages']),4)
        self.assertEqual(KnowledgeGap.objects.get(user=self.student,concept_id='sides').errors,1)
        self.assertTrue(r.json()['response']['incorrect'])
    def test_bad_model_response_does_not_save(self):
        with patch('ai_service.main.tutor_reply',side_effect=ValueError('secret-key=abc')):
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'test'},headers=self.headers)
        self.assertEqual(r.status_code,502);self.assertNotIn('secret-key',r.text);self.assertEqual(LearningSession.objects.count(),0)
    def test_photo_validation_checks_bytes(self):
        r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'test'},files={'photo':('bad.png',b'not an image','image/png')},headers=self.headers)
        self.assertEqual(r.status_code,422)
    def test_valid_photo_goes_only_to_tutor_provider(self):
        from PIL import Image
        stream=io.BytesIO();Image.new('RGB',(5,5)).save(stream,format='PNG')
        with patch('ai_service.main.tutor_reply',return_value=TutorResponse(text='Em thấy những dữ kiện nào?')) as local,patch('ai_service.main.generate_learning') as cloud:
            r=self.ai.post('/api/v1/tutor/socratic-ask',files={'photo':('ok.png',stream.getvalue(),'image/png')},headers=self.headers)
        self.assertEqual(r.status_code,200);self.assertTrue(local.call_args.args[1]['data'].startswith('data:image/png'));cloud.assert_not_called()
    def test_rag_unconfigured_is_explicit(self):
        with patch.dict(os.environ,{'RAG_ENABLED':'false'}):
            r=self.ai.post('/api/v1/rag/analyze-gap',json={'concept_id':'trig'},headers=self.headers)
        self.assertEqual(r.status_code,503)
    def test_recommendation_uses_academic_context_only(self):
        context={'concept_id':'trig','contexts':[{'concept_id':'trig','text':'sin = đối/huyền'}]}
        content=LearningContent(summary='Tỉ số lượng giác',questions=[{'concept':'trig','question':'sin là gì?','options':['đối/huyền','kề/huyền','đối/kề','kề/đối'],'correct':0,'explanation':'Định nghĩa sin.'}],exercises=[{'concept':'trig','question':'Tính sin khi đối=3,huyền=5','hints':['Dùng tỉ số'],'answer':'3/5'}])
        with patch('integrations.geometry_rag.retrieve',return_value=context),patch('ai_service.main.generate_learning',return_value=(content,'gemini')) as cloud:
            r=self.ai.post('/api/v1/recommend/quiz-summary',json={'concept_id':'trig','student_name':'DO NOT SEND','messages':['PRIVATE']},headers=self.headers)
        self.assertEqual(r.status_code,200);self.assertEqual(cloud.call_args.args[0],context)
        self.assertEqual(Quiz.objects.get(pk=r.json()['quiz_id']).user,self.student)
        self.assertNotIn('correct',r.json())
    def test_daily_quota_is_enforced_before_provider(self):
        from learning.services import reserve_generation
        from .models import SystemConfig
        from rest_framework.exceptions import Throttled
        SystemConfig.objects.create(key='gemini_daily_limit',value=1)
        reserve_generation()
        with self.assertRaises(Throttled):reserve_generation()
        self.assertEqual(DailyUsage.objects.get().calls,1)
    def test_admin_changes_role_and_revokes_tokens(self):
        self.client.force_authenticate(self.admin)
        r=self.client.patch('/api/v1/users/',{'id':self.student.id,'role':'educator'},format='json')
        self.assertEqual(r.status_code,200);self.assertFalse(Token.objects.filter(user=self.student).exists())
        self.assertEqual(self.client.patch('/api/v1/users/',{'id':self.admin.id,'role':'student'},format='json').status_code,400)
    def test_clear_learning_does_not_delete_other_users(self):
        LearningSession.objects.create(user=self.student,title='Mine')
        other=LearningSession.objects.create(user=self.other,title='Other')
        self.assertEqual(self.client.delete('/api/v1/learning-data/').status_code,204)
        self.assertTrue(LearningSession.objects.filter(pk=other.pk).exists())

class UpstreamReuseTests(TransactionTestCase):
    def test_upstream_rrf_combines_shared_nodes(self):
        from integrations.upstream import load_source
        from llama_index.core.schema import TextNode,NodeWithScore
        hybrid=load_source('test_upstream_rrf','hybrid_graph_rag/hybridRAG_paper/retrieval/search/hybrid_search.py').HybridSearch()
        a=NodeWithScore(node=TextNode(id_='a',text='A'),score=1)
        b=NodeWithScore(node=TextNode(id_='b',text='B'),score=1)
        result=hybrid.merge(vector_results=[a,b],graph_results=[b],top_k=2)
        self.assertEqual(result[0].node.node_id,'b')
        self.assertEqual({n.node.node_id for n in result},{'a','b'})
