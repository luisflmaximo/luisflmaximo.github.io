# Luís Máximo — Portfolio Site

Site pessoal de portefólio e currículo, construído em HTML/CSS/JS puro, desenhado para funcionar no GitHub Pages.

---

## 📁 Estrutura de Ficheiros

```
portfolio/
├── index.html                  ← Redireciona automaticamente PT/EN
├── 404.html                    ← Página de erro personalizada
├── assets/
│   ├── css/style.css           ← Folha de estilos principal
│   ├── js/main.js              ← JavaScript partilhado
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
    └── index.html              ← Página secreta (5 toques na foto)
```

---

## 🚀 Como colocar no GitHub Pages

### Passo 1 — Criar conta e repositório no GitHub
1. Vai a [github.com](https://github.com) e cria uma conta (se não tiveres)
2. Clica em **"New repository"** (botão verde no canto superior direito)
3. Nome do repositório: `luisflmaximo.github.io` (substitui `luisflmaximo` pelo teu username exato do GitHub)
4. Marca como **Public**
5. Clica **"Create repository"**

### Passo 2 — Fazer upload dos ficheiros
1. No repositório criado, clica em **"uploading an existing file"**
2. Arrasta **todos os ficheiros e pastas** desta pasta para a janela do browser
3. Escreve uma mensagem como "Primeiro commit" no campo em baixo
4. Clica **"Commit changes"**

### Passo 3 — Ativar o GitHub Pages
1. No repositório, vai a **Settings** (ícone de engrenagem)
2. No menu lateral, clica em **Pages**
3. Em "Source", seleciona **"Deploy from a branch"**
4. Em "Branch", escolhe **"main"** e a pasta **"/ (root)"**
5. Clica **Save**

### Passo 4 — Aceder ao site
Após 1-2 minutos, o teu site estará disponível em:
```
https://luisflmaximo.github.io
```
(com o teu username real)

---

## ✏️ Como atualizar conteúdo

### Adicionar um trabalho académico (PDF)
1. Coloca o ficheiro PDF na pasta `/docs/`
2. Abre o ficheiro `/pt/projetos/index.html`
3. Procura o comentário `EXEMPLO de como ficará um trabalho real`
4. Copia o bloco de exemplo, descomenta-o e preenche os dados
5. Faz o mesmo no ficheiro `/en/projects/index.html`

### Adicionar embeds do Instagram (Politiza-te)
1. Abre uma publicação do Instagram no computador
2. Clica nos três pontos `···` e escolhe **"Incorporar"**
3. Copia o código HTML
4. No ficheiro `/pt/projetos/index.html`, localiza os `instagram-embed-slot`
5. Substitui o conteúdo do slot pelo código copiado
6. Faz o mesmo no ficheiro `/en/projects/index.html`

### Adicionar links na página secreta
1. Abre `/secret/index.html`
2. Procura o bloco `EXEMPLO DE CARTÃO`
3. Copia o exemplo, descomenta-o e preenche os dados
4. Podes criar novas categorias duplicando um bloco `secret-category`

### Adicionar o LinkedIn do Politiza-te (quando disponível)
1. Abre `/pt/projetos/index.html` e `/en/projects/index.html`
2. Localiza o botão `politizate-social--coming` do LinkedIn
3. Remove a classe `politizate-social--coming`
4. Adiciona o `href` com o link correto

---

## 🔐 Página Secreta

A página secreta é ativada clicando **5 vezes** na fotografia de perfil da página inicial.
- Funciona em mobile e PC
- Não está indexada nos motores de busca (tem `noindex, nofollow`)
- O URL é `/secret/` — podes partilhar diretamente se quiseres

---

## 📱 Compatibilidade
- ✅ Chrome, Firefox, Safari, Edge
- ✅ iOS Safari (iPhone/iPad)
- ✅ Android Chrome
- ✅ Responsive em todos os tamanhos de ecrã
