from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from learning.models import Material,Prerequisite,Profile


class PrerequisiteGradeTests(TestCase):
    def setUp(self):
        teacher=User.objects.create_user('grade_teacher')
        Profile.objects.create(user=teacher,role='educator')
        self.client=APIClient();self.client.force_authenticate(teacher)
        self.foundation=Material.objects.create(id='grade6',title='Nền tảng lớp 6',text='Điểm',topic='Hình học',grade=6,owner=teacher)
        self.later=Material.objects.create(id='grade7',title='Bài lớp 7',text='Tam giác',topic='Hình học',grade=7,owner=teacher)

    def test_cannot_require_a_future_grade(self):
        response=self.client.post('/api/v1/edges/',{'source':'grade7','target':'grade6'},format='json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(Prerequisite.objects.exists())

    def test_prior_grade_is_a_valid_prerequisite(self):
        response=self.client.post('/api/v1/edges/',{'source':'grade6','target':'grade7'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertTrue(Prerequisite.objects.filter(source=self.foundation,target=self.later).exists())

    def test_changing_grade_cannot_reverse_an_existing_prerequisite(self):
        Prerequisite.objects.create(source=self.foundation,target=self.later)
        response=self.client.patch('/api/v1/materials/grade6/',{'grade':8},format='json')
        self.assertEqual(response.status_code,400)
        self.foundation.refresh_from_db();self.assertEqual(self.foundation.grade,6)
