from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views import View
from .forms import CadastroForm, LoginForm
from .models import users
# from mylist.forms import PrincipalForm

class MenuView(View):

    @staticmethod
    def get(request):
        return render(request, 'menu.html')

@csrf_protect
def cadastro_view(request):
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            user = users(
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email']
            )
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            messages.success(request, 'Cadastro realizado com sucesso!')
            return render(request, 'cadastro.html', {'form': form})
    else:
        form = CadastroForm()
    
    return render(request, 'cadastro.html', {'form': form})

@csrf_protect
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
            else:
                messages.error(request, 'Email ou senha inválidos.')
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Logout realizado com sucesso!')
    return redirect('login')
