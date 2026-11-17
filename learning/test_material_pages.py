from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from learning.models import Material,Profile


class MaterialPageTests(TestCase):
    def setUp(self):
        self.teacher=User.objects.create_user('page_teacher')
        Profile.objects.create(user=self.teacher,role='educator')
        other=User.objects.create_user('other_teacher')
        Profile.objects.create(user=other,role='educator')
        for i in range(25):
            Material.objects.create(id=f'lesson-{i:02}',title=f'Đường tròn {i:02}',text='Nội dung đầy đủ',topic='Hình học',grade=9,kind='general',owner=self.teacher,status='Bản nháp' if i==24 else 'Đã xuất bản',corpus_metadata={'review_status':'approved','sections':{'example':'x'*3000}} if i%2==0 else {})
        Material.objects.create(id='private-other',title='Bài riêng',text='Riêng tư',topic='Hình học',owner=other,status='Bản nháp')
        self.client=APIClient();self.client.force_authenticate(self.teacher)

    def test_pages_are_stable_and_return_only_table_fields(self):
        first=self.client.get('/api/v1/materials/?page=1').json()
        last=self.client.get('/api/v1/materials/?page=3').json()
        self.assertEqual(first['count'],25)
        self.assertEqual(len(first['results']),10)
        self.assertEqual(len(last['results']),5)
        self.assertFalse(set(m['id'] for m in first['results'])&set(m['id'] for m in last['results']))
        self.assertNotIn('text',first['results'][0])
        self.assertNotIn('corpus_metadata',first['results'][0])
        self.assertIn('review_status',first['results'][0])
        self.assertEqual(self.client.get('/api/v1/materials/?page=4').status_code,404)

    def test_publication_and_review_filters_are_independent(self):
        approved=self.client.get('/api/v1/materials/',{'page':1,'review':'approved'}).json()
        pending=self.client.get('/api/v1/materials/',{'page':1,'review':'pending'}).json()
        combined=self.client.get('/api/v1/materials/',{'page':1,'review':'approved','status':'Bản nháp'}).json()
        self.assertEqual(approved['count'],13)
        self.assertEqual(pending['count'],12)
        self.assertEqual(combined['count'],1)
        self.assertEqual(combined['results'][0]['id'],'lesson-24')

    def test_search_folds_vietnamese_and_runs_before_pagination(self):
        result=self.client.get('/api/v1/materials/',{'page':1,'search':'đƯỜNG TRÒN 24'}).json()
        self.assertEqual(result['count'],1)
        self.assertEqual(result['results'][0]['id'],'lesson-24')
        self.assertEqual(self.client.get('/api/v1/materials/?page=1&search=nothing').json()['count'],0)

    def test_brief_catalog_defers_metadata_and_detail_keeps_it(self):
        brief=self.client.get('/api/v1/materials/?brief=1').json()
        self.assertEqual(len(brief),25)
        self.assertNotIn('corpus_metadata',brief[0])
        detail=self.client.get('/api/v1/materials/lesson-00/').json()
        self.assertIn('sections',detail['corpus_metadata'])

    def test_student_cannot_find_private_drafts_through_any_list(self):
        student=User.objects.create_user('page_student');Profile.objects.create(user=student)
        self.client.force_authenticate(student)
        for params in ({'page':1,'status':'Bản nháp'},{'page':1,'search':'Bài riêng'}):
            self.assertEqual(self.client.get('/api/v1/materials/',params).json()['count'],0)
        self.assertEqual(len(self.client.get('/api/v1/materials/?brief=1').json()),24)
        self.assertEqual(self.client.get('/api/v1/materials/private-other/').status_code,404)
