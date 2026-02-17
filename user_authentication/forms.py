from django import forms
from email_validator import EmailNotValidError, validate_email

from .models import users


class CadastroForm(forms.ModelForm):
    name = forms.CharField(
        label='Nome',
        widget=forms.TextInput(),
        error_messages={'required': 'Este campo e obrigatorio.'},
    )

    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(),
        error_messages={
            'required': 'Este campo e obrigatorio.',
            'invalid': 'O e-mail digitado nao e valido',
        },
    )

    phone = forms.CharField(
        label='Phone',
        widget=forms.TextInput(),
        error_messages={'required': 'Este campo e obrigatorio.'},
    )

    cpf = forms.CharField(
        label='Cpf',
        widget=forms.TextInput(),
        error_messages={'required': 'Este campo e obrigatorio.'},
    )

    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(),
        error_messages={'required': 'Este campo e obrigatorio.'},
    )

    password_confirm = forms.CharField(
        label='Confirmar Senha',
        widget=forms.PasswordInput(),
        error_messages={'required': 'Este campo e obrigatorio.'},
    )

    class Meta:
        model = users
        fields = ['name', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            result = validate_email(email, check_deliverability=False)
        except EmailNotValidError as exc:
            raise forms.ValidationError(str(exc))
        return result.normalized

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        phone_digits = ''.join(filter(str.isdigit, str(phone)))

        if len(phone_digits) not in (10, 11):
            raise forms.ValidationError('Telefone invalido.')

        return int(phone_digits)

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        cpf_digits = ''.join(filter(str.isdigit, str(cpf)))

        if len(cpf_digits) != 11:
            raise forms.ValidationError('CPF invalido.')

        return int(cpf_digits)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'As senhas nao coincidem.')

        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(),
        error_messages={
            'required': 'Este campo e obrigatorio.',
            'invalid': 'O e-mail digitado nao e valido',
        },
    )

    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(),
        error_messages={'required': 'Este campo e obrigatorio.'},
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            result = validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            raise forms.ValidationError('O e-mail digitado nao e valido')
        return result.normalized
