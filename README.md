# Projeto Aplicado: Práticas de Mercado — Protótipo Web Seguro

Protótipo de aplicação web desenvolvido sob os princípios **Secure by Design** e
**Secure by Default**, integrando os três eixos da disciplina:

- ☁️ **Eixo 1 — Infraestrutura:** VM Ubuntu na Oracle Cloud (Free Tier), Nginx, HTTPS.
- 📦 **Eixo 2 — Repositório:** GitHub público, `.gitignore` blindado, sem credenciais versionadas.
- 💻 **Eixo 3 — Desenvolvimento:** app Flask (Python) com login, área interna e logout.
- 🔄 **CI/CD:** GitHub Actions faz o deploy automático a cada `git push origin main`.

> Este README é o relatório técnico da entrega.

---

## 1. Visão geral da aplicação

App mínimo em **Python + Flask**. Sem banco de dados: um único usuário é definido
por variáveis de ambiente (usuário + hash Argon2 da senha). Três telas/rotas:

| Rota        | Método   | Descrição                                              |
|-------------|----------|--------------------------------------------------------|
| `/login`    | GET/POST | Tela de login (formulário com token CSRF)              |
| `/interna`  | GET      | Página interna — **só acessível autenticado**          |
| `/logout`   | POST     | Encerra a sessão (POST + CSRF, evita logout forçado)   |
| `/healthz`  | GET      | Checagem de disponibilidade (usada no deploy/CI)       |

### Estrutura do projeto

```
tcc/
├── app.py               # aplicação Flask
├── templates/
│   ├── login.html       # tela de login
│   └── interna.html     # página interna protegida
├── static/style.css
├── generate_hash.py     # gera o hash Argon2 da senha
├── requirements.txt
├── .gitignore           # impede versionar .env, chaves, DBs
├── .env.example         # modelo de configuração (sem segredos reais)
└── README.md
```

### Pilha tecnológica

| Camada              | Ferramenta        | Papel                                         |
|---------------------|-------------------|-----------------------------------------------|
| Linguagem/framework | Python 3 / Flask  | Servir páginas e lógica                       |
| Autenticação/sessão | Flask-Login       | Sessão e proteção de rotas                    |
| Hash de senha       | argon2-cffi       | Armazenamento seguro da credencial            |
| CSRF                | Flask-WTF         | Token anti-CSRF em todo POST                  |
| Headers/HSTS/HTTPS  | Flask-Talisman    | Cabeçalhos de segurança, HSTS, CSP            |
| Rate limiting       | Flask-Limiter     | Limita tentativas de login (anti brute force) |
| Servidor WSGI (prod)| Gunicorn          | Executa o app atrás do Nginx                  |

---

## 2. Mitigação da OWASP Top 10:2025 (Eixo 3)

