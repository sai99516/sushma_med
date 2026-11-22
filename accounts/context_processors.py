def user_notifications_count(request):
    """Context processor exposing unread notification count for authenticated user."""
    if request.user.is_authenticated:
        # Review N39: computed once per request and reused by views via get_unread_count().
        return {'unread_notifications_count': get_unread_count(request)}
    return {'unread_notifications_count': 0}


def get_unread_count(request):
    """Unread notification count, cached on the request so it is queried only once."""
    if not request.user.is_authenticated:
        return 0
    cached = getattr(request, '_unread_notifications_count', None)
    if cached is None:
        from requests_app.models import Notification
        cached = Notification.objects.filter(user=request.user, is_read=False).count()
        request._unread_notifications_count = cached
    return cached


def demo_mode(request):
    """Demo logins are shown only when DEBUG is on (review finding N2)."""
    from django.conf import settings
    return {'show_demo_logins': bool(settings.DEBUG)}
