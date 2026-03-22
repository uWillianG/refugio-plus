from django.db import models
from user_authentication.models import users

class courts(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=200)
    
class sports(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    
class schedules(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField()
    start_hour = models.TimeField()
    end_hour = models.TimeField()
    user_id = models.ForeignKey(users, on_delete=models.CASCADE, related_name='user_schedule', null=True, blank=True)
    court_id = models.ForeignKey(courts, on_delete=models.CASCADE, related_name='court_scheduled')
    sport_id = models.ForeignKey(sports, on_delete=models.CASCADE, related_name='sport_scheduled')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    user_name = models.CharField(max_length=150, null=True, blank=True)
    user_phone = models.BigIntegerField(null=True, blank=True)

class court_blocks(models.Model):
    id = models.AutoField(primary_key=True)
    court_id = models.ForeignKey(courts, on_delete=models.CASCADE, related_name='court_blocked')
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=200)
    is_fixed = models.BooleanField(default=False)
    fixed_weekday = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)


class court_block_exceptions(models.Model):
    id = models.AutoField(primary_key=True)
    block_id = models.ForeignKey(court_blocks, on_delete=models.CASCADE, related_name='exceptions')
    skip_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('block_id', 'skip_date')

class holidays(models.Model):
    id = models.AutoField(primary_key=True)
    dates = models.DateField()
    description = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
