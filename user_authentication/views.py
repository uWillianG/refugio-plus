import random

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_protect

from .forms import CadastroForm, LoginForm
from .models import users

PENDING_REGISTRATION_KEY = 'pending_registration'
EMAIL_VERIFICATION_CODE_KEY = 'email_verification_code'


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
        'cpf': form.cleaned_data['cpf'],
        'password_hash': make_password(form.cleaned_data['password']),
    }


def _send_verification_email(email, code):
    send_mail(
        subject='Refugio+ - Codigo de verificacao',
        message=(
            'Recebemos uma solicitacao de cadastro no Refugio+.\n\n'
            f'Seu codigo de verificacao e: {code}\n\n'
            'Se voce nao solicitou este cadastro, ignore este email.'
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )


def _clear_pending_registration(request):
    request.session.pop(PENDING_REGISTRATION_KEY, None)
    request.session.pop(EMAIL_VERIFICATION_CODE_KEY, None)


def _cadastro_context(form, request, verification_error='', verification_info='', show_modal=False):
    pending = request.session.get(PENDING_REGISTRATION_KEY)

    return {
        'form': form,
        'show_verification_modal': bool(pending) and show_modal,
        'verification_email': pending.get('email') if pending else '',
        'verification_error': verification_error,
        'verification_info': verification_info,
    }


@csrf_protect
def cadastro_view(request):
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            if users.objects.filter(cpf=form.cleaned_data['cpf']).exists():
                form.add_error('cpf', 'Este CPF ja esta cadastrado.')
                return render(request, 'cadastro.html', _cadastro_context(form, request))

            _save_pending_registration(request, form)

            verification_code = _generate_verification_code()
            request.session[EMAIL_VERIFICATION_CODE_KEY] = verification_code

            try:
                _send_verification_email(form.cleaned_data['email'], verification_code)
            except Exception:
                _clear_pending_registration(request)
                form.add_error(None, 'Nao foi possivel enviar o email de verificacao. Tente novamente.')
                return render(request, 'cadastro.html', {'form': form})

            return render(
                request,
                'cadastro.html',
                _cadastro_context(
                    CadastroForm(),
                    request,
                    verification_info='Codigo enviado. Verifique sua caixa de entrada.',
                    show_modal=True,
                ),
            )
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
        messages.error(request, 'Sua verificacao expirou. Faca o cadastro novamente.')
        return redirect('cadastro')

    informed_code = request.POST.get('verification_code', '').strip()

    if informed_code != expected_code:
        return render(
            request,
            'cadastro.html',
            _cadastro_context(
                CadastroForm(),
                request,
                verification_error='Codigo incorreto. Tente novamente.',
                show_modal=True,
            ),
        )

    try:
        user = users(
            name=pending['name'],
            email=pending['email'],
            phone=pending['phone'],
            cpf=pending['cpf'],
        )
        user.password = pending['password_hash']
        user.save()
    except IntegrityError:
        _clear_pending_registration(request)
        messages.error(request, 'Nao foi possivel concluir o cadastro. Email ou CPF ja cadastrado.')
        return redirect('cadastro')

    _clear_pending_registration(request)
    messages.success(request, 'Cadastro concluido com sucesso. Faca login para continuar.')
    return redirect('login')


@csrf_protect
def reenviar_codigo_view(request):
    if request.method != 'POST':
        return redirect('cadastro')

    pending = request.session.get(PENDING_REGISTRATION_KEY)
    if not pending:
        messages.error(request, 'Nao ha verificacao pendente. Preencha o cadastro novamente.')
        return redirect('cadastro')

    verification_code = _generate_verification_code()
    request.session[EMAIL_VERIFICATION_CODE_KEY] = verification_code

    try:
        _send_verification_email(pending['email'], verification_code)
    except Exception:
        return render(
            request,
            'cadastro.html',
            _cadastro_context(
                CadastroForm(),
                request,
                verification_error='Falha ao reenviar o codigo. Tente novamente.',
                show_modal=True,
            ),
        )

    return render(
        request,
        'cadastro.html',
        _cadastro_context(
            CadastroForm(),
            request,
            verification_info='Codigo reenviado para o seu email.',
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

            messages.error(request, 'Email ou senha invalidos.')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Logout realizado com sucesso!')
    return redirect('login')
