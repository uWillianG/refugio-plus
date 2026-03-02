import logging
import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_protect

from .forms import CadastroForm, LoginForm, PasswordResetConfirmForm, PasswordResetRequestForm
from .models import users

PENDING_REGISTRATION_KEY = 'pending_registration'
EMAIL_VERIFICATION_CODE_KEY = 'email_verification_code'
PENDING_PASSWORD_RESET_KEY = 'pending_password_reset'
PASSWORD_RESET_CODE_KEY = 'password_reset_code'
PASSWORD_RESET_VERIFIED_KEY = 'password_reset_verified'
logger = logging.getLogger(__name__)


class MenuView(View):
    @staticmethod
    def get(request):
        return render(request, 'menu.html')


def _generate_verification_code():
    return f'{random.randint(0, 999999):06d}'


def _save_pending_registration(request, form):
    request.session[PENDING_REGISTRATION_KEY] = {
        'name': form.cleaned_data['name'],
        'email': form.cleaned_data['email'],
        'phone': form.cleaned_data['phone'],
        'password_hash': make_password(form.cleaned_data['password']),
    }


def _send_verification_email(email, code):
    send_mail(
        subject='Refúgio Plus - Código de verificação',
        message=(
            'Recebemos uma solicitação de cadastro no Refúgio+.\n\n'
            f'Seu código de verificação é: {code}\n\n'
            'Se voce não solicitou este cadastro, ignore este email.'
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )


def _clear_pending_registration(request):
    request.session.pop(PENDING_REGISTRATION_KEY, None)
    request.session.pop(EMAIL_VERIFICATION_CODE_KEY, None)


def _save_pending_password_reset(request, email):
    request.session[PENDING_PASSWORD_RESET_KEY] = {'email': email}
    request.session[PASSWORD_RESET_VERIFIED_KEY] = False


def _clear_pending_password_reset(request):
    request.session.pop(PENDING_PASSWORD_RESET_KEY, None)
    request.session.pop(PASSWORD_RESET_CODE_KEY, None)
    request.session.pop(PASSWORD_RESET_VERIFIED_KEY, None)


def _send_password_reset_email(email, code):
    send_mail(
        subject='Refúgio Plus - Recuperação de senha',
        message=(
            'Recebemos uma solicitação de recuperação de senha no Refúgio+.\n\n'
            f'Seu código de verificação é: {code}\n\n'
            'Se voce não solicitou a redefinição de senha, ignore este email.'
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )


def _cadastro_context(form, request, verification_error='', verification_info='', show_modal=False):
    pending = request.session.get(PENDING_REGISTRATION_KEY)

    return {
        'form': form,
        'show_verification_modal': bool(pending) and show_modal,
        'verification_email': pending.get('email') if pending else '',
        'verification_error': verification_error,
        'verification_info': verification_info,
    }


def _login_context(form, request, show_modal=False, reset_step='email', reset_error='', reset_info='', reset_email=''):
    pending_reset = request.session.get(PENDING_PASSWORD_RESET_KEY)

    if pending_reset and not reset_email:
        reset_email = pending_reset.get('email', '')

    return {
        'form': form,
        'show_password_reset_modal': show_modal,
        'password_reset_step': reset_step,
        'password_reset_error': reset_error,
        'password_reset_info': reset_info,
        'password_reset_email': reset_email,
    }


@csrf_protect
def cadastro_view(request):
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            try:
                user = users(
                    name=form.cleaned_data['name'],
                    email=form.cleaned_data['email'],
                    phone=form.cleaned_data['phone'],
                )
                user.password = make_password(form.cleaned_data['password'])
                user.save()
            except IntegrityError:
                form.add_error(None, 'Não foi possível concluir o cadastro. Dados já utilizados.')
                return render(request, 'cadastro.html', {'form': form})

            messages.success(request, 'Cadastro concluído com sucesso.')
            return redirect('login')

            # Fluxo de confirmação por email desativado temporariamente.
            # _save_pending_registration(request, form)
            # verification_code = _generate_verification_code()
            # request.session[EMAIL_VERIFICATION_CODE_KEY] = verification_code
            #
            # try:
            #     _send_verification_email(form.cleaned_data['email'], verification_code)
            # except Exception as exc:
            #     logger.exception('Falha ao enviar email de verificação no cadastro')
            #     _clear_pending_registration(request)
            #     error_message = 'Não foi possivel enviar o email de verificação. Tente novamente.'
            #     if settings.DEBUG:
            #         error_message = f'{error_message} Detalhe técnico: {exc}'
            #     form.add_error(None, error_message)
            #     return render(request, 'cadastro.html', {'form': form})
            #
            # return render(
            #     request,
            #     'cadastro.html',
            #     _cadastro_context(
            #         CadastroForm(),
            #         request,
            #         show_modal=True,
            #     ),
            # )
    else:
        form = CadastroForm()

    return render(request, 'cadastro.html', _cadastro_context(form, request))


@csrf_protect
def verificar_codigo_view(request):
    if request.method != 'POST':
        return redirect('cadastro')

    pending = request.session.get(PENDING_REGISTRATION_KEY)
    expected_code = request.session.get(EMAIL_VERIFICATION_CODE_KEY)

    if not pending or not expected_code:
        messages.error(request, 'Sua verificação expirou. Faça o cadastro novamente.')
        return redirect('cadastro')

    informed_code = request.POST.get('verification_code', '').strip()

    if informed_code != expected_code:
        return render(
            request,
            'cadastro.html',
            _cadastro_context(
                CadastroForm(),
                request,
                verification_error='Código incorreto. Tente novamente.',
                show_modal=True,
            ),
        )

    try:
        user = users(
            name=pending['name'],
            email=pending['email'],
            phone=pending['phone'],
        )
        user.password = pending['password_hash']
        user.save()
    except IntegrityError:
        _clear_pending_registration(request)
        messages.error(request, 'Não foi possível concluir o cadastro. Dados já utilizados.')
        return redirect('cadastro')

    _clear_pending_registration(request)
    messages.success(request, 'Cadastro concluído com sucesso.')
    return redirect('login')


@csrf_protect
def reenviar_codigo_view(request):
    if request.method != 'POST':
        return redirect('cadastro')

    pending = request.session.get(PENDING_REGISTRATION_KEY)
    if not pending:
        messages.error(request, 'Não há verificação pendente. Preencha o cadastro novamente.')
        return redirect('cadastro')

    verification_code = _generate_verification_code()
    request.session[EMAIL_VERIFICATION_CODE_KEY] = verification_code

    try:
        _send_verification_email(pending['email'], verification_code)
    except Exception as exc:
        logger.exception('Falha ao reenviar email de verificação')
        error_message = 'Falha ao reenviar o código. Tente novamente.'
        if settings.DEBUG:
            error_message = f'{error_message} Detalhe técnico: {exc}'
        return render(
            request,
            'cadastro.html',
            _cadastro_context(
                CadastroForm(),
                request,
                verification_error=error_message,
                show_modal=True,
            ),
        )

    return render(
        request,
        'cadastro.html',
        _cadastro_context(
            CadastroForm(),
            request,
            verification_info='Código reenviado para o seu email.',
            show_modal=True,
        ),
    )


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            user = authenticate(request, username=email, password=password)

            if user is not None:
                login(request, user)
                return redirect('booking')

            messages.error(request, 'Email ou senha inválidos.')
    else:
        form = LoginForm()

    return render(request, 'login.html', _login_context(form, request))


@csrf_protect
def enviar_codigo_recuperacao_view(request):
    if request.method != 'POST':
        return redirect('login')

    form = LoginForm()
    reset_request_form = PasswordResetRequestForm(request.POST)
    if not reset_request_form.is_valid():
        return render(
            request,
            'login.html',
            _login_context(
                form,
                request,
                show_modal=True,
                reset_step='email',
                reset_error=reset_request_form.errors.get('email', ['Email inválido.'])[0],
                reset_email=request.POST.get('email', '').strip(),
            ),
        )

    email = reset_request_form.cleaned_data['email']
    user = users.objects.filter(email=email).first()
    if not user:
        return render(
            request,
            'login.html',
            _login_context(
                form,
                request,
                show_modal=True,
                reset_step='email',
                reset_error='Não foi possível encontrar uma conta com esse e-mail.',
                reset_email=email,
            ),
        )

    _save_pending_password_reset(request, email)
    verification_code = _generate_verification_code()
    request.session[PASSWORD_RESET_CODE_KEY] = verification_code

    try:
        _send_password_reset_email(email, verification_code)
    except Exception as exc:
        logger.exception('Falha ao enviar email de recuperação de senha')
        _clear_pending_password_reset(request)
        error_message = 'Não foi possível enviar o email de verificação. Tente novamente.'
        if settings.DEBUG:
            error_message = f'{error_message} Detalhe técnico: {exc}'
        return render(
            request,
            'login.html',
            _login_context(
                form,
                request,
                show_modal=True,
                reset_step='email',
                reset_error=error_message,
                reset_email=email,
            ),
        )

    return render(
        request,
        'login.html',
        _login_context(
            form,
            request,
            show_modal=True,
            reset_step='code',
            reset_email=email,
        ),
    )


@csrf_protect
def reenviar_codigo_recuperacao_view(request):
    if request.method != 'POST':
        return redirect('login')

    form = LoginForm()
    pending_reset = request.session.get(PENDING_PASSWORD_RESET_KEY)
    if not pending_reset:
        messages.error(request, 'Não há recuperação de senha pendente.')
        return redirect('login')

    email = pending_reset.get('email', '')
    verification_code = _generate_verification_code()
    request.session[PASSWORD_RESET_CODE_KEY] = verification_code
    request.session[PASSWORD_RESET_VERIFIED_KEY] = False

    try:
        _send_password_reset_email(email, verification_code)
    except Exception as exc:
        logger.exception('Falha ao reenviar email de recuperação')
        error_message = 'Falha ao reenviar o código. Tente novamente.'
        if settings.DEBUG:
            error_message = f'{error_message} Detalhe técnico: {exc}'
        return render(
            request,
            'login.html',
            _login_context(
                form,
                request,
                show_modal=True,
                reset_step='code',
                reset_error=error_message,
                reset_email=email,
            ),
        )

    return render(
        request,
        'login.html',
        _login_context(
            form,
            request,
            show_modal=True,
            reset_step='code',
            reset_info='Código reenviado para o seu email.',
            reset_email=email,
        ),
    )


@csrf_protect
def verificar_codigo_recuperacao_view(request):
    if request.method != 'POST':
        return redirect('login')

    form = LoginForm()
    pending_reset = request.session.get(PENDING_PASSWORD_RESET_KEY)
    expected_code = request.session.get(PASSWORD_RESET_CODE_KEY)

    if not pending_reset or not expected_code:
        messages.error(request, 'Sua recuperação expirou. Solicite um novo código.')
        return redirect('login')

    informed_code = request.POST.get('verification_code', '').strip()
    if informed_code != expected_code:
        return render(
            request,
            'login.html',
            _login_context(
                form,
                request,
                show_modal=True,
                reset_step='code',
                reset_error='Código incorreto. Tente novamente.',
            ),
        )

    request.session[PASSWORD_RESET_VERIFIED_KEY] = True
    return render(
        request,
        'login.html',
        _login_context(
            form,
            request,
            show_modal=True,
            reset_step='new_password',
        ),
    )


@csrf_protect
def redefinir_senha_view(request):
    if request.method != 'POST':
        return redirect('login')

    form = LoginForm()
    pending_reset = request.session.get(PENDING_PASSWORD_RESET_KEY)
    is_verified = request.session.get(PASSWORD_RESET_VERIFIED_KEY, False)

    if not pending_reset or not is_verified:
        messages.error(request, 'Sua recuperação expirou. Solicite um novo código.')
        return redirect('login')

    reset_confirm_form = PasswordResetConfirmForm(request.POST)
    if not reset_confirm_form.is_valid():
        field_error = (
            reset_confirm_form.errors.get('password_confirm', [''])[0]
            or reset_confirm_form.errors.get('password', [''])[0]
            or 'Dados inválidos.'
        )
        return render(
            request,
            'login.html',
            _login_context(
                form,
                request,
                show_modal=True,
                reset_step='new_password',
                reset_error=field_error,
            ),
        )

    email = pending_reset.get('email', '')
    user = users.objects.filter(email=email).first()
    if not user:
        _clear_pending_password_reset(request)
        messages.error(request, 'Não foi possível redefinir a senha. Conta nao encontrada.')
        return redirect('login')

    user.password = make_password(reset_confirm_form.cleaned_data['password'])
    user.save(update_fields=['password'])

    _clear_pending_password_reset(request)
    messages.success(request, 'Senha redefinida com sucesso. Faça login com a nova senha.')
    return redirect('login')


def logout_view(request):
    logout(request)
    return redirect('login')
