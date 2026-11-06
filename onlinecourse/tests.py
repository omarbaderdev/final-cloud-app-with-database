from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Choice, Course, Enrollment, Question, Submission


class CourseExamTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='learner',
            password='test-password',
        )
        self.course = Course.objects.create(
            name='Test course',
            image='',
            description='Course description',
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
        )
        self.question = Question.objects.create(
            course=self.course,
            content='Test question?',
        )
        self.choice = Choice.objects.create(
            question=self.question,
            content='Correct answer',
            is_correct=True,
        )

    def test_authenticated_course_page_displays_exam(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('onlinecourse:course_details', args=(self.course.id,))
        )

        self.assertContains(response, 'Start Exam')
        self.assertContains(response, 'Test question?')
        self.assertContains(response, 'Correct answer')
        self.assertContains(
            response,
            reverse('onlinecourse:submit', args=(self.course.id,)),
        )

    def test_exam_submission_saves_selected_choices(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('onlinecourse:submit', args=(self.course.id,)),
            {f'choice_{self.choice.id}': str(self.choice.id)},
        )

        submission = Submission.objects.get(enrollment=self.enrollment)
        self.assertRedirects(
            response,
            reverse(
                'onlinecourse:show_exam_result',
                args=(self.course.id, submission.id),
            ),
        )
        self.assertEqual(list(submission.choices.all()), [self.choice])

    def test_result_displays_score_and_answer_feedback(self):
        submission = Submission.objects.create(enrollment=self.enrollment)
        submission.choices.add(self.choice)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                'onlinecourse:show_exam_result',
                args=(self.course.id, submission.id),
            )
        )

        self.assertContains(response, 'You passed the exam with 100%')
        self.assertContains(response, 'Correct answer')
        self.assertContains(response, '50 / 50 points')

    def test_selecting_a_wrong_choice_does_not_earn_question_points(self):
        wrong_choice = Choice.objects.create(
            question=self.question,
            content='Wrong answer',
        )
        submission = Submission.objects.create(enrollment=self.enrollment)
        submission.choices.add(self.choice, wrong_choice)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                'onlinecourse:show_exam_result',
                args=(self.course.id, submission.id),
            )
        )

        self.assertContains(response, 'Your score was 0%')
        self.assertContains(response, '0 / 50 points')

    def test_result_is_not_visible_to_another_user(self):
        submission = Submission.objects.create(enrollment=self.enrollment)
        another_user = get_user_model().objects.create_user(
            username='another-learner',
            password='test-password',
        )
        self.client.force_login(another_user)

        response = self.client.get(
            reverse(
                'onlinecourse:show_exam_result',
                args=(self.course.id, submission.id),
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_submission_rejects_choices_from_another_course(self):
        self.client.force_login(self.user)
        other_course = Course.objects.create(
            name='Other course',
            image='',
            description='Other course description',
        )
        other_question = Question.objects.create(
            course=other_course,
            content='Other question?',
        )
        other_choice = Choice.objects.create(
            question=other_question,
            content='Other answer',
        )

        response = self.client.post(
            reverse('onlinecourse:submit', args=(self.course.id,)),
            {f'choice_{other_choice.id}': str(other_choice.id)},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Submission.objects.exists())
