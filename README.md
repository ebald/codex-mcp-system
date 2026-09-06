# codex-mcp-system

`codex-mcp-system` é um servidor MCP local, em Python, que permite a um cliente MCP pedir geração e edição de imagens à capacidade integrada `$imagegen` do Codex. Ele inicia o processo oficial `codex app-server` por `stdio`, usa o login ChatGPT que o próprio Codex gerencia e devolve o arquivo final com metadados e, quando couber, uma prévia MCP inline.

> Projeto pessoal e não oficial. Não é desenvolvido, mantido nem suportado pela OpenAI.

```text
Cliente MCP
  └─ stdio → codex-mcp-system
                └─ stdio/JSONL → codex app-server
                                      └─ login ChatGPT → $imagegen / GPT Image 2
```

## Cota do Codex versus OpenAI API

A geração integrada usa GPT Image 2 e é contabilizada nos limites gerais do Codex associados ao plano ChatGPT. Este projeto remove `OPENAI_API_KEY` apenas do ambiente do subprocesso e bloqueia autenticação `apikey` antes de gerar.

A formulação correta é: **sem cobrança da OpenAI API; descontado da franquia/cota do Codex associada ao plano ChatGPT**. Isso não significa custo monetário zero: a assinatura, a cota e eventuais limites do plano continuam aplicáveis. Não há fallback automático para a API paga.

Documentação oficial consultada:

