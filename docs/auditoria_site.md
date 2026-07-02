# Auditoria do site

Data: 2026-07-02  
Projeto: portfolio pessoal de Luis Maximo

## Notas de escopo

Esta auditoria olha para desktop e mobile, mas sem sugerir como prioridade tres coisas que ja tens planeadas:

- adicionar novas linguas;
- automatizar/trocar os embeds de Instagram e LinkedIn;
- criar uma aba dedicada ao Politiza-te.

Tambem tentei validar visualmente no browser integrado, mas a navegacao para o servidor local foi bloqueada por politica de URL. Por isso, esta auditoria baseia-se em leitura do HTML/CSS/JS, validacoes locais de links/assets/metadados e analise responsive pelas regras CSS existentes. Vale a pena fazer uma ultima passagem manual em Chrome/Safari/telemovel real antes de publicar alteracoes.

## Estado apos correcoes de 2026-07-02

Foram corrigidos ou mitigados os pontos mais urgentes que estavam a afetar estrutura, manutencao e experiencia em desktop/mobile:

- corrigido: estrutura HTML do Politiza-te em PT/EN;
- corrigido: bloco CSS duplicado/corrompido no Estudio de ficheiros;
- corrigido: botao "voltar ao topo" da area secret;
- mitigado: acesso direto a area secret, com nova barreira client-side em `assets/js/secret-access.js`;
- corrigido: configuracao da IA alinhada para Groq/GROQ_API_KEY, sem fallback antigo de outro fornecedor;
- corrigido: conflito entre raiz `noindex` e sitemap, tornando a raiz indexavel e mantendo-a como `x-default` no `sitemap.xml`;
- ajustado: espacos laterais globais e do visualizador PDF ficaram menores, mantendo containers centrados;
- corrigido adicionalmente: `document.documentElement.lang` passa a acompanhar PT/EN na area secret;
- corrigido adicionalmente: README deixou de apontar para o Instagram antigo do Politiza-te e deixou de descrever o Worker com fornecedor IA antigo.

Verificacao local executada: estrutura HTML do Politiza-te, ausencia do bloco CSS corrompido, existencia de `--shadow-md`, scripts da area secret, config IA e sitemap. A validacao visual em browser real continua recomendada antes de publicar, porque o browser integrado bloqueou o servidor local nesta sessao.

## Prioridade alta

### 1. Corrigir a estrutura HTML do Politiza-te nas paginas de projetos

Ficheiros:

- `pt/projetos/index.html`
- `en/projects/index.html`

Estado apos alteracao: corrigido. O divisor e o feed voltaram a ser filhos de `.politizate-card` nas duas linguas.

Problema original: o bloco `.politizate-card` fechava antes de `.politizate-card__divider` e `.politizate-card__feed`. Na pratica, o separador e o feed ficavam como filhos de `.container`, nao dentro do cartao. Isto podia explicar margens estranhas, sombras/bordas cortadas e comportamento diferente entre browsers.

Evidencia:

- `pt/projetos/index.html:209-216`
- `en/projects/index.html:216-222`

Sugestao: mover um `</div>` para depois do bloco `.politizate-card__feed`, garantindo esta estrutura:

```html
<div class="politizate-card reveal">
  <div class="politizate-card__top">...</div>
  <div class="politizate-card__divider"></div>
  <div class="politizate-card__feed">...</div>
</div>
```

Mesmo que a aba dedicada ao Politiza-te venha a substituir isto, convem corrigir enquanto a pagina atual existir.

### 2. Corrigir CSS duplicado/corrompido no Estudio de ficheiros

Ficheiro:

- `assets/css/media-studio.css`

Estado apos alteracao: corrigido. Foi removido o bloco duplicado/corrompido e foi adicionada a variavel global `--shadow-md`.

Problema original: havia um bloco suspeito em `.studio-actions` com `display: flex` seguido de `display: grid`, e depois propriedades que pareciam pertencer ao icone da drop-zone.

Evidencia:

