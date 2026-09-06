# Instalação no Claude Code

Este guia mostra como instalar o `codex-mcp-system` como um servidor MCP local no Claude Code. A conexão usa `stdio`: o Claude inicia o servidor automaticamente, e o servidor inicia o Codex App Server usando o login ChatGPT já gerenciado pelo Codex.

> O projeto é pessoal e não oficial. As gerações não usam a OpenAI API: elas descontam da franquia/cota do Codex associada ao plano ChatGPT. Não configure `OPENAI_API_KEY`.

## O que foi instalado neste Mac

A instalação validada em 6 de setembro de 2026 usa:

- Claude Code `2.1.105` em `/Users/baker/.local/bin/claude`;
- `codex-cli 0.153.4` fornecido pelo aplicativo ChatGPT;
- servidor em `/Users/baker/repos-own/codex-mcp-system`;
- ambiente virtual em `/Users/baker/repos-own/codex-mcp-system/.venv`;
- saída em `/Users/baker/Pictures/codex-mcp-system`;
- conexão MCP `codex-mcp-system` no escopo `user`.

O estado final foi confirmado com `claude mcp get codex-mcp-system`: tipo `stdio` e status `Connected`. Também foi feita uma geração real pelo Claude Code, salva como `pelourinho-salvador-hero.png` no diretório de saída.

## 1. Instalar os pré-requisitos

São necessários:

- macOS, Linux ou Windows com Python 3.11 ou superior;
- Claude Code instalado;
- Codex CLI/App Server instalado e autenticado com ChatGPT;
- acesso do plano à capacidade integrada `$imagegen`.

Confira os executáveis:

```bash
python3 --version
claude --version
command -v claude
command -v codex
```

No macOS, quando o Codex vem do aplicativo ChatGPT e não está no `PATH`, o executável normalmente está em:

```text
/Applications/ChatGPT.app/Contents/Resources/codex
```

## 2. Baixar e instalar o servidor

Para uma instalação nova:

```bash
git clone https://github.com/ebald/codex-mcp-system.git
cd codex-mcp-system
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e .
```

Se o repositório já estiver em `/Users/baker/repos-own/codex-mcp-system`, basta executar os quatro últimos comandos a partir dele, sem clonar novamente.

Confirme a instalação:

```bash
./.venv/bin/codex-mcp-system version
```

## 3. Autenticar o Codex com ChatGPT

Use exclusivamente o fluxo oficial:

```bash
codex login
```

Se o executável usado for o incluído no aplicativo ChatGPT para macOS:

```bash
/Applications/ChatGPT.app/Contents/Resources/codex login
```

Não copie tokens, não leia arquivos internos de autenticação e não adicione `OPENAI_API_KEY` à configuração MCP.

## 4. Executar o diagnóstico

No Mac em que esta instalação foi validada:

```bash
CODEX_MCP_CODEX_BIN=/Applications/ChatGPT.app/Contents/Resources/codex \
  /Users/baker/repos-own/codex-mcp-system/.venv/bin/codex-mcp-system doctor
```

O resultado esperado inclui:

```json
{
  "auth_mode": "chatgpt",
  "imagegen_available": true,
  "api_billing_blocked": true,
  "app_server_initialized": true,
  "doctor_ok": true
}
```

`api_billing_blocked: true` é correto: indica que o caminho pago da OpenAI API está bloqueado. O diagnóstico não gera imagem nem consome uma geração.

## 5. Cadastrar o MCP no Claude Code

Este foi o comando executado nesta máquina:

```bash
claude mcp add \
  --env CODEX_MCP_CODEX_BIN=/Applications/ChatGPT.app/Contents/Resources/codex \
  --env CODEX_MCP_OUTPUT_DIR=/Users/baker/Pictures/codex-mcp-system \
  --transport stdio --scope user \
  codex-mcp-system -- \
  /Users/baker/repos-own/codex-mcp-system/.venv/bin/codex-mcp-system serve
```

Significado dos argumentos:

- `--transport stdio`: conecta o cliente diretamente ao processo local, sem abrir porta de rede;
- `--scope user`: disponibiliza o MCP em todos os projetos locais do usuário;
- `codex-mcp-system`: nome mostrado pelo Claude;
- `--`: separa as opções do Claude do comando do servidor;
- `.../codex-mcp-system serve`: executável e subcomando iniciados pelo Claude;
- `CODEX_MCP_CODEX_BIN`: caminho do Codex que contém o App Server;
- `CODEX_MCP_OUTPUT_DIR`: diretório previsível para as imagens finais.

Mantenha `--transport` e `--scope` depois dos argumentos `--env`. Essa ordem evita que algumas versões da CLI interpretem opções posteriores como continuação da variável de ambiente.

Para limitar a conexão somente ao projeto atual, execute o cadastro dentro do projeto e troque `--scope user` por `--scope local`.

