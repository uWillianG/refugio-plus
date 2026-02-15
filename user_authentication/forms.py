from django import forms
from .models import users

class CadastroForm(forms.ModelForm):
    name = forms.CharField(
        label='Nome',
        widget=forms.TextInput(),
        error_messages={'required': 'Este campo é obrigatório.'}
    )

    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(),
        error_messages={'required': 'Este campo é obrigatório.', 
                        'invalid': 'O e-mail digitado não é válido'}
    )

    phone = forms.IntegerField(
        label='Phone',
        widget=forms.NumberInput(),
        error_messages={'required': 'Este campo é obrigatório.'}
    )

    cpf = forms.IntegerField(
        label='Cpf',
        widget=forms.NumberInput(),
        error_messages={'required': 'Este campo é obrigatório.'}
    )

    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(),
        error_messages={'required': 'Este campo é obrigatório.'}
    )
    password_confirm = forms.CharField(
        label='Confirmar Senha',
        widget=forms.PasswordInput(),
        error_messages={'required': 'Este campo é obrigatório.'}
    )
    
    class Meta:
        model = users
        fields = ['name', 'email',]
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
    
        if password and password_confirm and password != password_confirm:
            error_message = "As senhas não coincidem."
            self.add_error('password', "")
            self.add_error('password_confirm', error_message)

        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(),
        error_messages={'required': 'Este campo é obrigatório.', 
                        'invalid': 'O e-mail digitado não é válido'}
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(),
        error_messages={'required': 'Este campo é obrigatório.'}
    )