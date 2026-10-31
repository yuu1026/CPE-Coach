from django.contrib.auth import views as auth
from django.urls import path, re_path
from django.conf import settings
from django.views.static import serve
from coach import views

urlpatterns = [
    # Local development asset route; runserver remains loopback-only.
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'static'}),
    path('login/', auth.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth.LogoutView.as_view(), name='logout'),
    path('', views.index, name='index'),
    path('choose-problem/', views.choose_problem, name='choose_problem'),
    path('problem/<int:pk>/', views.practice, name='practice'),
    path('problem/<int:pk>/completion/', views.mark_completion, name='mark_completion'),
    path('submission/<int:pk>/', views.detail, name='detail'),
]