### Modelo genérico para outro computador

Substitua os três caminhos absolutos:

```bash
claude mcp add \
  --env CODEX_MCP_CODEX_BIN=/caminho/para/codex \
  --env CODEX_MCP_OUTPUT_DIR=/caminho/para/imagens \
  --transport stdio --scope user \
  codex-mcp-system -- \
  /caminho/para/codex-mcp-system/.venv/bin/codex-mcp-system serve
```

Use caminhos absolutos. O Claude pode iniciar o processo com um diretório de trabalho diferente, por isso caminhos relativos são frágeis nessa configuração.

## 6. Verificar a conexão

No terminal:

```bash
claude mcp get codex-mcp-system
```

O resultado validado foi equivalente a:

```text
codex-mcp-system:
  Scope: User config (available in all your projects)
  Status: ✓ Connected
  Type: stdio
  Command: /Users/baker/repos-own/codex-mcp-system/.venv/bin/codex-mcp-system
  Args: serve
```

Depois do cadastro:

1. Abra uma nova sessão do Claude Code ou reinicie a sessão atual.
2. Execute `/mcp` no Claude Code.
3. Confirme que `codex-mcp-system` aparece conectado.
4. Confirme que estão disponíveis `codex_account_status`, `imagegen_status`, `generate_image` e `edit_image`.

Na aba **Code** do aplicativo Claude, o cadastro feito pela CLI também fica disponível para sessões locais. A tela **Add custom connector**, que exige uma URL HTTPS, destina-se a conectores remotos e não deve ser usada para este servidor local por `stdio`.

## 7. Fazer um teste sem gerar imagem

Envie ao Claude:

> Use `codex-mcp-system` para verificar o estado da conta e da geração de imagens, sem gerar nenhuma imagem.

O resultado correto deve indicar:

```text
ready: true
auth_mode: chatgpt
imagegen_available: true
api_billing_blocked: true
```

As ferramentas `codex_account_status` e `imagegen_status` não geram imagem por padrão.

## 8. Fazer uma geração real

Exemplo equivalente ao teste validado:

> Use `codex-mcp-system` para gerar uma imagem horizontal do Pelourinho, em Salvador, para o hero de um site turístico. Use qualidade low, formato PNG e salve como `pelourinho-salvador-hero.png`. Informe o caminho do arquivo final.

O arquivo será salvo em:

```text
/Users/baker/Pictures/codex-mcp-system/pelourinho-salvador-hero.png
```

Se a imagem exceder o limite de prévia inline, ela continuará salva no disco e o Claude receberá o caminho e os metadados. Geração e edição descontam da cota geral do Codex associada ao plano ChatGPT.

## Atualizar ou corrigir o cadastro

Confira primeiro o estado atual:

```bash
claude mcp get codex-mcp-system
```

Se algum caminho mudou, remova somente o cadastro MCP e execute novamente o comando da etapa 5:

```bash
claude mcp remove "codex-mcp-system" -s user
```

Esse comando não apaga o repositório, as imagens ou as credenciais do Codex.

## Solução de problemas

### O MCP aparece como desconectado

1. Rode o `doctor` diretamente.
2. Confirme que o caminho da `.venv` ainda existe.
3. Confirme o caminho de `CODEX_MCP_CODEX_BIN`.
4. Rode `claude mcp get codex-mcp-system`.
5. Abra uma nova sessão do Claude Code depois de corrigir o cadastro.

### `auth_mode` não é `chatgpt`

Execute `codex login` com a conta ChatGPT. O servidor recusa geração quando detecta autenticação por API key.

### `api_billing_blocked: true`

Não é erro. É a proteção esperada contra fallback acidental para a OpenAI API paga.

### A ferramenta funciona, mas a imagem não aparece inline

Arquivos acima de `CODEX_MCP_INLINE_IMAGE_MAX_BYTES` não são enviados em base64. O caminho absoluto retornado continua válido. O padrão é 2 MiB.

### O Claude pede uma URL HTTPS

Essa é a tela de conectores remotos. Feche-a e faça o cadastro local pelo comando `claude mcp add` da etapa 5.

### JPEG ou WebP foi solicitado, mas o backend devolveu PNG

A geração integrada pode devolver PNG mesmo quando outro formato é solicitado. O servidor valida o formato real e não renomeia conteúdo PNG como JPEG/WebP. Converta depois com uma ferramenta local ou solicite PNG.

## Remover a integração

Remova apenas o cadastro do Claude Code:

```bash
claude mcp remove "codex-mcp-system" -s user
```

Opcionalmente, remova o ambiente virtual do projeto por um método recuperável de sua preferência. Isso não remove nem altera as credenciais administradas pelo Codex.

## Referências

- [Documentação oficial de MCP no Claude Code](https://code.claude.com/docs/en/mcp)
- [README do codex-mcp-system](../README.md)

