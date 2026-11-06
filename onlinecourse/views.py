from django.shortcuts import render
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from .models import Choice, Course, Enrollment, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import logging
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))


@login_required(login_url='onlinecourse:login')
@require_POST
def submit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    enrollment = get_object_or_404(Enrollment, user=request.user, course=course)

    try:
        selected_ids = [
            int(value)
            for key, value in request.POST.items()
            if key.startswith('choice_')
        ]
    except ValueError:
        return HttpResponseBadRequest('Invalid choice selection.')

    selected_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course,
    )
    if selected_choices.count() != len(selected_ids):
        return HttpResponseBadRequest('Selected choices must belong to this course.')

    submission = Submission.objects.create(enrollment=enrollment)
    submission.choices.set(selected_choices)

    return HttpResponseRedirect(reverse(
        viewname='onlinecourse:show_exam_result',
        args=(course.id, submission.id),
    ))


@login_required(login_url='onlinecourse:login')
def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__user=request.user,
        enrollment__course=course,
    )
    selected_ids = set(submission.choices.values_list('id', flat=True))
    question_results = []
    total_points = 0
    earned_points = 0

    for question in course.question_set.prefetch_related('choice_set').all():
        is_correct = question.is_get_score(selected_ids)
        total_points += question.grade
        points_earned = question.grade if is_correct else 0
        earned_points += points_earned
        choices = [
            {
                'choice': choice,
                'is_selected': choice.id in selected_ids,
            }
            for choice in question.choice_set.all()
        ]
        question_results.append({
            'question': question,
            'choices': choices,
            'is_correct': is_correct,
            'points_earned': points_earned,
        })

    grade = round(earned_points * 100 / total_points) if total_points else 0
    return render(request, 'onlinecourse/exam_result_bootstrap.html', {
        'course': course,
        'submission': submission,
        'question_results': question_results,
        'earned_points': earned_points,
        'total_points': total_points,
        'grade': grade,
    })
