def user_notifications_count(request):
    """Context processor exposing unread notification count for authenticated user."""
    if request.user.is_authenticated:
        try:
            from requests_app.models import Notification
            count = Notification.objects.filter(user=request.user, is_read=False).count()
            return {'unread_notifications_count': count}
        except Exception:
            return {'unread_notifications_count': 0}
    return {'unread_notifications_count': 0}


def demo_mode(request):
    """Demo logins are shown only when DEBUG is on (review finding N2)."""
    from django.conf import settings
    return {'show_demo_logins': bool(settings.DEBUG)}
