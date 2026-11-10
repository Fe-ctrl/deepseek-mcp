# deepseek-mcp

Servidor MCP (stdio, só biblioteca padrão do Python) que expõe a DeepSeek como a ferramenta `ask_deepseek(prompt, system_prompt?)`.

## Configuração

- `DEEPSEEK_API_KEY` (obrigatória): a chave nunca vai para o repositório.
- `DEEPSEEK_MODEL` (padrão `deepseek-chat`).
- `DEEPSEEK_BASE_URL` (padrão `https://api.deepseek.com`).
- `DEEPSEEK_TIMEOUT` (segundos, padrão 300).

## Registro no Claude Code

Registre no escopo do usuário, para não gravar nada no repositório do projeto:

    claude mcp add --scope user deepseek -e DEEPSEEK_API_KEY=... -- python3 /caminho/para/server.py

`examples/mcp.json.example` mostra o formato de `.mcp.json`, caso se prefira o escopo do projeto.

## Subagente

`examples/deepseek-worker.md` é um modelo para `~/.claude/agents/`. Ele usa `model: haiku` e delega a implementação à DeepSeek.

## Atenção

O conteúdo enviado no prompt sai do seu ambiente e vai para a API da DeepSeek. Não envie código sensível sem autorização do dono do projeto.

## Teste

Sem chave, a ferramenta devolve um erro claro em vez de falhar. Teste contra uma API local com `DEEPSEEK_BASE_URL` apontando para um servidor de mentira.
