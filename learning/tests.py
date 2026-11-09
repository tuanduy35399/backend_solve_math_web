import io
import os
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from fastapi.testclient import TestClient
from ai_service.main import app
from ai_service.providers import TutorResponse, LearningContent, ProviderUnavailable, qwen_reply
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
    def test_missing_local_model_does_not_call_cloud_or_persist_fake_chat(self):
        with patch.dict(os.environ,{'QWEN_BASE_URL':'','QWEN_MODEL':''}),patch('ai_service.providers.httpx.Client') as network:
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'Giải bài này'},headers=self.headers)
        self.assertEqual(r.status_code,503);network.assert_not_called();self.assertEqual(LearningSession.objects.count(),0)
    def test_qwen_turn_persists_and_records_gap(self):
        with patch('ai_service.main.qwen_reply',return_value=TutorResponse(text='Cạnh nào đối diện góc vuông?',geometry={'type':'triangle','b':4,'h':3})):
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'Tam giác vuông'},headers=self.headers)
        self.assertEqual(r.status_code,200);sid=r.json()['session']['id']
        with patch('ai_service.main.qwen_reply',return_value=TutorResponse(text='Em thử kiểm tra lại cạnh huyền nhé.',correct=False,concept='sides')):
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'session_id':sid,'prompt_question':'AB'},headers=self.headers)
        self.assertEqual(r.status_code,200);self.assertEqual(len(r.json()['session']['messages']),4)
        self.assertEqual(KnowledgeGap.objects.get(user=self.student,concept_id='sides').errors,1)
        self.assertTrue(r.json()['response']['incorrect'])
    def test_bad_model_response_does_not_save(self):
        with patch('ai_service.main.qwen_reply',side_effect=ValueError('secret-key=abc')):
            r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'test'},headers=self.headers)
        self.assertEqual(r.status_code,502);self.assertNotIn('secret-key',r.text);self.assertEqual(LearningSession.objects.count(),0)
    def test_photo_validation_checks_bytes(self):
        r=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'test'},files={'photo':('bad.png',b'not an image','image/png')},headers=self.headers)
        self.assertEqual(r.status_code,422)
    def test_valid_photo_goes_only_to_local_provider(self):
        from PIL import Image
        stream=io.BytesIO();Image.new('RGB',(5,5)).save(stream,format='PNG')
        with patch('ai_service.main.qwen_reply',return_value=TutorResponse(text='Em thấy những dữ kiện nào?')) as local,patch('ai_service.main.generate_learning') as cloud:
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
