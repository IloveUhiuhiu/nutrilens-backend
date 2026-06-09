"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/accounts/", include("accounts.urls")),
    path("api/v1/admin/accounts/", include("accounts.admin_urls")),
    path("api/v1/admin/auth/", include("accounts.auth_admin_urls")),
    path("api/v1/nutrients/", include("nutrients.urls")),
    path("api/v1/admin/nutrients/", include("nutrients.admin_urls")),
    path("api/v1/inference/", include("inference.urls")),
    path("api/v1/admin/inference/", include("inference.admin_urls")),
    path("api/v1/analysis/", include("analysis.urls")),
    path("api/v1/admin/analysis/", include("analysis.admin_urls")),
    path("api/v1/reports/", include("reports.urls")),
    path("api/v1/admin/reports/", include("reports.admin_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
