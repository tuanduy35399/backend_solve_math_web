import io
import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TransactionTestCase
from fastapi.testclient import TestClient
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ai_service.main import app
from ai_service.providers import LearningContent
from .models import KnowledgeGap, LearningReport, LearningSession, Material, Profile, Quiz, QuizAttempt

QUESTION = {'concept': 'trig', 'question': 'sin là tỉ số nào?', 'options': ['đối/huyền', 'kề/huyền', 'đối/kề', 'kề/đối'], 'correct': 0, 'explanation': 'Định nghĩa.'}


class AssignmentFlowTests(TransactionTestCase):
    def setUp(self):
        call_command('seed_learning', stdout=io.StringIO())
        Material.objects.filter(pk='trig').update(status='Đã xuất bản', grade=9)
        self.teacher = User.objects.create_user('teacher', password='ComplexPass123!', first_name='Cô Lan')
        self.other_teacher = User.objects.create_user('teacher2', password='ComplexPass123!')
        self.student = User.objects.create_user('student', password='ComplexPass123!', first_name='Nguyễn Văn An')
        self.grade8 = User.objects.create_user('grade8', password='ComplexPass123!')
        Profile.objects.create(user=self.teacher, role='educator')
        Profile.objects.create(user=self.other_teacher, role='educator')
        Profile.objects.create(user=self.student, role='student', grade=9)
        Profile.objects.create(user=self.grade8, role='student', grade=8)
        self.api = APIClient()
        self.ai = TestClient(app)

    def as_user(self, user):
        self.api.force_authenticate(user)
        return {'Authorization': 'Token ' + Token.objects.get_or_create(user=user)[0].key}

    def create_assignment(self, **extra):
        self.as_user(self.teacher)
        body = {'title': 'Bài tập lượng giác', 'material': 'trig', 'grade': 9, 'questions': [QUESTION, {**QUESTION, 'question': 'cos là tỉ số nào?', 'correct': 1}], **extra}
        response = self.api.post('/api/v1/assignments/', body, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def test_draft_publish_take_and_results(self):
        pk = self.create_assignment()
        self.as_user(self.student)
        self.assertFalse(any(q['id'] == pk for q in self.api.get('/api/v1/quizzes/').json()))
        self.assertEqual(self.api.get(f'/api/v1/quizzes/{pk}/').status_code, 404)
        self.as_user(self.teacher)
        self.assertEqual(self.api.post(f'/api/v1/assignments/{pk}/publish/', {'published': True}, format='json').json()['status'], 'published')
        # Published only to the assignment's grade.
        self.as_user(self.grade8)
        self.assertEqual(self.api.get(f'/api/v1/quizzes/{pk}/').status_code, 404)
        self.as_user(self.student)
        listed = [q for q in self.api.get('/api/v1/quizzes/').json() if q['id'] == pk][0]
        self.assertEqual((listed['title'], listed['best_score']), ('Bài tập lượng giác', None))
        self.assertNotIn('correct', self.api.get(f'/api/v1/quizzes/{pk}/').json()['questions'][0])
        result = self.api.post(f'/api/v1/quizzes/{pk}/submit/', {'answers': [1, 1], 'seconds': 30}, format='json')
        self.assertEqual(result.json()['result']['score'], 1)
        self.assertEqual(KnowledgeGap.objects.get(user=self.student, concept_id='trig').errors, 1)
        self.as_user(self.teacher)
        stats = self.api.get(f'/api/v1/assignments/{pk}/results/').json()
        self.assertEqual((stats['attempts'], stats['average']), (1, 50))
        self.assertEqual(stats['questions'][0]['common_wrong'], 'kề/huyền')
        self.assertEqual((stats['students'], stats['student_rows'][0]['name']), (1, 'Nguyễn Văn An'))
        self.assertEqual(self.api.get('/api/v1/statistics/').json()['assignments'][0]['attempts'], 1)
        # Questions are locked once students have answered; deletion would erase their results.
        changed = {'title': 'x', 'material': 'trig', 'grade': 9, 'questions': [QUESTION]}
        self.assertEqual(self.api.patch(f'/api/v1/assignments/{pk}/', changed, format='json').status_code, 400)
        self.assertEqual(self.api.delete(f'/api/v1/assignments/{pk}/').status_code, 400)
        self.assertEqual(self.api.post(f'/api/v1/assignments/{pk}/publish/', {'published': False}, format='json').json()['status'], 'draft')

    def test_validation_and_ownership(self):
        self.as_user(self.teacher)
        bad = {'title': 'x', 'material': 'trig', 'grade': 9, 'questions': [{**QUESTION, 'options': ['a', 'a', 'b', 'c']}]}
        self.assertEqual(self.api.post('/api/v1/assignments/', bad, format='json').status_code, 400)
        self.assertEqual(self.api.post('/api/v1/assignments/', {**bad, 'questions': [{**QUESTION, 'concept': 'khong-co'}]}, format='json').status_code, 400)
        pk = self.create_assignment()
        self.as_user(self.other_teacher)
        self.assertEqual(self.api.get(f'/api/v1/assignments/{pk}/').status_code, 403)
        self.assertEqual(self.api.get('/api/v1/assignments/').json(), [])
        self.as_user(self.student)
        self.assertEqual(self.api.get('/api/v1/assignments/').status_code, 403)

    def test_ai_draft_uses_django_context_without_rag(self):
        headers = self.as_user(self.teacher)
        content = LearningContent(summary='S', questions=[QUESTION])
        with patch.dict(os.environ, {'RAG_ENABLED': 'false'}), patch('ai_service.main.generate_learning', return_value=(content, 'openai')) as generate:
            response = self.ai.post('/api/v1/ai/assignment-draft', json={'concept_id': 'trig', 'count': 3}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['context_source'], 'django')
        self.assertEqual(generate.call_args.kwargs['questions'], 3)
        self.assertEqual(generate.call_args.args[0]['contexts'][0]['concept_id'], 'trig')
        self.assertEqual(Quiz.objects.filter(source='assignment').count(), 0)  # nothing saved before teacher review
        self.assertEqual(self.ai.post('/api/v1/ai/assignment-draft', json={'concept_id': 'trig'}, headers=self.as_user(self.student)).status_code, 403)

    def test_personal_quiz_uses_own_learning_data(self):
        headers = self.as_user(self.student)
        self.assertEqual(self.ai.post('/api/v1/recommend/personal-quiz', headers=headers).status_code, 422)
        pk = self.create_assignment(); Quiz.objects.filter(pk=pk).update(status='published')
        QuizAttempt.objects.create(user=self.student, quiz_id=pk, answers=[2, 1], score=1)
        LearningSession.objects.create(user=self.student, title='t', messages=[{'role': 'student', 'text': 'Vì sao sin không phải kề chia huyền?'}, {'role': 'tutor', 'text': 'Hỏi', 'concept': 'trig'}])
        content = LearningContent(summary='S', questions=[QUESTION])
        with patch('ai_service.main.generate_learning', return_value=(content, 'openai')) as generate:
            response = self.ai.post('/api/v1/recommend/personal-quiz', headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        focus = generate.call_args.kwargs['focus']
        self.assertIn('đối/kề', focus); self.assertIn('Vì sao sin', focus); self.assertIn('bài giáo viên giao', focus)
        self.assertNotIn('Nguyễn Văn An', focus)
        quiz = Quiz.objects.get(pk=response.json()['quiz_id'])
        self.assertEqual((quiz.user, quiz.source), (self.student, 'openai'))
        self.as_user(self.grade8)
        self.assertEqual(self.api.get(f'/api/v1/quizzes/{quiz.pk}/').status_code, 404)

    def test_learning_report_sends_aggregates_only(self):
        headers = self.as_user(self.teacher)
        self.assertEqual(self.ai.post('/api/v1/ai/learning-report', headers=headers).status_code, 422)
        KnowledgeGap.objects.create(user=self.student, concept_id='trig', errors=3)
        reply = {'content': '## Tổng quan\nÍt dữ liệu.', 'focus': [{'concept_id': 'trig', 'title': 'T', 'reason': 'r', 'suggestion': 's'}, {'concept_id': 'bịa', 'title': 'x'}]}
        with patch('ai_service.providers.complete_json', return_value=(reply, 'gemini')) as complete:
            response = self.ai.post('/api/v1/ai/learning-report', headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('Nguyễn Văn An', complete.call_args.args[0])
        self.assertEqual([f['concept_id'] for f in response.json()['focus']], ['trig'])
        self.assertEqual(LearningReport.objects.count(), 1)
        self.as_user(self.teacher)
        self.assertEqual(len(self.api.get('/api/v1/learning-reports/').json()), 1)

    def test_story_source_search_is_for_educators(self):
        with patch('integrations.research.create_report', return_value={'content': '# Nguồn', 'sources': []}) as create:
            response = self.ai.post('/api/v1/research/story-sources', json={'topic': 'Định lý Pythagore'}, headers=self.as_user(self.teacher))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_args.kwargs, {'topic': 'Định lý Pythagore', 'mode': 'story'})
        self.assertEqual(self.ai.post('/api/v1/research/story-sources', json={'topic': 'abc'}, headers=self.as_user(self.student)).status_code, 403)