A aplicação mitiga ativamente **3 categorias** da
[OWASP Top 10:2025](https://owasp.org/Top10/2025/). Abaixo, o quê, onde e como.

### ✅ A01 — Broken Access Control

**Onde:** `app.py`, rota `interna()` — decorador `@login_required`.

**Como:** a página interna é protegida pelo Flask-Login. Qualquer requisição sem
sessão válida é redirecionada para `/login` (HTTP 302), sem jamais expor o
conteúdo protegido. O logout invalida a sessão, e o acesso posterior à área
interna volta a ser bloqueado.

```python
@app.route("/interna")
@login_required  # bloqueia acesso não autenticado
def interna():
    return render_template("interna.html", user=current_user.id)
```

### ✅ A07 — Authentication Failures

**Onde:** `app.py`, rota `login()` + configuração de sessão + `generate_hash.py`.

**Como (várias camadas):**
- **Senha nunca em texto puro** — armazenada apenas como hash **Argon2**
  (`argon2-cffi`), algoritmo vencedor do Password Hashing Competition.
- **Rate limiting** — `@limiter.limit("5 per minute")` no POST de login corta
  ataques de força bruta (retorna HTTP 429 ao estourar).
- **Mensagem de erro genérica** — "Usuário ou senha inválidos" não revela se o
  usuário existe (evita enumeração de contas).
- **Cookie de sessão endurecido** — `HttpOnly` (inacessível a JS),
  `SameSite=Lax`, e `Secure` em produção (só trafega sob HTTPS). Sessão expira
  em 30 minutos.

### ✅ A05 — Security Misconfiguration

**Onde:** `app.py`, bloco de configuração do `Talisman` e `app.config`.

**Como:** o Flask-Talisman aplica, por padrão, uma configuração endurecida:
- **HSTS** (`Strict-Transport-Security`, 1 ano, includeSubDomains) força o
  navegador a só usar HTTPS.
- **Content-Security-Policy** restritiva (`default-src 'self'`, sem inline
  script/style, `object-src 'none'`, `frame-ancestors 'none'`).
- **X-Frame-Options: DENY** (anti-clickjacking) e **X-Content-Type-Options:
  nosniff**.
- **Redirecionamento forçado para HTTPS** em produção.
- **Sem segredos hardcoded** — `SECRET_KEY` e `APP_PASSWORD_HASH` vêm do
  ambiente; o app **recusa iniciar** com valores padrão inseguros.

> **Defesa extra (bônus):** proteção **CSRF** via Flask-WTF em todos os POSTs
> (login e logout). POST sem token válido é rejeitado com HTTP 400.

### Evidências dos testes

| Cenário testado                          | Resultado esperado | Obtido |
|------------------------------------------|--------------------|--------|
| Login válido                             | 302 → `/interna`   | ✅ 302 |
| Acesso a `/interna` sem login            | 302 → `/login`     | ✅ 302 |
| Logout                                   | 302 → `/login`     | ✅ 302 |
| `/interna` após logout                   | 302 → `/login`     | ✅ 302 |
| POST login sem token CSRF                | 400                | ✅ 400 |
| 6+ logins/minuto                         | 429 (rate limit)   | ✅ 429 |

---

## 3. Como executar localmente

Pré-requisitos: **Python 3.11+**.

```bash
# 1. criar e ativar ambiente virtual
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 2. instalar dependências
pip install -r requirements.txt

# 3. configurar segredos (NUNCA versionar o .env)
cp .env.example .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"   # cole no .env
python generate_hash.py                                                     # cole o APP_PASSWORD_HASH no .env

# 4. rodar
python app.py
# acesse http://127.0.0.1:5000
```

Login de exemplo: usuário `admin` + a senha definida no passo 3.

---

## 4. Infraestrutura — Eixo 1 (Oracle Cloud Free Tier)

> _Seção em construção — preenchida na fase de deploy._

Plano:
- VM **Ubuntu Server LTS** na Oracle Cloud (Free Tier), IP público.
- Acesso remoto **só por chave SSH** (autenticação por senha desabilitada).
- **Fail2Ban** na porta 22 (tolerância de 4 erros → banimento de 24h).
- **Firewall / Security List** com least privilege (expor apenas 80/443).
- **Nginx** como servidor web, proxy reverso para o Gunicorn.
- **HTTPS via Certbot 5.4+** com certificado Let's Encrypt para o IP público,
  autorrenovação ativada, e redirecionamento automático HTTP → HTTPS.
- Meta: **SSL Labs nota A** + **PQC (Post-Quantum Cryptography) ativado**.

_A preencher: IP público, prints da console Oracle, saída do SSL Labs._

---

## 5. CI/CD — GitHub Actions

> _Seção em construção — preenchida na fase de automação._

Plano:
- Workflow `.github/workflows/deploy.yml` disparado em `push` na branch `main`.
- Conexão SSH com a VM usando chave privada guardada em **GitHub Secrets**
  (nenhuma credencial no `.yml`).
- Passos: instalar dependências, reiniciar o serviço Gunicorn, recarregar Nginx.

---

## 6. Segurança do repositório — Eixo 2

- `.gitignore` impede o commit de `.env`, chaves privadas (`*.pem`, `*.key`,
  `id_rsa`, `id_ed25519`), bancos locais e artefatos de ambiente.
- Nenhuma credencial real é versionada — apenas `.env.example` (modelo).
- Recomendado na conta GitHub: **2FA ativado** e uso de chave SSH/PAT para push.
