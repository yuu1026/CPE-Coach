import uuid
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db import transaction
from .forms import SubmissionForm
from .models import Problem, Submission, ProblemCompletion
from .workflows import submit, thread_records
from .learning import learning_context

def cpe_problems():
    return Problem.objects.filter(category__startswith='CPE ').order_by('title')

def completion_context(owner, problem=None):
    completed = set(ProblemCompletion.objects.filter(owner=owner, problem__in=cpe_problems()).values_list('problem_id', flat=True))
    problems = list(cpe_problems())
    total = len(problems)
    return {'completed_ids': completed, 'completed_count': len(completed), 'problem_count': total, 'completion_percent': round(len(completed) * 100 / total) if total else 0, 'is_completed': problem is not None and problem.pk in completed, 'can_mark_complete': problem is not None and problem.category.startswith('CPE ')} | learning_context(problems, completed, problem)

def workbench_context(record=None):
    result = record.judge_result if record else {}
    cases = result.get('cases', [])
    return {'record': record, 'judge': result, 'ordered_cases': sorted(cases, key=lambda c: c.get('status') == 'accepted'), 'passed_cases': sum(c.get('status') == 'accepted' for c in cases), 'total_cases': len(cases), 'assistant_mode': settings.HINT_MODE, 'active_model': settings.MODEL_NAME if settings.HINT_MODE == 'live' else '固定示範回覆'}

@login_required
@require_http_methods(['POST'])
def test_program(request, pk):
    problem = get_object_or_404(cpe_problems(), pk=pk)
    payload = request.POST.copy()
    payload['action'] = 'test'
    form = SubmissionForm(payload)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    parent_id = form.cleaned_data.get('parent_submission')
    parent = get_object_or_404(Submission, pk=parent_id, owner=request.user, problem=problem) if parent_id else None
    record = submit(request.user, problem, form.cleaned_data, parent)
    # A replay token must never expose another problem's record.
    if record.problem_id != problem.pk or record.action != 'test':
        return JsonResponse({'error':'提交編號已使用，請重新整理後再試。'},status=409)
    context = workbench_context(record) | {'form': form}
    from django.urls import reverse
    return JsonResponse({'html':render_to_string('test_results.html',context,request=request),
        'record':record.pk,'token':str(record.submission_id),'next_token':str(uuid.uuid4()),
        'url':reverse('detail',args=[record.pk]),'code':record.code,
        'custom_test':record.judge_result.get('custom_test'), 'status':record.judge_result.get('status')})

@login_required
@require_http_methods(['POST'])
def clear_chat(request, pk):
    problem = get_object_or_404(cpe_problems(),pk=pk)
    with transaction.atomic():
        Submission.objects.filter(owner=request.user,problem=problem).exclude(action='test').delete()
        latest_test = Submission.objects.filter(owner=request.user,problem=problem,action='test').first()
    from django.urls import reverse
    return JsonResponse({'parent':latest_test.pk if latest_test else '', 'next_token':str(uuid.uuid4()),
        'url':reverse('detail',args=[latest_test.pk]) if latest_test else reverse('practice',args=[problem.pk])})

@login_required
def index(request):
    records = Submission.objects.filter(owner=request.user, problem__in=cpe_problems()).select_related('problem')
    context = completion_context(request.user)
    selected = request.GET.get('track', '')
    if selected not in {group['slug'] for group in context['learning_tracks']}:
        selected = ''
    return render(request, 'index.html', {'history': Paginator(records, 10).get_page(request.GET.get('page')),
        'resume_record': records.first(), 'practiced_count': records.order_by().values('problem_id').distinct().count(),
        'selected_track': selected, 'selected_track_info': next((g for g in context['learning_tracks'] if g['slug'] == selected), None)} | context)

@login_required
@require_http_methods(['POST'])
def mark_completion(request, pk):
    problem = get_object_or_404(cpe_problems(), pk=pk)
    state = request.POST.get('state')
    if state not in ('complete', 'incomplete'):
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('無效的完成狀態。')
    # Validate return target before writing; it can only be this user's same-problem record.
    return_record = None
    value = request.POST.get('return_submission', '')
    if value:
        if not value.isascii() or not value.isdecimal() or len(value) > 10:
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest('無效的回覆紀錄。')
        return_record = get_object_or_404(Submission, pk=int(value), owner=request.user, problem=problem)
    if state == 'complete':
        ProblemCompletion.objects.get_or_create(owner=request.user, problem=problem)
    else:
        ProblemCompletion.objects.filter(owner=request.user, problem=problem).delete()
    return redirect('detail', pk=return_record.pk) if return_record else redirect('practice', pk=problem.pk)

@login_required
@require_http_methods(['GET'])
def choose_problem(request):
    value = request.GET.get('problem', '')
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        return redirect('index')
    problem = get_object_or_404(cpe_problems(), pk=int(value))
    return redirect('practice', pk=problem.pk)

@login_required
@require_http_methods(['GET', 'POST'])
def practice(request, pk):
    problem = get_object_or_404(cpe_problems(), pk=pk)
    form = SubmissionForm(request.POST if request.method == 'POST' else None, initial={'submission_id': uuid.uuid4(), 'hint_level': 1, 'code': ''})
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        parent_id = data.get('parent_submission')
        parent = get_object_or_404(Submission, pk=parent_id, owner=request.user, problem=problem) if parent_id else None
        record = submit(request.user, problem, data, parent)
        return redirect('detail', pk=record.pk)
    return render(request, 'practice.html', {'problem': problem, 'problems': cpe_problems(), 'form': form, 'mode': settings.HINT_MODE} | completion_context(request.user, problem) | workbench_context())

@login_required
@require_http_methods(['GET', 'POST'])
def detail(request, pk):
    record = get_object_or_404(Submission.objects.select_related('problem'), pk=pk, owner=request.user)
    custom = record.judge_result.get('custom_test')
    if custom is None:
        custom = next((c for c in record.judge_result.get('cases', []) if c.get('name') == '自訂測資'), None)
    if custom and not custom.get('enabled', True):
        custom = None
    form = SubmissionForm(request.POST if request.method == 'POST' else None, initial={'submission_id': uuid.uuid4(), 'parent_submission': record.pk, 'hint_level': record.hint_level, 'code': record.code, 'run_custom': bool(custom), 'custom_input': custom['input'] if custom else '', 'custom_expected': custom['expected'] if custom else ''})
    if request.method == 'POST' and form.is_valid():
        if form.cleaned_data.get('parent_submission') not in (None, record.pk):
            form.add_error(None, '回覆對話不符，請重新整理後再試。')
        elif not record.problem.category.startswith('CPE '):
            form.add_error(None, '此題已退出目前題庫，請選擇 CPE 題目。')
        else:
            next_record = submit(request.user, record.problem, form.cleaned_data, record)
            return redirect('detail', pk=next_record.pk)
    return render(request, 'detail.html', {'problem': record.problem, 'problems': cpe_problems(), 'turns': [turn for turn in thread_records(record) if turn.action != 'test'], 'form': form} | completion_context(request.user, record.problem) | workbench_context(record))
