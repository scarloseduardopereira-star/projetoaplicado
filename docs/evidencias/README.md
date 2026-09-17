# Evidências

Comprovações da configuração e dos testes, capturadas **em produção** no
servidor `163.176.123.133`. As imagens de terminal foram renderizadas a partir
da saída **real** dos comandos executados na VM.

| # | Arquivo | Comprova |
|---|---|---|
| 01 | `01-servidor.png` | SO Ubuntu 26.04 LTS, Nginx 1.28 e serviços ativos (app, nginx, fail2ban) |
| 02 | `02-ssh.png` | Acesso SSH só por chave — `passwordauthentication no` |
| 03 | `03-fail2ban.png` | Fail2Ban na porta 22 — `maxretry=4`, `bantime=86400` (24h), IPs banidos |
| 04 | `04-firewall.png` | Firewall least-privilege — apenas 22, 80 e 443 (resto REJECT) |
| 05 | `05-certbot.png` | Certbot 5.8 + certificados Let's Encrypt (IP e hostname) |
| 06 | `06-tls-pqc.png` | TLS 1.3 + PQC (`X25519MLKEM768`) e redirect HTTP→HTTPS (301) |
| 07 | `07-ssl-org.png` | **SSL.org (IP):** Certificate Trusted: YES · Good signature/key |
| 08 | `08-digicert-pqc.png` | **DigiCert PQC (IP):** PASS — quantum-safe key exchange |
| 09 | `09-ssllabs.png` | **SSL Labs (hostname):** nota A+ com suporte a PQC |
| 10 | `10-github-actions.png` | Pipeline CI/CD — run `Success` (test + deploy) |

## Evidências a capturar manualmente (fora do meu alcance)

Estas dependem de acesso a interfaces externas e devem ser anexadas pelo aluno:

- **Console da Oracle Cloud** — a instância em estado *Running* (prova de operação do console do provedor).
- **Uso da IA (Claude)** — 1–2 prints da IA gerando/auditando/refatorando o código.

> Os certificados de IP têm validade curta (renovação automática). Recomenda-se
> recapturar `07`, `08` e `09` pouco antes da apresentação.
