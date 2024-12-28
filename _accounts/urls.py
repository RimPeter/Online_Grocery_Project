from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path(
        'password_change/', 
        auth_views.PasswordChangeView.as_view(
            template_name='accounts/change_password.html',        # The template where you show the form
            success_url='/accounts/password_change/done/'         # Where to go upon success
        ), 
        name='password_change'
    ),
    path(
        'password_change/done/', 
        auth_views.PasswordChangeDoneView.as_view(
            template_name='accounts/change_password_done.html'    # A simple "Success" page
        ), 
        name='password_change_done'
    ),
    path('delete_account/', views.delete_account, name='delete_account'),
]
