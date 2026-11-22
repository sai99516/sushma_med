from django.contrib import admin
from django.urls import include, path
from dashboard.views import home_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('accounts/', include('accounts.urls')),
    path('medicines/', include('medicines.urls')),
    path('pharmacies/', include('pharmacies.urls')),
    path('inventory/', include('inventory.urls')),
    path('requests/', include('requests_app.urls')),
    path('dashboard/', include('dashboard.urls')),
]
