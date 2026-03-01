from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
import uuid

class UsuarioManager(BaseUserManager):
    def create_user(self, email, name, password=None):
        if not email:
            raise ValueError('O usuário deve ter um email')
        
        user = self.model(
            email=self.normalize_email(email),
            name=name,
        )
        
        user.set_password(password)
        user.save(using=self._db)
        return user

class userTypes(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=150, null=True, blank=True)
    
class users(AbstractBaseUser):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=150)
    phone = models.BigIntegerField()
    email = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    user_type = models.ForeignKey(userTypes, on_delete=models.CASCADE, related_name='user_type', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    
    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    def __str__(self):
        return self.email
    
    def set_password(self, raw_password):
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
    
