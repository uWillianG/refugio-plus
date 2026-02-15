from django.contrib.auth.backends import BaseBackend
from .models import users

class UsuarioBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = users.objects.get(email=username)
            if user.check_password(password):
                return user
        except users.DoesNotExist:
            return None
        
    def get_user(self, user_id):
        try:
            return users.objects.get(pk=user_id)
        except users.DoesNotExist:
            return None