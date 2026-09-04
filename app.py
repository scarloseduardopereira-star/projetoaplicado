"""
Protótipo web seguro — Projeto Aplicado: Práticas de Mercado.

Secure by Design / Secure by Default. Sem banco de dados: um usuário fixo
definido por variáveis de ambiente. Mitiga 3 categorias da OWASP Top 10:2025:

  A01 - Broken Access Control ......... @login_required protege /interna
  A07 - Authentication Failures ....... hash Argon2 + rate limit + cookie seguro
  A05 - Security Misconfiguration ..... Talisman (headers, HSTS, força HTTPS)

Nenhum segredo é hardcoded: SECRET_KEY e APP_PASSWORD_HASH vêm do ambiente,
e o app se recusa a iniciar sem eles.
"""

import os

from flask import Flask, flash, redirect, render_template, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import CSRFProtect, FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuração vinda do ambiente (Secure by Default: nada de padrão inseguro)
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY")
APP_USER = os.environ.get("APP_USER", "admin")
APP_PASSWORD_HASH = os.environ.get("APP_PASSWORD_HASH")
APP_ENV = os.environ.get("APP_ENV", "development")
IS_PROD = APP_ENV == "production"

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY não definida. Recusando iniciar com chave insegura. "
        "Defina SECRET_KEY no .env."
    )
if not APP_PASSWORD_HASH:
    raise RuntimeError(
        "APP_PASSWORD_HASH não definida. Gere com: python generate_hash.py"
    )

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,      # cookie inacessível a JS (anti-XSS roubo de sessão)
    SESSION_COOKIE_SAMESITE="Lax",     # mitiga CSRF em navegação cross-site
    SESSION_COOKIE_SECURE=IS_PROD,     # cookie só trafega sob HTTPS em produção
    PERMANENT_SESSION_LIFETIME=1800,   # sessão expira em 30 min
    WTF_CSRF_TIME_LIMIT=3600,
)

# Em produção o app roda atrás do Nginx (TLS). Confia nos cabeçalhos
# X-Forwarded-* para que o Flask saiba que a conexão original é HTTPS.
if IS_PROD:
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ---------------------------------------------------------------------------
# A05 - Security Misconfiguration: headers de segurança, HSTS, CSP, força HTTPS
# ---------------------------------------------------------------------------
Talisman(
    app,
    force_https=IS_PROD,
    strict_transport_security=True,
    strict_transport_security_max_age=31_536_000,  # 1 ano
    strict_transport_security_include_subdomains=True,
    session_cookie_secure=IS_PROD,
    frame_options="DENY",
    # same-origin: envia Referer nas requisições do próprio site (necessário para
    # a verificação estrita de CSRF do Flask-WTF sob HTTPS) e o omite cross-site.
    referrer_policy="same-origin",
    content_security_policy={
        "default-src": "'self'",
        "style-src": "'self'",
        "script-src": "'self'",
        "img-src": "'self'",
        "object-src": "'none'",
        "base-uri": "'none'",
        "frame-ancestors": "'none'",
        "form-action": "'self'",
    },
)

# ---------------------------------------------------------------------------
# CSRF: token obrigatório em todo POST (login e logout)
# ---------------------------------------------------------------------------
csrf = CSRFProtect(app)

# ---------------------------------------------------------------------------
# A07 - rate limit contra força bruta no login
# ---------------------------------------------------------------------------
limiter = Limiter(get_remote_address, app=app, default_limits=[])

# ---------------------------------------------------------------------------
# Autenticação (Flask-Login) — usuário único vindo do ambiente
# ---------------------------------------------------------------------------
ph = PasswordHasher()
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para acessar esta página."


class User(UserMixin):
    def __init__(self, uid):
        self.id = uid


@login_manager.user_loader
def load_user(uid):
    return User(uid) if uid == APP_USER else None


class LoginForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired()])
    password = PasswordField("Senha", validators=[DataRequired()])


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("interna"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("interna"))

    form = LoginForm()
    if form.validate_on_submit():
        # Mensagem de erro genérica: não revela se o usuário existe (A07).
        if form.username.data == APP_USER:
            try:
                ph.verify(APP_PASSWORD_HASH, form.password.data)
                login_user(User(APP_USER))
                return redirect(url_for("interna"))
            except (VerifyMismatchError, InvalidHashError):
                pass
        flash("Usuário ou senha inválidos.")

    return render_template("login.html", form=form)


@app.route("/interna")
@login_required  # A01 - Broken Access Control: bloqueia acesso não autenticado
def interna():
    return render_template("interna.html", user=current_user.id)


@app.route("/logout", methods=["POST"])  # POST + CSRF: evita logout forçado via CSRF
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.")
    return redirect(url_for("login"))


@app.route("/healthz")
def healthz():
    # Endpoint simples para checagem de disponibilidade (usado no deploy/CI).
    return {"status": "ok"}, 200


@app.errorhandler(429)
def ratelimit_handler(_e):
    return (
        render_template(
            "login.html",
            form=LoginForm(),
            error="Muitas tentativas de login. Aguarde 1 minuto e tente de novo.",
        ),
        429,
    )


if __name__ == "__main__":
    # Execução local apenas. Em produção: gunicorn atrás do Nginx.
    app.run(host="127.0.0.1", port=5000, debug=False)
