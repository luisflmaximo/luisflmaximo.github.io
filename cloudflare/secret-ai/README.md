# Secret AI Worker

Este Worker serve de proxy entre a aba `secret` e o Gemini, para que a chave nunca fique exposta no browser.

## O que falta configurar

1. Instalar e autenticar o Wrangler.
2. Entrar nesta pasta:
   - `C:\Users\luisf\Downloads\portefolio\cloudflare\secret-ai`
3. Definir o segredo:
   - `wrangler secret put GEMINI_API_KEY`
4. Publicar o Worker:
   - `wrangler deploy`
5. Copiar o URL final do Worker e colocá-lo em:
   - `C:\Users\luisf\Downloads\portefolio\assets\js\secret-ai-config.js`

## Notas

- O endpoint esperado pelo frontend é o URL com a rota `/recommend`.
- `ALLOWED_ORIGINS` já vem preparado para o domínio de produção.
- `localhost` e `127.0.0.1` são aceites automaticamente para testes locais.
- Se quiseres usar o secret do GitHub chamado `api_key` num workflow, basta mapeá-lo para `GEMINI_API_KEY` no deploy do Worker.
