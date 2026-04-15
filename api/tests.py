from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Task, UserProfile


class ApiSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='admin', password='Admin123!', email='admin@example.com')
        UserProfile.objects.create(user=self.user, role=UserProfile.Role.ADMIN)
        self.client = Client()

    def test_login_and_me(self):
        res = self.client.post('/api/auth/login/', data='{"username":"admin","password":"Admin123!"}', content_type='application/json')
        self.assertEqual(res.status_code, 200)
        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200)

    def test_task_create(self):
        self.client.login(username='admin', password='Admin123!')
        res = self.client.post('/api/tasks/', data='{"title":"Test Task","column":"pending"}', content_type='application/json')
        self.assertEqual(res.status_code, 201)
        self.assertTrue(Task.objects.filter(title='Test Task').exists())
