from django.contrib import admin, messages
from django import forms
from django.core.mail import send_mail
from django.conf import settings
from .models import (
    User,
    Address,
    Company,
    ContactMessage,
    ContactMessageActive,
    ContactMessageArchived,
)


admin.site.register(User)
admin.site.register(Address)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "city", "country", "is_default")
    list_filter = ("country", "is_default")
    search_fields = ("name", "legal_name", "email", "vat_number", "company_number", "city")
    prepopulated_fields = {"slug": ("name",)}


class ContactEmailActionForm(forms.Form):
    # required by admin to populate choices
    action = forms.ChoiceField(label='Action', required=False)
    # keep selected ids when posting the action form
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput, required=False)
    select_across = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput)
    index = forms.IntegerField(required=False, initial=0, widget=forms.HiddenInput)
    subject = forms.CharField(required=False, label='Subject', widget=forms.TextInput(attrs={'size': 60}))
    email_body = forms.CharField(required=False, label='Email message', widget=forms.Textarea(attrs={'rows': 4, 'cols': 80}))


class BaseContactAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'subject', 'short_message')
    list_filter = ('created_at',)
    search_fields = ('subject', 'message', 'user__username', 'user__email')
    ordering = ('-created_at',)

    def short_message(self, obj):
        text = obj.message or ''
        return (text[:60] + '…') if len(text) > 60 else text
    short_message.short_description = 'Message'


@admin.register(ContactMessageActive)
class ContactMessageActiveAdmin(BaseContactAdmin):
    actions = ['archive_selected', 'email_selected']
    action_form = ContactEmailActionForm

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(archived=False)

    def archive_selected(self, request, queryset):
        updated = queryset.update(archived=True)
        self.message_user(request, f'Archived {updated} message(s).', level=messages.SUCCESS)
    archive_selected.short_description = 'Move to archive'

    def email_selected(self, request, queryset):
        subject = request.POST.get('subject') or 'Message from support'
        body = request.POST.get('email_body') or ''
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'no-reply@example.com'
        sent = 0
        for cm in queryset:
            to_email = (getattr(cm.user, 'email', '') or '').strip()
            if to_email:
                try:
                    send_mail(subject, body, from_email, [to_email], fail_silently=False)
                    sent += 1
                except Exception:
                    # continue sending to others
                    pass
        if sent:
            self.message_user(request, f'Sent emails to {sent} recipient(s).', level=messages.SUCCESS)
        else:
            self.message_user(request, 'No emails sent. Check recipients and SMTP settings.', level=messages.WARNING)
    email_selected.short_description = 'Send email to selected users'


@admin.register(ContactMessageArchived)
class ContactMessageArchivedAdmin(BaseContactAdmin):
    actions = ['move_to_active']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(archived=True)

    def move_to_active(self, request, queryset):
        updated = queryset.update(archived=False)
        self.message_user(request, f'Moved {updated} message(s) to active.', level=messages.SUCCESS)
    move_to_active.short_description = 'Move to active'