- `assets/css/media-studio.css:462-470`
- bloco correto volta a aparecer em `assets/css/media-studio.css:657-662`

Tambem havia duplicacao de blocos como `.drop-zone__icon svg`, `.link-panel`, `.tool-options`, `.studio-metrics` e outros.

Impacto:

- maior risco de comportamento inesperado no mobile;
- manutencao mais dificil;
- estilos finais dependem da ordem acidental do ficheiro;
- possivel layout estranho nos botoes de resultados.

Sugestao original: limpar a zona duplicada e deixar apenas uma definicao coerente por componente. `--shadow-md` ja foi definida em `style.css`.

### 3. Corrigir o botao "voltar ao topo" na area secret

Ficheiro:

- `secret/index.html`

Estado apos alteracao: corrigido. O script espera por `DOMContentLoaded` quando necessario antes de ligar eventos ao botao.

Problema original: o script procurava `#bttBtn` antes do botao existir no DOM.

Evidencia:

- script em `secret/index.html:267-279`
- botao so aparece em `secret/index.html:281-286`

Impacto: o script faz `if (!btn) return;`, portanto o botao provavelmente nunca ganha o comportamento de aparecer ao scroll nem fazer scroll-to-top.

Sugestao: mover o script para depois do botao, ou usar `DOMContentLoaded`, ou integrar esta logica em `secret-tools.js`.

### 4. Tratar a area `secret` como publica, mesmo com noindex

Ficheiros:

- `secret/index.html`
- `secret/tools-data.json`
- `assets/js/secret-ai-config.js`

Estado apos alteracao: mitigado. A area secret agora carrega `assets/js/secret-access.js` em `secret/index.html` e `secret/estudio/index.html`, e `assets/js/secret-tools.js` deixou de desbloquear a sessao automaticamente. Isto reduz acesso direto casual, mas nao substitui autenticacao real num site estatico.

Problema de fundo: a area esta "escondida" pela navegacao e com `noindex`, mas continua num site estatico. Mesmo com a nova barreira client-side, nao deve ser tratada como segura se houver dados sensiveis.

Impacto:

- o catalogo `tools-data.json` fica publico;
- o endpoint do Worker fica publico em `assets/js/secret-ai-config.js`;
- qualquer protecao baseada apenas no clique 7 vezes na foto e `sessionStorage` e apenas uma barreira visual.

Sugestao: se houver dados sensiveis ou custos relevantes de API, proteger com uma camada real: Cloudflare Access, password gate server-side, token temporario, ou pelo menos rate limit e validacao forte no Worker.

### 5. Alinhar nomes e configuracao do Worker IA

Ficheiros:

- `assets/js/secret-ai-config.js`
- `cloudflare/secret-ai/worker.js`
- `cloudflare/secret-ai/wrangler.toml`

Estado apos alteracao: corrigido. O frontend deixou de declarar um modelo antigo inexistente, o Worker usa apenas `GROQ_API_KEY`, e README/guia do Worker foram atualizados para Groq.

Problema original: o frontend declarava um modelo antigo que nao era usado, mas o Worker usava Groq (`https://api.groq.com/openai/v1/chat/completions`) e modelos `llama-*`. Ao mesmo tempo, a secret tinha um nome de fornecedor antigo.

Evidencia:

- frontend: `assets/js/secret-ai-config.js:5-7`
- Worker: `cloudflare/secret-ai/worker.js:8-9`, `cloudflare/secret-ai/worker.js:45-52`, `cloudflare/secret-ai/worker.js:325-329`
- vars Groq: `cloudflare/secret-ai/wrangler.toml`

Impacto: pode funcionar se a secret contiver uma chave Groq, mas fica confuso para debug/deploy e aumenta a chance de configurar a chave errada.

Sugestao original: renomear para `AI_API_KEY` ou `GROQ_API_KEY`, remover `model` do config se nao e usado no frontend, e atualizar textos/README para refletirem a stack real.

## Ajuste de layout aplicado

