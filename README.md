# Luís Máximo — Portfolio Site

Site pessoal de portefólio e currículo, construído em HTML/CSS/JS puro, desenhado para funcionar no GitHub Pages.

---

## 📁 Estrutura de Ficheiros

```
portfolio/
├── index.html                  ← Redireciona automaticamente PT/EN
├── 404.html                    ← Página de erro personalizada
├── site.webmanifest            ← Configuração PWA
├── robots.txt                  ← Instruções para motores de busca
├── sitemap.xml                 ← Mapa do site para SEO
├── assets/
│   ├── css/style.css           ← Folha de estilos principal
│   ├── css/tools.css           ← Estilos do catálogo e IA Chat
│   ├── js/main.js              ← JavaScript partilhado
│   ├── js/secret-tools.js      ← Lógica do catálogo e paginação incremental
│   ├── js/secret-ai.js         ← Chatbot e envio de imagem
│   └── images/
│       └── profile.jpg         ← Fotografia de perfil
├── docs/
│   └── CV_Luis_Maximo.pdf      ← CV para download
├── pt/                         ← Versão portuguesa
│   ├── index.html              ← Página inicial
│   ├── projetos/index.html     ← Página de projetos
│   └── curriculo/index.html    ← Página de currículo
├── en/                         ← English version
│   ├── index.html              ← Home page
│   ├── projects/index.html     ← Projects page
│   └── curriculum/index.html   ← Curriculum page
└── secret/
    ├── index.html              ← Launcher leve do catálogo e AI Chat
    ├── tools-data.json         ← Base de dados do catálogo de ferramentas
    └── estudio/
        └── index.html          ← Estúdio de ficheiros em lote
```

---

## 🚀 Como colocar no GitHub Pages

### Passo 1 — Criar conta e repositório no GitHub
1. Vai a [github.com](https://github.com) e cria uma conta.
2. Clica em **"New repository"** no canto superior direito.
3. Nome do repositório: `portefolio` (ou o nome que desejares).
4. Marca como **Public**.
5. Clica em **"Create repository"**.

### Passo 2 — Fazer upload dos ficheiros
1. No repositório criado, clica em **"uploading an existing file"**.
2. Arrasta **todos os ficheiros e pastas** desta pasta para a janela do browser.
3. Escreve uma mensagem de commit (ex.: "Atualização do site") e clica em **"Commit changes"**.

### Passo 3 — Ativar o GitHub Pages
1. No repositório, vai a **Settings** (ícone de engrenagem).
2. No menu lateral, clica em **Pages**.
3. Em "Source", seleciona **"Deploy from a branch"**.
4. Em "Branch", escolhe **"main"** e a pasta **"/ (root)"**.
5. Clica em **Save**.

### Passo 4 — Aceder ao site
Após 1-2 minutos, o teu site estará disponível em:
```
https://luisflmaximo.github.io/portefolio/
```

---

## ✍️ Como atualizar conteúdo

### Adicionar um trabalho académico (PDF)
1. Coloca o ficheiro PDF na pasta `/docs/`
2. Abre o ficheiro `/pt/projetos/index.html` e `/en/projects/index.html`
3. Procura o comentário `EXEMPLO de como ficará um trabalho real`, copia o bloco de exemplo, descomenta-o e preenche os dados do projeto.

### Adicionar embeds do Instagram (Politiza-te)
1. Abre uma publicação do Instagram no computador, clica nos três pontos `···` e escolhe **"Incorporar"**.
2. Copia o código HTML e substitui o conteúdo do slot nos ficheiros `/pt/projetos/index.html` e `/en/projects/index.html`.

### Estúdio de Ficheiros e Catálogo
1. Abre `/secret/index.html`
2. Usa o botão **"Abrir estúdio"** para entrares em `/secret/estudio/`
3. No estúdio podes carregar ficheiros, pastas ou links e processá-los em lote.

---

## 🔍 Página Secreta

A página secreta é ativada clicando **5 vezes** na fotografia de perfil da página inicial.
- Funciona em mobile e PC.
- Não está indexada nos motores de busca (tem `noindex, nofollow`).
- O URL é `/secret/` — abre o catálogo inteligente que inclui:
  - **Catálogo de Ferramentas:** Mais de 2150 recursos organizados por categorias e secções com paginação incremental super fluida.
  - **Estúdio de Ficheiros:** Ferramenta avançada para gestão e download de recursos em lote.
  - **Assistente IA (Chat):** Chatbot integrado multimodal (`gemini-3.1-flash-lite-preview` via Cloudflare Worker) que recomenda itens do catálogo. Suporta anexo e colagem de imagens (`Ctrl+V`) e chips de prompt rápidos.

---

## 📱 Compatibilidade
- ✅ Chrome, Firefox, Safari, Edge
- ✅ iOS Safari (iPhone/iPad)
- ✅ Android Chrome
- ✅ Responsive em todos os tamanhos de ecrã
