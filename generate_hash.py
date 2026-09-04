"""
Gera um hash Argon2 para a senha do usuário do app.

Uso:
    python generate_hash.py
    (a senha é lida sem eco no terminal)

Cole a saída no .env como APP_PASSWORD_HASH.
A senha em texto puro nunca é armazenada — só o hash vai para o ambiente.
"""

import getpass

from argon2 import PasswordHasher

if __name__ == "__main__":
    ph = PasswordHasher()
    pw1 = getpass.getpass("Senha: ")
    pw2 = getpass.getpass("Confirme a senha: ")
    if pw1 != pw2:
        raise SystemExit("As senhas não conferem.")
    if len(pw1) < 8:
        raise SystemExit("Use pelo menos 8 caracteres.")
    print("\nAPP_PASSWORD_HASH=" + ph.hash(pw1))