### Espacos laterais em desktop, mobile e viewer PDF

Ficheiro:

- `assets/css/style.css`

Estado apos alteracao: ajustado. O `--max-w` global passou de `1080px` para `1240px`, os paddings laterais dos containers/nav usam `clamp()` mais curto, e o visualizador PDF passou a usar larguras base maiores com gutters menores em desktop e mobile.

Objetivo: reduzir os vazios laterais sem deixar o texto colado as bordas, mantendo conteudo centrado, alinhado e com leitura confortavel.

## SEO, metadados e indexacao

### 6. Resolver conflito entre sitemap e `noindex` na raiz

Ficheiros:

- `index.html`
- `sitemap.xml`

Estado apos alteracao: corrigido para SEO de nome proprio. A raiz passou a `index, follow`, voltou ao `sitemap.xml` como `x-default`, e as entradas foram atualizadas para `lastmod` 2026-07-02. Isto torna a home tecnica coerente com o objetivo de aparecer em pesquisas por "Luis Maximo" / "Luís Máximo".

Problema original: `index.html` tinha `noindex, nofollow`, mas a raiz aparecia no sitemap com prioridade `1.0`.

Evidencia:

- `index.html:10-11`
- `sitemap.xml:6-12`

Sugestao original: escolher uma estrategia:

- se a raiz e so redirect tecnico, remove-la do sitemap ou baixar prioridade;
- se queres que a raiz seja `x-default` indexavel, remover `noindex` e garantir fallback sem JS forte;
- se queres so PT/EN indexados, deixar raiz fora do sitemap e manter PT/EN como entradas principais.

### 7. Rever `x-default` nas paginas internas

Ficheiro:

- `sitemap.xml`

Problema: todas as paginas internas apontam `hreflang="x-default"` para a home. Exemplo: projetos PT/EN e curriculo PT/EN apontam x-default para `/portefolio/`, nao para uma versao default da propria pagina.

Evidencia:

- `sitemap.xml:39`
- `sitemap.xml:48`
- `sitemap.xml:57`
- `sitemap.xml:66`

Sugestao: para cada cluster PT/EN, usar como x-default a pagina equivalente mais neutra/default. Exemplo para projetos: x-default para `/pt/projetos/` ou `/en/projects/`, nao para a home.

### 8. Corrigir dimensao Open Graph da pagina 404

Ficheiro:

- `404.html`

Problema: `og:image:height` declara `634`, mas `banner-social-pt.jpg` tem `1200x633`.

Evidencia:

- `404.html` declara `og:image:height` 634;
- imagem real em `assets/images/banner-social-pt.jpg`: `1200x633`.

Sugestao: mudar para `633` ou usar a imagem `banner-social.jpg` se quiseres manter `634`.

### 9. Adicionar metadados melhores ao viewer Super Bock

Ficheiro:

- `docs/superbock-viewer.html`

Problema: a pagina tem `noindex`, mas nao tem description/canonical/OG. Se for intencionalmente privada, tudo bem. Se for partilhavel, fica pobre em previews.

Evidencia:

- `docs/superbock-viewer.html:6-8`

Sugestao: decidir se o viewer deve ser partilhavel. Se sim, adicionar description, canonical, OG image, titulo bilingue e talvez `robots: noindex, follow` em vez de `nofollow`.

### 10. Rever manifest/PWA para GitHub Pages

Ficheiro:

- `site.webmanifest`

Problema: `"id": "/"` pode identificar a app como a raiz do dominio, nao necessariamente `/portefolio/`. Para GitHub Pages em subpasta, isto pode ser menos robusto.

Evidencia:

- `site.webmanifest:2`
- `site.webmanifest:8-9`

Sugestao: usar `"id": "/portefolio/"` ou URL absoluto. Tambem pensar se a PWA deve ser so PT ou respeitar a lingua escolhida.

## Performance

### 11. Criar variantes responsivas da fotografia de perfil

Ficheiro:

- `assets/images/profile.jpg`