- [Autenticação do Codex](https://learn.chatgpt.com/pt-BR/docs/auth)
- [Geração integrada de imagens](https://learn.chatgpt.com/pt-BR/docs/image-generation)
- [Codex App Server](https://learn.chatgpt.com/pt-BR/docs/app-server)

## Pré-requisitos

- macOS ou outro sistema com o executável `codex` compatível;
- Python 3.11 ou superior;
- conta ChatGPT com acesso ao Codex e à geração de imagens;
- um cliente compatível com MCP por `stdio`.

O App Server é experimental; esta versão foi validada com `codex-cli 0.153.4`. O servidor MCP usa a linha estável v2 do SDK MCP para Python.

## Instalação

Com `venv` e `pip`:

```bash
cd /Users/baker/repos-own/codex-mcp-system
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e .
```

Para desenvolvimento:

```bash
./.venv/bin/python -m pip install -e '.[dev]'
```

`uv` também funciona:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
```

## Login oficial com ChatGPT

Use o fluxo fornecido pelo Codex; o projeto não implementa OAuth próprio nem lê o armazenamento de credenciais:

```bash
codex login
```

Ou peça ao utilitário para executar o mesmo fluxo e depois rodar o diagnóstico:

```bash
./.venv/bin/codex-mcp-system login
```

## Diagnóstico sem consumo de imagem

```bash
./.venv/bin/codex-mcp-system doctor
```

O `doctor` verifica Python, executável e versão do Codex, inicialização do App Server, `account/read` sanitizado, modo de autenticação, plano quando disponível, presença local de `$imagegen` e escrita no diretório de saída. Ele não gera imagem e nunca mostra email, token, cookie, cabeçalho ou URL OAuth.

Um resultado pronto contém, entre outros campos:

```json
{
  "auth_mode": "chatgpt",
  "imagegen_available": true,
  "api_billing_blocked": true,
  "app_server_initialized": true,
  "doctor_ok": true
}
```

## Executar por stdio

```bash
./.venv/bin/codex-mcp-system serve
```

O `stdout` fica reservado exclusivamente ao protocolo MCP. Logs vão para `stderr`. Ao desconectar o cliente, o servidor encerra o App Server filho de forma limpa.

## Configuração de um cliente MCP

Bloco pronto para copiar:

```json
{
  "mcpServers": {
    "codex-mcp-system": {
      "command": "/Users/baker/repos-own/codex-mcp-system/.venv/bin/codex-mcp-system",
      "args": ["serve"],
      "env": {
        "CODEX_MCP_OUTPUT_DIR": "/Users/baker/Pictures/codex-mcp-system"
      }
    }
  }
}
```

Não adicione `OPENAI_API_KEY`. O mesmo exemplo está em `examples/mcp-client-config.json`.

## Ferramentas MCP

O servidor publica exatamente quatro ferramentas:

- `codex_account_status`: confirma login, plano, Codex e `$imagegen`;
- `generate_image`: gera uma imagem;
- `edit_image`: edita uma ou mais imagens locais, com máscara opcional;
- `imagegen_status`: informa backend, saída e limites; o probe opcional não consome geração.

Exemplo de `generate_image`:

```json
{
  "prompt": "Um pequeno vaso de cerâmica azul sobre uma mesa clara, luz suave de estúdio.",
  "size": "1024x1024",
  "quality": "medium",
  "background": "opaque",
  "output_format": "png",
  "output_filename": "vaso-azul.png",
  "include_inline": true
}
```

Exemplo de `edit_image`:

```json
{
  "prompt": "Troque apenas o fundo por cinza-claro. Preserve objeto, recorte, sombras e cores.",
  "image_paths": ["/Users/baker/Pictures/produto.png"],
  "mask_path": null,
  "size": "auto",
  "quality": "medium",
  "background": "opaque",
  "output_format": "png",
  "output_filename": "produto-fundo-cinza.png",
  "include_inline": true
}
```

Cada sucesso retorna caminho absoluto, nome, MIME detectado, largura, altura, bytes, backend, confirmação `chatgpt` e aviso de cota. Uma `ImageContent` base64 é incluída até o limite configurado; acima dele, a resposta traz um `ResourceLink` local e sempre mantém o caminho absoluto no objeto estruturado.

## Diretório de saída e configuração

Sem configuração, a saída diária é:

```text
~/Pictures/codex-mcp-system/YYYY-MM-DD/
```

Se `CODEX_MCP_OUTPUT_DIR` for definido, ele é usado como diretório final exato.

| Variável | Padrão | Uso |
|---|---:|---|
| `CODEX_MCP_OUTPUT_DIR` | diretório diário acima | arquivos finais |
| `CODEX_MCP_TIMEOUT_SECONDS` | `600` | timeout total do turno |
| `CODEX_MCP_CODEX_BIN` | `codex` no `PATH` | executável do Codex |
| `CODEX_MCP_LOG_LEVEL` | `INFO` | logs em `stderr` |
| `CODEX_MCP_INLINE_IMAGE_MAX_BYTES` | `2097152` | limite da prévia inline |
| `CODEX_MCP_ALLOW_API_KEY` | `false` obrigatório | qualquer valor `true` bloqueia `serve` e geração |

Suposições documentadas: o override de saída é o diretório final, não recebe sufixo de data; nomes existentes nunca são sobrescritos e ganham `-2`, `-3` etc.; dimensões são requisitos enviados ao backend, mas a dimensão efetiva sempre é medida no arquivo e pode ser normalizada pela geração integrada.

## Segurança e limites

- somente MCP por `stdio`; nenhuma porta, API HTTP ou WebSocket é aberta;
- `OPENAI_API_KEY` é removida apenas do ambiente do App Server filho; o ambiente global e arquivos do usuário não são alterados;
- o projeto não lê `~/.codex/auth.json` nem copia credenciais;
- prompts têm até 8.000 caracteres e são serializados como dados não confiáveis, separados das instruções de desenvolvedor;
- referências aceitas: PNG, JPEG e WebP validados por conteúdo, até 4 arquivos, 20 MiB cada e 50 MiB no total incluindo máscara;
- arquivos animados são rejeitados;
- nomes não aceitam caminhos, absolutos, `..` ou separadores;
- publicação final é atômica e não segue links simbólicos para sobrescrever destinos;
- a versão inicial serializa gerações: um trabalho de imagem por vez;
- o cliente que receber acesso ao servidor poderá consumir a cota do Codex e criar arquivos locais;
- não há relay público, scraping de `chatgpt.com`, reutilização de cookies nem fallback PAYG.

A máscara de edição é enviada pelo tipo oficial `localImage` e descrita semanticamente ao Codex. A versão atual do App Server não expõe um campo de máscara separado em `turn/start`, portanto o recorte exato depende da interpretação da capacidade integrada.

## Smoke test

Este comando faz **uma geração real** em qualidade `low` e consome a cota geral do Codex:

```bash
./.venv/bin/codex-mcp-system smoke-test
```

Não o repita desnecessariamente. Ele se recusa a executar com autenticação `apikey`.

Na prova de conceito de 2026-09-06, o backend `CodexAppServerBackend` gerou com sucesso o cubo vermelho solicitado. O arquivo retornado era PNG válido, 1.687.720 bytes e 1254×1254 pixels; a dimensão efetiva ilustra a normalização mencionada acima.

## Solução de problemas

`Executável 'codex' não encontrado`
: Abra/instale o Codex ou defina `CODEX_MCP_CODEX_BIN` com o caminho absoluto do executável.

`Autenticação por API key detectada e bloqueada`
: Remova `OPENAI_API_KEY` da configuração do cliente MCP e execute `codex login` escolhendo ChatGPT.

`$imagegen não está disponível`
: Confirme plano e políticas do workspace no Codex. O projeto não substitui esse caminho por API paga.

`Limite de uso do Codex atingido`
: Aguarde a renovação indicada pelo produto. O servidor não tenta contornar limites.

`Timeout`
: A geração não é repetida automaticamente depois que o turno começa, pois um retry poderia consumir a cota duas vezes. Aumente `CODEX_MCP_TIMEOUT_SECONDS` apenas para a próxima chamada.

`turn/start` ou evento incompatível
: Atualize o Codex e rode `doctor`. O cliente usa os métodos oficiais e foi construído contra os schemas da versão instalada.

## Confirmar que não usa API key

1. Não inclua `OPENAI_API_KEY` no bloco MCP.
2. Mantenha `CODEX_MCP_ALLOW_API_KEY=false` ou simplesmente omita a variável.
3. Rode `doctor` e confira: `auth_mode: "chatgpt"`, `api_key_forwarded_to_app_server: false`, `api_billing_blocked: true` e `doctor_ok: true`.

O campo `api_key_present_in_parent` é apenas um booleano diagnóstico. Mesmo que outro software tenha definido uma chave no shell pai, o valor nunca é impresso e a chave não é encaminhada ao App Server.

## Desenvolvimento

```bash
./.venv/bin/ruff format --check .
./.venv/bin/ruff check .
./.venv/bin/pytest -q
```

A suíte normal usa um App Server falso e não consome cota. Testes reais ficam fora da execução unitária comum.

## Desinstalação

Remova somente o ambiente virtual e o checkout deste projeto usando o gerenciador de arquivos ou comandos direcionados aos caminhos exatos. Depois remova o bloco `codex-mcp-system` do cliente MCP.

Não execute logout e não apague `~/.codex`: a desinstalação deste projeto não precisa remover, ler nem alterar as credenciais gerenciadas pelo Codex.
