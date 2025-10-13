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
    path('verify_account/', views.verify_account, name='verify_account'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('contact/', views.contact_us, name='contact_us'),
    path('contact/submitted/', views.contact_submitted, name='contact_submitted'),
    path('profile/', views.profile_view, name='profile'),
    # _accounts/urls.py
    path('addresses/', views.manage_addresses, name='manage_addresses'),
    path('addresses/<int:pk>/default/', views.set_default_address, name='set_default_address'),
    path('addresses/<int:pk>/delete/', views.delete_address, name='delete_address')
]
