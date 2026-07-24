# Atualização automática de Instagram e LinkedIn

O workflow `.github/workflows/update-social-data.yml` executa diariamente e também pode ser iniciado manualmente. Atualiza `assets/data/social.json`, que é lido pelo site sem expor tokens no browser.

Enquanto esta alteração estiver apenas na branch de preview, a execução agendada não corre automaticamente: o GitHub só agenda workflows presentes na branch predefinida. É possível testar o workflow manualmente nessa branch. O agendamento diário começa quando a branch for integrada na `main`.

## Instagram

A atualização usa o campo `followers_count` da API oficial Instagram Graph. Cada conta precisa de ser profissional (Business ou Creator), estar ligada a uma Página Meta e ter um token com acesso à respetiva conta.

Adicionar os seguintes segredos em **Settings → Secrets and variables → Actions**:

- `IG_USER_ID_POLITIZA_TE`
- `IG_ACCESS_TOKEN_POLITIZA_TE`
- `IG_USER_ID_TROCA_RESPOSTA`
- `IG_ACCESS_TOKEN_TROCA_RESPOSTA`
- `IG_USER_ID_NOTICIAS_DE_ONTEM`
- `IG_ACCESS_TOKEN_NOTICIAS_DE_ONTEM`
- `IG_USER_ID_POLITOMETRO`
- `IG_ACCESS_TOKEN_POLITOMETRO`

Se o mesmo token tiver acesso às quatro contas, é possível adicionar apenas `META_ACCESS_TOKEN` e manter os quatro `IG_USER_ID_*`.

O projeto Notícias de Ontem ainda não tinha um `INSTAGRAM_PROFILE_URL` configurado nos ficheiros locais. O username inicial ficou como `noticiasdeontem.pt`; a primeira resposta válida da API substitui-o pelo username confirmado.

Quando uma chamada falha, o script preserva o último número válido. Nunca substitui uma métrica conhecida por zero devido a uma falha da API.

## LinkedIn

Adicionar:

- `LINKEDIN_ACCESS_TOKEN`
- `LINKEDIN_AUTHOR_URN` no formato `urn:li:person:...`

O token precisa de acesso autorizado à leitura das publicações do autor através da API Posts do LinkedIn. Este acesso depende dos produtos e permissões aprovados para a aplicação LinkedIn; um token de início de sessão básico pode não ser suficiente.

O site conserva a publicação incorporada atual quando a API não está disponível. Quando a API devolve publicações, o workflow guarda os URLs de incorporação mais recentes e a página inicial passa a mostrar automaticamente a primeira.