Problema: a imagem tem `2000x1996` e 221 KB, mas e mostrada a tamanhos muito menores: hero, sidebar do CV e foto circular de 90px.

Sugestao:

- criar `profile-320.webp`, `profile-640.webp`, talvez `profile-1200.webp`;
- usar `srcset` e `sizes`;
- usar uma versao pequena no CV sidebar;
- manter a original so se for mesmo necessaria.

### 12. Remover ou justificar assets aparentemente pesados/nao usados

Ficheiro:

- `assets/images/banner.png`

Problema: `banner.png` tem 903 KB e nao parece ser usado nas paginas principais.

Sugestao: se nao for necessario, remover. Se for usado noutro fluxo, converter para WebP/JPEG otimizado e documentar.

### 13. Otimizar o viewer Super Bock para mobile

Ficheiros:

- `docs/superbock-viewer.html`
- `docs/superbock-pages/`

Problema: o viewer gera 71 figuras/imagens. As paginas WebP somam cerca de 10 MB, e o PDF original tem cerca de 19 MB.

Evidencia:

- `docs/superbock-viewer.html:51`
- `docs/superbock-pages`: 71 ficheiros, cerca de 10.1 MB no total.

Sugestoes:

- carregar so as primeiras paginas e ir adicionando mais com IntersectionObserver;
- adicionar uma navegacao por pagina/indice;
- mostrar peso/tempo estimado em mobile;
- considerar thumbnails + pagina atual em vez de 71 paginas no DOM;
- manter link alternativo para PDF quando o utilizador preferir descarregar.

### 14. Cuidado com embeds e iframes de grande altura

Ficheiros:

- `assets/css/style.css`
- `assets/js/main.js`

O lazy loading dos embeds ja e uma boa decisao. Ainda assim, no mobile o LinkedIn iframe fica com `min-height: 643px`, o que pode dominar o ecra e criar uma pagina muito pesada.

Evidencia:

- `assets/css/style.css:1620`
- `assets/css/style.css:1644`

Sugestao: enquanto os embeds automaticos nao chegam, manter sempre uma versao leve com preview/link e deixar o embed como opcao secundaria.

## Acessibilidade

### 15. O viewer protegido e pouco acessivel por desenho

Ficheiro:

- `docs/superbock-viewer.html`

Problema: as paginas sao imagens com `alt=""`.

Evidencia:

- `docs/superbock-viewer.html:95`

Isto evita copia de texto, mas tambem impede leitores de ecra e pesquisa no documento.

Sugestao: se quiseres manter protecao, acrescentar pelo menos:

- resumo textual acessivel;
- titulo, autor, data e indice;
- contacto para pedir versao acessivel;
- nomes de pagina, por exemplo `aria-label="Pagina 1"` nas figuras.

### 16. A lingua da area secret nao muda semanticamente

Ficheiros:

- `secret/index.html`
- `assets/js/secret-tools.js`

Estado apos alteracao: corrigido. `assets/js/secret-tools.js` passa a atualizar `document.documentElement.lang` conforme a lingua interna escolhida.

Problema original: a pagina secret tem botoes PT/EN e muda textos via JS, mas nao encontrei atualizacao de `document.documentElement.lang`.

Impacto: leitores de ecra, traducao automatica e ferramentas de acessibilidade podem continuar a tratar o conteudo como PT mesmo quando esta em EN.

Sugestao: quando mudares a lingua interna, atualizar tambem `document.documentElement.lang = 'en'` ou `'pt'`.

### 17. Reduzir dependencia de percentagens visuais para skills/languages

Ficheiros:

- `pt/curriculo/index.html`
- `en/curriculum/index.html`

Problema: barras e pontos transmitem nivel, mas nao explicam criterios. Por exemplo, "Gmail Excelente" e "AI 95%" podem soar menos profissionais do que competencias contextualizadas.

Sugestao:

