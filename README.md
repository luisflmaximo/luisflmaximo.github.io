# Luís Máximo — Portefólio Pessoal

Site pessoal de portefólio, currículo e projetos de Luís Máximo, estudante de Gestão na [ISCTE Business School](https://ibs.iscte-iul.pt/), Lisboa.

[luisflmaximo.github.io/portefolio](https://luisflmaximo.github.io/portefolio/)

## Sobre

O site apresenta o percurso académico, o currículo, projetos académicos e atividade pública ligada a participação cívica. Está disponível em três idiomas:

- Português
- English
- Español

É construído em HTML, CSS e JavaScript puros e alojado no GitHub Pages.

## Secções Públicas

### Início

Página de apresentação com fotografia, resumo pessoal, contactos públicos, redes sociais e acesso a publicações/artigos no LinkedIn.

### Projetos

Trabalhos académicos e iniciativas pessoais, incluindo o projeto Politiza-te e o visualizador do relatório académico Mega Caixa Super Bock 100 Anos de Cerveja.

### Currículo

Percurso académico, competências, experiências relevantes e ligação para download do CV em PDF.

## Características Técnicas

| Característica | Detalhe |
|---|---|
| Idiomas | PT · EN · ES |
| Redirecionamento | Preferência guardada ou idioma do browser |
| SEO | Schema.org / JSON-LD · Open Graph · Twitter Cards · Sitemap XML · robots.txt · hreflang |
| PWA | `site.webmanifest`, ícones e atalhos |
| Embeds | LinkedIn e Instagram carregados de forma diferida |
| Cache | Assets globais versionados por query string |
| Tipografia | Cormorant Garamond + Outfit |
| Acessibilidade | Skip links, ARIA labels e navegação por teclado |
| Compatibilidade | Chrome · Firefox · Safari · Edge · iOS · Android |
| Responsivo | Layouts dedicados para desktop, tablet e mobile |

## Estrutura Pública

```text
portefolio/
├── index.html
├── 404.html
├── robots.txt
├── sitemap.xml
├── site.webmanifest
├── assets/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── main.js
│   └── images/
├── docs/
│   ├── seo-public.json
│   ├── superbock-viewer.html
│   └── superbock-pages/
├── pt/
├── en/
└── es/
```

## Manutenção SEO

Os dados públicos de SEO e alternates estão resumidos em `docs/seo-public.json`. As páginas continuam a ter meta tags estáticas no HTML para preservar a qualidade de indexação em motores de busca.

O `sitemap.xml` lista as páginas públicas indexáveis em PT, EN e ES, incluindo o visualizador público do projeto Super Bock. O `robots.txt` mantém o crawl aberto para as páginas públicas, bloqueando apenas ficheiros auxiliares que não fazem parte da experiência pública.

Quando `assets/css/style.css` ou `assets/js/main.js` mudam, os links HTML usam uma query string de versão, como `?v=20260704-site7`, para evitar cache antiga no GitHub Pages. Como esses ficheiros são globais, a mesma versão aparece em todas as páginas que os carregam.

## Contacto

- [LinkedIn](https://www.linkedin.com/in/luisflmaximo/)
- [Instagram](https://www.instagram.com/luisflmaximo/)
- [X](https://x.com/luisflmaximo)
