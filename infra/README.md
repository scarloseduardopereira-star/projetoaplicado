# Infraestrutura (infra as code)

Configurações **reais** do servidor de produção, versionadas para auditoria e
reprodutibilidade. O que está aqui é exatamente o que roda na VM.

| Arquivo | Papel | Destino na VM |
|---|---|---|
| `harden.sh` | Provisiona e endurece a VM do zero (idempotente) | executado uma vez |
| `nginx.conf` | Proxy reverso TLS + PQC + redirect + SNI por IP/hostname | `/etc/nginx/sites-available/tccapp` |
| `fail2ban-jail.local` | Jail SSH: 4 erros → ban 24h | `/etc/fail2ban/jail.local` |
| `tccapp.service` | Serviço Gunicorn (usuário dedicado) | `/etc/systemd/system/tccapp.service` |

## Provisionar do zero

```bash
# em uma VM Ubuntu 26.04 LTS recém-criada, como usuário com sudo:
git clone https://github.com/scarloseduardopereira-star/projetoaplicado.git /tmp/app
cd /tmp/app
sudo APP_IP=<seu_ip_publico> bash infra/harden.sh
```

O script cuida de: pacotes, SSH só por chave, Fail2Ban, firewall (22/80/443),
deploy do app (venv + Gunicorn + systemd), Nginx, e emissão dos certificados
Let's Encrypt para o **IP** (perfil short-lived) e para o **hostname** sslip.io,
com **PQC** (`X25519MLKEM768`) e reload automático do Nginx na renovação.

> Segredos (`SECRET_KEY`, hash da senha) são gerados na VM e gravados em
> `/opt/app/.env` — **nunca** versionados.

## Decisões de segurança

- **SNI por certificado:** o bloco do IP é `default_server`, então conexões ao
  IP puro (sem SNI) recebem o certificado do IP → SSL.org retorna
  *Certificate Trusted: YES*. Conexões via hostname (SNI) recebem o cert do
  hostname → usado no teste do SSL Labs.
- **PQC:** `ssl_ecdh_curve X25519MLKEM768:...` sobre OpenSSL 3.5 habilita a troca
  de chave híbrida pós-quântica sem compilar nada.
- **Least privilege:** firewall no host (iptables) + Security List do provedor,
  apenas 22/80/443; app roda como usuário `appuser` sem shell.
