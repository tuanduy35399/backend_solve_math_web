"""Independent regression cases from QA; only test databases and controlled mocks."""
import io
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.cache import cache
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from fastapi.testclient import TestClient
from ai_service.main import app
from .models import Profile,Material,LearningSession,Story,Quiz

class IndependentQATests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        call_command('seed_learning',stdout=io.StringIO())
        self.student=User.objects.create_user('qa_ind_student',password='QA-Password32!')
        self.teacher=User.objects.create_user('qa_ind_teacher',password='QA-Password32!')
        self.other=User.objects.create_user('qa_ind_other',password='QA-Password32!')
        for user,role in [(self.student,'student'),(self.teacher,'educator'),(self.other,'educator')]:Profile.objects.create(user=user,role=role)
        self.client=APIClient()
        self.ai=TestClient(app)
        self.token=Token.objects.create(user=self.student)
        self.headers={'Authorization':'Token '+self.token.key}
    def test_teacher_cannot_write_other_teacher_material(self):
        material=Material.objects.create(owner=self.other,title='Other author',text='Text',topic='Geometry',status='Đã xuất bản')
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.patch(f'/api/v1/materials/{material.pk}/',{'text':'Changed'}).status_code,403)
        self.assertEqual(self.client.delete(f'/api/v1/materials/{material.pk}/').status_code,403)
        material.refresh_from_db();self.assertEqual(material.text,'Text')
    def test_draft_is_hidden_from_other_teacher(self):
        material=Material.objects.create(owner=self.other,title='Draft',text='Text',topic='Geometry')
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(f'/api/v1/materials/{material.pk}/').status_code,404)
    def test_malformed_published_story_is_rejected(self):
        self.client.force_authenticate(self.teacher)
        result=self.client.post('/api/v1/stories/',{'id':'bai-viet-qa-malformed','status':'published','paragraphs':[1],'title':{},'sources':None},format='json')
        self.assertEqual(result.status_code,400)
        self.assertFalse(Story.objects.filter(pk='bai-viet-qa-malformed').exists())
    def test_duplicate_material_id_is_validation_error(self):
        self.client.force_authenticate(self.teacher)
        self.client.raise_request_exception=False
        result=self.client.post('/api/v1/materials/',{'id':'trig','title':'Duplicate','text':'Text','topic':'Geometry','kind':'triangle','grade':9},format='json')
        self.assertEqual(result.status_code,400)
        self.assertNotEqual(Material.objects.get(pk='trig').title,'Duplicate')
    def test_closed_session_cannot_accept_more_turns(self):
        session=LearningSession.objects.create(user=self.student,title='Completed',completed=True)
        with patch('ai_service.main.tutor_reply') as provider:
            result=self.ai.post('/api/v1/tutor/socratic-ask',data={'session_id':str(session.pk),'prompt_question':'Another answer'},headers=self.headers)
        self.assertEqual(result.status_code,409);provider.assert_not_called()
    def test_geometry_sync_ownership_and_locked_facts(self):
        other=LearningSession.objects.create(user=self.other,title='Other',completed=True)
        own=LearningSession.objects.create(user=self.student,title='Own',completed=False)
        body={'session_id':str(other.pk),'version':0,'geometry':{'type':'sphere','r':5}}
        self.assertEqual(self.ai.post('/api/v1/Geometry2D/sync',json=body,headers=self.headers).status_code,404)
        body['session_id']=str(own.pk)
        self.assertEqual(self.ai.post('/api/v1/Geometry2D/sync',json=body,headers=self.headers).status_code,409)
    def test_disabled_user_cannot_use_fastapi_token(self):
        self.student.is_active=False;self.student.save()
        with patch('ai_service.main.tutor_reply') as provider:
            result=self.ai.post('/api/v1/tutor/socratic-ask',data={'prompt_question':'Test'},headers=self.headers)
        self.assertEqual(result.status_code,401);provider.assert_not_called()
    def test_invalid_geometry_parameters_rejected(self):
        session=LearningSession.objects.create(user=self.student,title='Own',completed=True)
        for radius in [0,-1,10001]:
            response=self.ai.post('/api/v1/Geometry2D/sync',json={'session_id':str(session.pk),'version':0,'geometry':{'type':'sphere','r':radius}},headers=self.headers)
            self.assertEqual(response.status_code,422)
    def test_private_quiz_not_submittable_by_another_student(self):
        quiz=Quiz.objects.create(user=self.other,kind='sphere',questions=[{'concept':'sphere','question':'Q','options':['A','B','C','D'],'correct':0,'explanation':'E'}])
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(f'/api/v1/quizzes/{quiz.pk}/submit/',{'answers':[0]},format='json').status_code,404)

    def test_external_generation_payload_excludes_student_fields_for_both_providers(self):
        import os
        import json
        from unittest.mock import MagicMock
        from ai_service.providers import generate_learning
        academic={'concept_id':'trig','text':'sin = cạnh đối / cạnh huyền','source':'Giáo trình'}
        context={'contexts':[academic],'student_name':'PRIVATE_STUDENT_SENTINEL','messages':['PRIVATE_CHAT_SENTINEL'],'photo':'PRIVATE_PHOTO_SENTINEL'}
        generated={'summary':'Tỉ số lượng giác','questions':[{'concept':'trig','question':'sin bằng tỉ số nào?','options':['đối/huyền','kề/huyền','đối/kề','kề/đối'],'correct':0,'explanation':'Định nghĩa sin.'}],'exercises':[]}
        for provider in ['gemini','openai']:
            response=MagicMock()
            if provider=='gemini':response.json.return_value={'candidates':[{'content':{'parts':[{'text':json.dumps(generated)}]}}]}
            else:response.json.return_value={'choices':[{'message':{'content':json.dumps(generated)}}]}
            connection=MagicMock();connection.post.return_value=response
            with patch.dict(os.environ,{'CONTENT_PROVIDER':provider,'GEMINI_API_KEY':'test-not-real','GEMINI_MODEL':'test-model','OPENAI_API_KEY':'test-not-real','OPENAI_MODEL':'test-model','OPENAI_BASE_URL':'http://127.0.0.1/mock'}),patch('ai_service.providers.httpx.Client') as client:
                client.return_value.__enter__.return_value=connection
                result,source=generate_learning(context)
            self.assertEqual(source,provider)
            payload=json.dumps(connection.post.call_args.kwargs['json'])
            self.assertIn('sin',payload)
            for private in ['PRIVATE_STUDENT_SENTINEL','PRIVATE_CHAT_SENTINEL','PRIVATE_PHOTO_SENTINEL']:self.assertNotIn(private,payload)

    def test_valid_story_draft_publish_and_http_source_validation(self):
        self.client.force_authenticate(self.teacher)
        draft={'id':'bai-viet-qa-valid','status':'draft','kind':'discovery','paragraphs':['Nội dung thử'],'sources':[],'title':'Bài viết QA'}
        self.assertEqual(self.client.post('/api/v1/stories/',draft,format='json').status_code,200)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/v1/stories/').data,[])
        published={**draft,'status':'published',**{k:'Nội dung hợp lệ' for k in ['theorem','hook','topic','insight','condition','evidence','question','answer']},'formula':'a^2+b^2=c^2','sources':[{'title':'Nguồn kiểm thử','url':'https://example.com/math','scope':'Phạm vi đối chiếu'}]}
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post('/api/v1/stories/',published,format='json').status_code,200)
        self.client.force_authenticate(self.student)
        visible=self.client.get('/api/v1/stories/').data
        self.assertEqual(visible[0]['id'],draft['id']);self.assertEqual(visible[0]['authorId'],str(self.teacher.id))
        self.client.force_authenticate(self.teacher)
        invalid={**published,'sources':[{'title':'Unsafe','url':'javascript:alert(1)','scope':'Test'}]}
        self.assertEqual(self.client.post('/api/v1/stories/',invalid,format='json').status_code,400)
        self.assertEqual(Story.objects.get(pk=draft['id']).data['sources'][0]['url'],'https://example.com/math')

    def test_training_metadata_is_admin_only_and_does_not_launch_training(self):
        from .models import TrainingRun
        payload={'method':'grpo','checkpoint':'/qa/checkpoints/qwen-grpo','metrics':{'accuracy':0.75},'note':'Synthetic QA metadata, not a trained model.'}
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post('/api/v1/training/',payload,format='json').status_code,403)
        profile=Profile.objects.get(user=self.teacher);profile.role='admin';profile.save()
        self.client.force_authenticate(self.teacher)
        with patch('subprocess.Popen') as launch:
            result=self.client.post('/api/v1/training/',payload,format='json')
        self.assertEqual(result.status_code,201);launch.assert_not_called()
        self.assertEqual(TrainingRun.objects.count(),1)
        self.assertEqual(self.client.post('/api/v1/training/',{**payload,'metrics':[]},format='json').status_code,400)
