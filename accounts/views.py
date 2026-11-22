import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from pharmacies.services import apply_pharmacy_profile_update, get_pharmacy_for_user
from requests_app.models import Notification
from .context_processors import get_unread_count
from .forms import CustomerRegistrationForm, PharmacyProfileForm, PharmacyRegistrationForm, UserProfileForm
from .services import (
    authenticate_user,
    mark_all_notifications_as_read,
    mark_notification_as_read,
    register_customer,
    register_pharmacy,
)

logger = logging.getLogger('medfind')


def register_customer_view(request):
    """Handles customer account self-registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            try:
                register_customer(form.cleaned_data)
                messages.success(request, "Account created successfully! Please log in to get started.")
                return redirect('login')
            except Exception as e:
                logger.exception("Unexpected error during customer registration")
                messages.error(request, "Registration failed due to a system error. Please try again.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomerRegistrationForm()

    return render(request, 'accounts/register_customer.html', {'form': form})


def register_pharmacy_view(request):
    """Handles pharmacy facility and owner registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = PharmacyRegistrationForm(request.POST)
        if form.is_valid():
            try:
                register_pharmacy(form.cleaned_data)
                messages.success(
                    request,
                    "Pharmacy registration submitted successfully! Your account will be reviewed by an administrator."
                )
                return redirect('login')
            except Exception as e:
                logger.exception("Unexpected error during pharmacy registration")
                messages.error(request, "Registration failed due to a system error. Please try again.")
        else:
            messages.error(request, "Please correct the highlighted form errors.")
    else:
        form = PharmacyRegistrationForm()

    return render(request, 'accounts/register_pharmacy.html', {'form': form})


def _login_rate_keys(request, username):
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    return [f"login-fail:ip:{ip}", f"login-fail:user:{username.lower()}"]


def _login_is_blocked(keys):
    limit = settings.LOGIN_RATE_LIMIT_ATTEMPTS
    return any((cache.get(k) or 0) >= limit for k in keys)


def _login_record_failure(keys):
    window = settings.LOGIN_RATE_LIMIT_WINDOW
    for k in keys:
        if cache.add(k, 1, window):
            continue
        try:
            cache.incr(k)
        except ValueError:
            cache.set(k, 1, window)


def login_view(request):
    """Handles user authentication across all platform roles with safe redirect validation."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Review known #6: simple cache-based login rate limit (per IP and per username).
        rate_keys = _login_rate_keys(request, username)
        if _login_is_blocked(rate_keys):
            logger.warning("Login blocked by rate limit for username: %s", username)
            messages.error(request, "Too many failed login attempts. Please wait a few minutes and try again.")
            return render(request, 'accounts/login.html', status=429)

        user, error_msg = authenticate_user(request, username=username, password=password)
        if user is not None:
            cache.delete_many(rate_keys)
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('dashboard')
        else:
            _login_record_failure(rate_keys)
            messages.error(request, error_msg)

    return render(request, 'accounts/login.html')


@require_POST
def logout_view(request):
    """Logs out the active user via POST only (review known #6) and clears their session."""
    username = request.user.username if request.user.is_authenticated else ''
    logout(request)
    if username:
        logger.info("User logged out: %s", username)
    messages.info(request, "You have been logged out safely.")
    return redirect('home')


@login_required
def profile_view(request):
    """
    Displays and updates the active user's account profile.
    For pharmacy owners, also presents and manages their facility profile without exposing approval toggles.
    """
    pharmacy = None
    if request.user.is_pharmacy_owner:
        pharmacy = get_pharmacy_for_user(request.user)

    if request.method == 'POST':
        action = request.POST.get('action', 'user')

        if action == 'pharmacy' and pharmacy:
            pharmacy_form = PharmacyProfileForm(request.POST, instance=pharmacy)
            user_form = UserProfileForm(instance=request.user)
            if pharmacy_form.is_valid():
                pharmacy, needs_reapproval = apply_pharmacy_profile_update(pharmacy_form, request.user)
                logger.info("Pharmacy profile updated for '%s' by user: %s", pharmacy.pharmacy_name, request.user.username)
                if needs_reapproval:
                    messages.warning(
                        request,
                        "Pharmacy store details updated. Because you changed the name, address or location, "
                        "your pharmacy is hidden from search until an administrator approves it again."
                    )
                else:
                    messages.success(request, "Pharmacy store details updated successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Please correct the errors in the pharmacy details form.")
        else:
            user_form = UserProfileForm(request.POST, instance=request.user)
            pharmacy_form = PharmacyProfileForm(instance=pharmacy) if pharmacy else None
            if user_form.is_valid():
                user_form.save()
                logger.info("User profile updated for user: %s", request.user.username)
                messages.success(request, "Personal profile updated successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Please correct the errors in your personal details form.")
    else:
        user_form = UserProfileForm(instance=request.user)
        pharmacy_form = PharmacyProfileForm(instance=pharmacy) if pharmacy else None

    context = {
        'form': user_form,
        'user_form': user_form,
        'pharmacy_form': pharmacy_form,
        'pharmacy': pharmacy,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def notifications_view(request):
    """Displays user notifications with read/unread filtering, unread counters, and pagination."""
    notifications_qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = get_unread_count(request)  # review N39: shared with the context processor

    filter_type = request.GET.get('filter', '').strip().lower()
    if filter_type == 'unread':
        notifications_qs = notifications_qs.filter(is_read=False)
    elif filter_type == 'read':
        notifications_qs = notifications_qs.filter(is_read=True)
    else:
        filter_type = 'all'

    paginator = Paginator(notifications_qs, 10)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    return render(request, 'accounts/notifications.html', {
        'notifications': page_obj,
        'page_obj': page_obj,
        'unread_count': unread_count,
        'filter_type': filter_type,
        'query_string': query_string,
    })


@login_required
@require_POST
def mark_notification_read(request, pk):
    """Marks an individual notification as read via POST."""
    mark_notification_as_read(pk, request.user)
    messages.success(request, "Notification marked as read.")
    return redirect('notifications')


@login_required
@require_POST
def mark_all_notifications_read_view(request):
    """Marks all unread notifications for the user as read via POST."""
    count = mark_all_notifications_as_read(request.user)
    messages.success(request, f"Marked {count} notification{'s' if count != 1 else ''} as read.")
    return redirect('notifications')