- usar CEFR para linguas: PT nativo, EN B2/C1, FR A1/A2, se aplicavel;
- trocar percentagens por "Avancado", "Intermedio", "Base" com exemplos;
- ou transformar em secoes de competencias demonstradas por projetos.

## Conteudo e posicionamento

### 18. Dar uma acao principal clara na home

Ficheiros:

- `pt/index.html`
- `en/index.html`

Problema: a home mostra identidade, contactos e redes, mas nao tem um CTA primario claro. Para quem chega pela primeira vez, falta uma direcao obvia.

Sugestao:

- botao principal: "Ver projetos";
- botao secundario: "Descarregar CV" ou "Contactar";
- manter redes sociais, mas com menos peso visual do que os objetivos principais.

### 19. Rever exposicao de dados pessoais

Ficheiros:

- `pt/index.html`
- `en/index.html`
- `pt/curriculo/index.html`
- `en/curriculum/index.html`

Problema: data de nascimento, telefone, WhatsApp e email aparecem publicamente e tambem em JSON-LD.

Evidencia:

- data de nascimento: `pt/index.html:174-175`, `en/index.html:193-194`
- telefone/schema: `pt/index.html:50-51`, `en/index.html:50-51`
- WhatsApp publico: varios footers e hero links.

Sugestao: se o objetivo e profissional, ponderar remover data de nascimento e trocar telefone/WhatsApp por email ou LinkedIn. Se quiseres manter WhatsApp, talvez so no CV PDF ou num botao de contacto mais discreto.

### 20. Fortalecer a narrativa "Sobre mim"

Ficheiros:

- `pt/index.html`
- `en/index.html`
- `pt/curriculo/index.html`
- `en/curriculum/index.html`

Sugestao: acrescentar 2-3 frases que respondam a:

- que tipo de oportunidades procuras;
- em que temas te diferencias;
- que provas existem disso: Politiza-te, eventos, marketing, escrita, IA, Excel, comunicacao.

Isto pode ficar na home ou no inicio do CV. Hoje o site diz bem "quem es", mas podia dizer melhor "porque devo continuar a ler".

### 21. Projetos precisam de formato de case study

Ficheiros:

- `pt/projetos/index.html`
- `en/projects/index.html`

Problema: ha pouco contexto sobre processo, contribuicao concreta e resultados.

Sugestao para cada projeto:

- contexto;
- objetivo;
- o teu papel;
- ferramentas/metodos;
- entregaveis;
- resultado/aprendizagem;
- link ou preview.

No projeto Super Bock, por exemplo, podias destacar competencias: diagnostico competitivo, STP, marketing mix, campanha integrada, apresentacao, pesquisa, trabalho em equipa.

### 22. Clarificar o estado do Politiza-te

Ficheiros:

- `pt/projetos/index.html`
- `en/projects/index.html`

Problema: aparece "Projeto em Curso", mas a funcao esta datada como junho 2024 a maio 2025.

Sugestao: se o projeto continua mas o teu cargo terminou, escrever isso explicitamente. Exemplo: "Projeto ativo; cocoordenador entre junho 2024 e maio 2025." Se tu continuas envolvido, atualizar a data para "junho 2024 - presente".

### 23. Reduzir repeticao de redes sociais

O mesmo conjunto de redes aparece na home, footer e paginas internas. Isto nao e errado, mas cria muito ruido.

Sugestao:

- hero: so LinkedIn, Email e talvez CV;
- footer: todos os links pequenos;
- Politiza-te: redes do projeto apenas na pagina/aba dedicada.

### 24. Melhorar microcopy bilingue

Alguns textos em ingles estao corretos, mas soam traduzidos. Exemplos a rever:

- "future perspective" no CV em ingles;
- "political processes" talvez "behind-the-scenes politics" dependendo do tom;
- "download PDF version" pode ser "Download CV as PDF".

Sugestao: fazer uma revisao editorial EN separada, focada em naturalidade.

## Mobile

### 25. Testar menu mobile em todas as paginas depois de cada alteracao

