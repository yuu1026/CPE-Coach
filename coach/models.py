import uuid
from django.conf import settings
from django.db import models

class Problem(models.Model):
    title = models.CharField(max_length=160, unique=True)
    statement = models.TextField()
    sample_input = models.TextField()
    sample_output = models.TextField()
    category = models.CharField(max_length=50)
    source = models.CharField(max_length=200, default='專案自編教學題，非官方 CPE 題目')
    test_cases = models.JSONField(default=list, blank=True)
    output_comparison = models.CharField(max_length=20, default='exact', choices=[('exact', '文字比對'), ('line_rstrip', '忽略各行結尾空白'), ('float_1e-6', '數值絕對誤差 1e-6')])

class ProblemCompletion(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'problem'], name='unique_owner_completed_problem')]

class Submission(models.Model):
    action = models.CharField(max_length=12, default='combined')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.PROTECT)
    submission_id = models.UUIDField(default=uuid.uuid4)
    code = models.TextField()
    question = models.TextField(blank=True)
    hint_level = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, default='running')
    mode = models.CharField(max_length=20)
    model = models.CharField(max_length=160)
    prompt_version = models.CharField(max_length=30, default='cpe-tutor-v1')
    messages = models.JSONField(default=list)
    answer = models.TextField(blank=True)
    error = models.TextField(blank=True)
    judge_result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['owner', 'submission_id'], name='unique_owner_submission')]
