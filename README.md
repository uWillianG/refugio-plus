# Refúgio Plus

Sistema web em Django para autenticação de usuários e agendamento de quadras. O projeto inclui fluxo de cadastro e login, recuperação de senha por e-mail, reserva de horários, cancelamento de agendamentos e área administrativa para gestão de reservas e bloqueios.

## Tecnologias

- Python
- Django 6
- PostgreSQL
- HTML, CSS e JavaScript
- uWSGI para deploy

## Estrutura do projeto

```text
.
|-- app/                    # Configuração principal do Django
|-- booking/                # Regras e telas de agendamento
|-- user_authentication/    # Cadastro, login e recuperação de senha
|-- manage.py
|-- requirements.txt
`-- refugio_uwsgi.ini
```

## Funcionalidades

- Cadastro de usuário
- Login e logout
- Recuperação de senha com envio de código por e-mail
- Agendamento de quadras por data, esporte e faixa de horário
- Reserva para usuário autenticado ou visitante
- Cancelamento de reservas
- Área de "meus agendamentos"
- Área administrativa para visualizar reservas
- Bloqueio administrativo de quadras, inclusive bloqueios fixos
- Tratamento de feriados para disponibilidade e preço

## Pré-requisitos

- Python 3.12 ou superior
- PostgreSQL disponível localmente ou em rede
- `pip`

## Instalação

1. Clone o repositório:

```bash
git clone <url-do-repositorio>
cd refugio-plus
```

2. Crie e ative um ambiente virtual:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Crie um banco PostgreSQL para o projeto.

5. Configure as variáveis de ambiente em um arquivo `.env` na raiz do projeto.

## Variáveis de ambiente

O projeto depende das seguintes variáveis:

```env
SECRET_KEY=sua_chave_django
DEBUG=True

DB_NAME=nome_do_banco
DB_USER=usuario_do_banco
DB_PASSWORD=senha_do_banco
DB_HOST=localhost
DB_PORT=5432

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.seu-provedor.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@dominio.com
EMAIL_HOST_PASSWORD=sua-senha-ou-token
DEFAULT_FROM_EMAIL=seu-email@dominio.com
```

## Banco de dados

Após configurar o `.env`, execute as migrações:

```bash
python manage.py migrate
```

Se precisar acessar o admin do Django, crie um superusuário:

```bash
python manage.py createsuperuser
```

Observação: o projeto usa um modelo de usuário customizado (`AUTH_USER_MODEL = 'user_authentication.users'`).

## Executando localmente

Inicie o servidor de desenvolvimento:

```bash
python manage.py runserver
```

Depois acesse:

```text
http://127.0.0.1:8000/login/
```

## Rotas principais

- `/login/`
- `/cadastro/`
- `/menu/`
- `/booking/`
- `/booking/confirmacao/`
- `/booking/meus-agendamentos/`
- `/booking/admin-agendamentos/`
- `/booking/admin-bloqueios/`
- `/admin/`

## Regras de negócio observadas

- Horários disponíveis variam entre dias úteis e fins de semana/feriados.
- O tempo máximo de reserva por agendamento é de 3 horas.
- Há validação de conflito entre reservas e bloqueios.
- Usuários comuns só podem cancelar uma reserva até 1 hora antes do horário marcado.
- Usuários administradores podem visualizar e cancelar agendamentos e gerenciar bloqueios.

## Testes

O projeto possui arquivos de teste nos apps. Para executar:

```bash
python manage.py test
```

## Deploy

Há arquivos de apoio para deploy com uWSGI:

- `refugio_uwsgi.ini`
- `uwsgi_params`

Antes de publicar, revise principalmente:

- `DEBUG`
- `SECRET_KEY`
- credenciais do banco
- configurações de e-mail
- `ALLOWED_HOSTS`

## Observações

- O projeto está configurado com idioma `pt-br` e timezone `America/Sao_Paulo`.
- O cadastro existe em fluxo direto e também contém código para confirmação por e-mail, hoje desativado temporariamente na view de cadastro.