O CSS tem regras mobile para nav (`assets/css/style.css:1567-1588`), e a logica esta em `assets/js/main.js`. Como a nav esta duplicada em varios HTML, um pequeno desvio pode partir uma pagina e nao outra.

Sugestao: checklist manual:

- abrir/fechar menu;
- clicar num link e confirmar que fecha;
- trocar PT/EN;
- confirmar foco visivel;
- testar em 390px e 768px.

### 26. Rever densidade da home no telemovel

No mobile, os botoes sociais ficam em coluna (`assets/css/style.css:1643`). Isto evita overflow, mas pode empurrar o conteudo importante para baixo.

Sugestao: em mobile, mostrar 2-3 acoes principais e esconder o resto num grupo "Mais redes" ou no footer.

### 27. Melhorar a experiencia mobile do Estudio

Ficheiros:

- `secret/estudio/index.html`
- `assets/css/media-studio.css`
- `assets/js/media-studio.js`

Risco: o Estudio e bastante poderoso, mas trabalha com canvas, PDF, FFmpeg, ZIP e ficheiros grandes diretamente no browser. Em mobile isto pode ficar lento ou falhar por memoria.

Sugestoes:

- avisar quando uma ferramenta e pesada em mobile;
- limitar tamanho/quantidade antes de processar;
- mostrar erro amigavel quando o browser nao suporta uma dependencia;
- considerar modo "desktop recomendado" para FFmpeg/PDF pesado;
- para editores visuais, confirmar suporte touch, nao so mouse.

### 28. Cuidado com FABs sobrepostos na area secret

Ficheiro:

- `secret/index.html`

Ha pelo menos tres elementos fixos: IA, Estudio e voltar ao topo. O CSS tenta coordenar isto, mas e fragil em mobile e com safe areas.

Sugestao: no mobile, usar uma unica dock inferior ou menu de acoes, em vez de varios FABs independentes.

## Manutencao

### 29. Reduzir duplicacao de HTML entre PT/EN e paginas

Hoje nav, footer, social links, metadados e JSON-LD estao repetidos em varias paginas. Isto aumenta risco de uma pagina ficar diferente da outra.

Sugestao simples sem framework:

- criar ficheiros de dados JSON/YAML para contactos, redes, paginas e traducoes;
- criar um script pequeno que gera os HTML estaticos;
- ou usar includes via um gerador estatico leve.

Isto tambem vai facilitar as novas linguas que ja tens planeadas.

### 30. Centralizar SEO/social cards

Problema: cada pagina tem muitos metadados repetidos. Isto ja causou pelo menos um mismatch no 404.

Sugestao: criar uma fonte unica para:

- title;
- description;
- canonical;
- OG image e dimensoes;
- hreflang;
- JSON-LD.

### 31. Atualizar README

Ficheiro:

- `README.md`

Problemas originais:

- corrigido: link Politiza-te no README usava `politizate_`, enquanto o site usa `politiza.te`;
- corrigido: README falava num fornecedor IA antigo, mas Worker atual usa Groq;
- a estrutura e as capacidades parecem ter evoluido mais do que a documentacao.

Estado apos alteracao: parcialmente corrigido. O link do Politiza-te e a referencia ao fornecedor IA foram atualizados. A recomendacao de rever a documentacao completa continua valida porque a estrutura da area secret e do Estudio pode continuar a evoluir.

Evidencia:

- `README.md:23`
- `README.md:49`
- `README.md:90`

Sugestao: atualizar README depois de estabilizar a area secret/IA.

### 32. Confirmar ficheiros locais sensiveis no Git

O `.gitignore` tem protecoes para `gemini_api_key.local.txt`, `*api_key*` e `*.local.txt`, o que e bom.

Nao consegui confirmar `git status` porque o comando `git` nao esta disponivel no PATH deste ambiente. Convem confirmares localmente se ficheiros como `gemini_api_key.local.txt`, `current_api_key_status.local.txt` e `current_api_status.json` nao estao tracked.

## Ideias de melhoria por pagina

### Home PT/EN

