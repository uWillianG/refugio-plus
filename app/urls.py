from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from user_authentication.views import *
from booking.views import BookingView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('login/enviar-codigo-recuperacao/', enviar_codigo_recuperacao_view, name='enviar_codigo_recuperacao'),
    path('login/reenviar-codigo-recuperacao/', reenviar_codigo_recuperacao_view, name='reenviar_codigo_recuperacao'),
    path('login/verificar-codigo-recuperacao/', verificar_codigo_recuperacao_view, name='verificar_codigo_recuperacao'),
    path('login/redefinir-senha/', redefinir_senha_view, name='redefinir_senha'),
    path('cadastro/', cadastro_view, name='cadastro'),
    path('cadastro/verificar-codigo/', verificar_codigo_view, name='verificar_codigo'),
    path('cadastro/reenviar-codigo/', reenviar_codigo_view, name='reenviar_codigo'),
    path('menu/', MenuView.as_view(), name='menu'),
    path('booking/', BookingView.as_view(), name='booking'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
