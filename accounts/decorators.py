from functools import wraps
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

# Review N16: anonymous users are sent to login with ?next=<current page>.
# Admin access is decided by User.is_admin_user (role ADMIN or superuser, not is_staff).


def customer_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to continue.")
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_customer or request.user.is_admin_user):
            messages.error(request, "Access restricted: This area is designated for customers.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def pharmacy_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in as a Pharmacy Owner to continue.")
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_pharmacy_owner or request.user.is_admin_user):
            messages.error(request, "Access restricted: Only registered Pharmacy Owners can access inventory.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Administrator credentials required.")
            return redirect_to_login(request.get_full_path())
        if not request.user.is_admin_user:
            messages.error(request, "Access denied: Platform Administrator privileges required.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