- Adicionar CTA principal para Projetos e CV.
- Reduzir peso dos links sociais no topo.
- Remover ou esconder data de nascimento.
- Acrescentar pequena narrativa de posicionamento.
- Se o LinkedIn falhar, garantir que a secao ainda tem valor sem iframe.
- Considerar uma secao "Em destaque" com 2 cards: Super Bock e Politiza-te.

### Projetos PT/EN

- Corrigido em 2026-07-02: HTML do Politiza-te.
- Transformar cada projeto em case study.
- Adicionar tags de competencias por projeto.
- Clarificar estado do Politiza-te.
- Na versao EN, indicar de forma mais elegante quando o conteudo esta so em PT.
- Quando criares a aba Politiza-te, deixar Projetos com um card teaser e link para a aba.

### Curriculo PT/EN

- Reescrever "Sobre mim" de forma mais orientada a recrutamento.
- Trocar barras percentuais por niveis/texto verificavel.
- Adicionar achievements: eventos organizados, conteudo publicado, ferramentas usadas, resultados.
- Rever se telefone/data de nascimento devem estar publicos.
- Garantir que o PDF descarregado esta sempre sincronizado com o HTML.
- Usar nomes de ficheiro ASCII como alternativa (`CV_Luis_Maximo_PT.pdf`) para compatibilidade.

### 404

- Corrigir altura OG.
- Adicionar alternativa EN mais completa se o referrer/URL indicar ingles.
- Considerar links para Home, Projetos e CV, nao so Home.

### Viewer Super Bock

- Melhorar acessibilidade minima.
- Carregar paginas de forma incremental.
- Adicionar indice ou navegacao por pagina.
- Rever se `noindex, nofollow` e mesmo o pretendido.
- Nao vender "protegido" como seguranca forte; e uma barreira de UX, nao protecao real.

### Secret / Ferramentas

- Corrigido em 2026-07-02: Back to Top.
- Corrigido em 2026-07-02: atualizar `html lang` quando muda PT/EN.
- Tratar como publico ou adicionar auth real.
- Melhorar mobile com uma barra/dock de acoes.
- Garantir que a pesquisa e filtros continuam rapidos com muitos recursos.
- Rever o fluxo da IA para limite de requests, erros de rede e privacidade de imagens enviadas.

### Estudio

- Corrigido em 2026-07-02: limpar CSS duplicado/corrompido.
- Corrigido em 2026-07-02: definir `--shadow-md`.
- Adicionar limites de tamanho e mensagens mobile.
- Testar touch nos editores visuais.
- Garantir que dependencias CDN falhadas geram mensagens claras.
- Mostrar "desktop recomendado" nas ferramentas com FFmpeg/PDF/canvas pesado.

## Checklist recomendado de QA

Desktop:

- Chrome, Edge ou Firefox em 1366x768 e 1920x1080.
- Navegacao PT/EN.
- Home, Projetos, Curriculo, 404, Viewer, Secret e Estudio.
- Sem scroll horizontal.
- Sem imagens quebradas.
- Sem erros de consola.
- Links externos abrem corretamente.

Mobile:

- 390x844 ou iPhone/Android real.
- Menu abre/fecha em todas as paginas.
- Botoes com area de toque confortavel.
- Sem FABs por cima de conteudo importante.
- Viewer Super Bock nao bloqueia o browser.
- Estudio mostra limites/avisos em tarefas pesadas.
- Footer nao fica demasiado alto nem repetitivo.

SEO/social:

- Validar sitemap depois de mexer em rotas.
- Testar cards com LinkedIn/Post Inspector e X Card Validator.
- Confirmar `hreflang` por cluster.
- Confirmar canonical em todas as paginas indexaveis.

Seguranca/privacidade:

- Confirmar que ficheiros locais de chave nao estao no Git.
- Confirmar rate limiting no Worker.
- Decidir se telefone/data nascimento devem continuar publicos.
- Se `secret` tiver dados privados, adicionar autenticacao real.
