from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from learning.models import Profile

class Command(BaseCommand):
    help='Cấp vai trò bằng CLI cho tài khoản đã tồn tại, không cấp qua đăng ký công khai.'
    def add_arguments(self,parser):
        parser.add_argument('username')
        parser.add_argument('role',choices=['student','educator','admin'])
    def handle(self,username,role,**kwargs):
        try: user=User.objects.get(username=username)
        except User.DoesNotExist: raise CommandError('Tài khoản không tồn tại.')
        profile,_=Profile.objects.get_or_create(user=user);profile.role=role;profile.save()
        from rest_framework.authtoken.models import Token
        Token.objects.filter(user=user).delete()
        self.stdout.write(self.style.SUCCESS('Đã cập nhật vai trò. Đăng nhập lại để sử dụng.'))
