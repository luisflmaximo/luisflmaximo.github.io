"""
Autofill X - Extracao e Catalogacao Automatica de Ferramentas do X (Twitter) via Playwright Browser
Este script abre o Brave Browser de forma segura e visivel, navega pelos teus marcadores (Bookmarks) do X,
descarrega a legenda, card-previews e as imagens de tweets novos, e envia-as ao Gemini para catalogar.
Apos o processamento bem sucedido de cada tweet, ele remove o marcador (Unsave/Bookmark) no ecra em tempo real!

Requisitos:
    pip install openpyxl pillow google-genai requests reportlab playwright
    playwright install chromium
"""

import os
import re
import sys
import json
import time
import urllib.request
import subprocess
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright

# Configuracoes Globais (Relativas ao diretorio do script)
SCRIPT_DIR = Path(__file__).parent
PROGRESS_FILE = SCRIPT_DIR / "autofill_x_progress.json"
POSTS_DOWNLOAD_DIR = SCRIPT_DIR / "x_posts"
LOCAL_GEMINI_KEY_FILE = SCRIPT_DIR / "gemini_api_key.local.txt"
TOOLS_JSON_PATH = SCRIPT_DIR / "secret" / "tools-data.json"

# ---------------------------------------------------------------------------
# Funcoes Auxiliares de Sistema
# ---------------------------------------------------------------------------

def find_brave_executable():
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(program_files) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        Path(program_files_x86) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        Path(local_appdata) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def is_brave_running():
    try:
        output = subprocess.check_output('tasklist /FI "IMAGENAME eq brave.exe"', shell=True, text=True)
        return "brave.exe" in output.lower()
    except Exception:
        return False

def download_file(url, filepath):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=15) as response, open(filepath, 'wb') as out_file:
            out_file.write(response.read())
        return True
    except Exception as e:
        print(f"    [Erro Download] Falha ao descarregar {url[:50]}: {e}")
        return False

# ---------------------------------------------------------------------------
# Download de Media e Remocao de Marcador no X
# ---------------------------------------------------------------------------

def download_tweet_media(page, tweet_el, post_dir, tweet_id):
    post_dir.mkdir(parents=True, exist_ok=True)
    
    tweet_text = ""
    img_count = 0
    image_urls = set()
    
    # Tentar obter os dados com uma pequena espera caso esteja vazio
    for attempt in range(4):
        # 1. Extrair texto do tweet
        tweet_text = ""
        try:
            text_loc = tweet_el.locator('div[data-testid="tweetText"]').first
            if text_loc.count() > 0:
                tweet_text = text_loc.inner_text().strip()
        except Exception:
            pass
            
        # 2. Extrair texto de link preview card
        try:
            card_loc = tweet_el.locator('div[data-testid="card.wrapper"]').first
            if card_loc.count() > 0:
                card_text = card_loc.inner_text().strip()
                if card_text:
                    tweet_text += "\n[Card/Link Preview Info]: " + card_text
        except Exception:
            pass
            
        # 3. Extrair imagens (fotos e card previews)
        image_urls = set()
        try:
            imgs = tweet_el.locator('img').all()
            for img in imgs:
                src = img.get_attribute('src')
                if src and 'pbs.twimg.com/' in src:
                    clean_url = src
                    if "name=" in src:
                        clean_url = re.sub(r"name=[a-zA-Z0-9]+", "name=large", src)
                    image_urls.add(clean_url)
        except Exception:
            pass
            
        img_count = len(image_urls)
        
        # Se temos algum texto ou imagens, ou se ja tentamos 4 vezes
        if tweet_text or img_count > 0 or attempt == 3:
            break
            
        # Caso contrario, esperar 800ms antes da proxima tentativa
        page.wait_for_timeout(800)
        
    # Salvar ficheiro de texto
    txt_path = post_dir / f"{tweet_id}.txt"
    txt_path.write_text(tweet_text, encoding="utf-8")
    
    # Descarregar imagens
    img_idx = 0
    for img_url in image_urls:
        img_idx += 1
        img_path = post_dir / f"{tweet_id}_{img_idx}.jpg"
        download_file(img_url, img_path)
        
    return tweet_text, img_count

def download_tweet_thread(page, post_dir, tweet_id):
    post_dir.mkdir(parents=True, exist_ok=True)
    
    url = f"https://x.com/i/status/{tweet_id}"
    page.goto(url, timeout=35000)
    page.wait_for_timeout(4000)
    
    main_tweet_el = page.locator('article[data-testid="tweet"]').first
    for attempt in range(5):
        if main_tweet_el.count() > 0:
            break
        page.wait_for_timeout(1000)
        
    if main_tweet_el.count() == 0:
        raise Exception("Tweet principal nao encontrado na pagina de detalhe.")
        
    author_username = ""
    author_fullname = ""
    try:
        user_loc = main_tweet_el.locator('div[data-testid="User-Name"]').first
        if user_loc.count() > 0:
            user_lines = user_loc.inner_text().strip().split("\n")
            if len(user_lines) >= 2:
                author_fullname = user_lines[0].strip()
                author_username = user_lines[1].strip().replace("@", "")
    except Exception:
        pass
        
    thread_parts = []
    image_urls = set()
    processed_tweet_ids = set()
    
    # Fazer scrolls para carregar a thread
    for scroll_step in range(3):
        tweets = page.locator('article[data-testid="tweet"]').all()
        for tweet_el in tweets:
            try:
                link_loc = tweet_el.locator('a[href*="/status/"]').first
                curr_tweet_id = ""
                if link_loc.count() > 0:
                    href = link_loc.get_attribute("href")
                    m = re.search(r"/status/([0-9]+)", href)
                    if m:
                        curr_tweet_id = m.group(1)
                        
                if curr_tweet_id and curr_tweet_id in processed_tweet_ids:
                    continue
                    
                curr_author = ""
                curr_fullname = ""
                user_loc = tweet_el.locator('div[data-testid="User-Name"]').first
                if user_loc.count() > 0:
                    user_lines = user_loc.inner_text().strip().split("\n")
                    if len(user_lines) >= 2:
                        curr_fullname = user_lines[0].strip()
                        curr_author = user_lines[1].strip().replace("@", "")
                        
                if curr_tweet_id == tweet_id or (curr_author == author_username and author_username != ""):
                    if curr_tweet_id:
                        processed_tweet_ids.add(curr_tweet_id)
                        
                    tweet_text = ""
                    text_loc = tweet_el.locator('div[data-testid="tweetText"]').first
                    if text_loc.count() > 0:
                        tweet_text = text_loc.inner_text().strip()
                        
                    if curr_tweet_id == tweet_id:
                        try:
                            card_loc = tweet_el.locator('div[data-testid="card.wrapper"]').first
                            if card_loc.count() > 0:
                                card_text = card_loc.inner_text().strip()
                                if card_text:
                                    tweet_text += "\n[Card/Link Preview Info]: " + card_text
                        except Exception:
                            pass
                            
                    if tweet_text:
                        part_label = "Post Principal" if curr_tweet_id == tweet_id else "Continuacao da Thread"
                        thread_parts.append(f"=== {part_label} (ID: {curr_tweet_id}) ===\n{tweet_text}")
                        
                    imgs = tweet_el.locator('img').all()
                    for img in imgs:
                        src = img.get_attribute('src')
                        if src and 'pbs.twimg.com/' in src:
                            clean_url = src
                            if "name=" in src:
                                clean_url = re.sub(r"name=[a-zA-Z0-9]+", "name=large", src)
                            image_urls.add(clean_url)
            except Exception:
                pass
                
        page.evaluate("window.scrollBy(0, 900)")
        page.wait_for_timeout(1500)
        
    full_text = "\n\n".join(thread_parts)
    
    txt_path = post_dir / f"{tweet_id}.txt"
    txt_path.write_text(full_text, encoding="utf-8")
    
    img_idx = 0
    for img_url in image_urls:
        img_idx += 1
        img_path = post_dir / f"{tweet_id}_{img_idx}.jpg"
        download_file(img_url, img_path)
        
    has_video = False
    try:
        has_video = main_tweet_el.locator('video, [data-testid="videoPlayer"]').count() > 0
    except Exception:
        pass
        
    return full_text, img_idx, author_username, author_fullname, has_video

def remove_bookmark_via_browser(tweet_el):
    try:
        selectors = [
            '[data-testid="removeBookmark"]',
            '[aria-label*="Remove bookmark"]',
            '[aria-label*="Remover dos marcadores"]',
            '[aria-label*="Remover marcador"]',
            '[aria-label*="Remove Bookmark"]',
            '[data-testid="bookmark"]'
        ]
        button_clicked = False
        for sel in selectors:
            loc = tweet_el.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                print("  [Unsave] Removido dos marcadores do X com sucesso.")
                button_clicked = True
                break
        if not button_clicked:
            print("  [Unsave Info] Botao de remover marcador nao encontrado para este tweet.")
        return button_clicked
    except Exception as e:
        print(f"  [Unsave Erro] Falha ao remover marcador: {e}")
        return False

# ---------------------------------------------------------------------------
# Gestao de Progresso e Catalogo
# ---------------------------------------------------------------------------

def load_progress():
    default_prog = {"processed_shortcodes": [], "manual_verification_shortcodes": []}
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return default_prog
            if "processed_shortcodes" not in data:
                data["processed_shortcodes"] = []
            if "manual_verification_shortcodes" not in data:
                data["manual_verification_shortcodes"] = []
            return data
        except Exception:
            return default_prog
    return default_prog

def save_progress(progress):
    PROGRESS_FILE.write_text(
        json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8"
    )

def count_total_cards(tools_data):
    total = 0
    for cat in tools_data.get("categories", []):
        for sec in cat.get("sections", []):
            for card in sec.get("cards", []):
                if card and isinstance(card, dict):
                    total += 1
    return total

def get_categories_and_sections_prompt(tools_data):
    lines = []
    for cat in tools_data.get("categories", []):
        lines.append(f"- Categoria ID: \"{cat.get('id')}\" (Nome: {cat.get('label')})")
        for sec in cat.get("sections", []):
            lines.append(f"  * Seccao ID: \"{sec.get('id')}\" (Nome: {sec.get('label')})")
    return "\n".join(lines)

def card_exists(tools_data, href, domain, title=""):
    clean_href = href.lower().rstrip('/')
    clean_domain = domain.lower().replace("www.", "")
    clean_title = title.strip().lower() if title else ""
    
    # Dominios partilhados onde o mesmo dominio nao significa a mesma ferramenta
    shared_domains = {
        "github.com", "github.io", "gitlab.com", "huggingface.co",
        "vercel.app", "netlify.app", "notion.site", "notion.so",
        "substack.com", "medium.com", "chromewebstore.google.com",
        "chrome.google.com", "play.google.com", "apps.apple.com",
        "drive.google.com", "docs.google.com", "npmtrends.com",
        "npmjs.com", "pypi.org", "codepen.io"
    }
    
    is_shared = clean_domain in shared_domains
    
    for cat in tools_data.get("categories", []):
        for sec in cat.get("sections", []):
            for card in sec.get("cards", []):
                if not card or not isinstance(card, dict):
                    continue
                card_href = card.get("href", "").lower().rstrip('/')
                card_domain = card.get("domain", "").lower().replace("www.", "")
                card_title = card.get("title", "").strip().lower()
                
                # 1. Se o URL for exatamente igual, ja existe
                if card_href == clean_href:
                    return card
                    
                # 2. Se o titulo/nome da ferramenta for igual, ja existe (case-insensitive)
                if clean_title and card_title == clean_title:
                    return card
                    
                # 3. Se o dominio for igual (e nao for um dominio partilhado como github), ja existe
                if not is_shared and card_domain == clean_domain:
                    if card_domain not in shared_domains:
                        return card
    return None

def find_tools_for_tweet(tools_data, tweet_id):
    found = []
    for cat in tools_data.get("categories", []):
        for sec in cat.get("sections", []):
            for card in sec.get("cards", []):
                if not card or not isinstance(card, dict):
                    continue
                source = card.get("source")
                if not source or not isinstance(source, dict):
                    continue
                source_href = source.get("href", "")
                if tweet_id in source_href:
                    found.append({
                        "title": card.get("title", ""),
                        "href": card.get("href", ""),
                        "desc": card.get("desc", ""),
                        "category": cat.get("label", ""),
                        "section": sec.get("label", "")
                    })
    return found

def remove_tweet_tools_from_catalog(tools_data, tweet_id):
    removed_count = 0
    for cat in tools_data.get("categories", []):
        for sec in cat.get("sections", []):
            cards = sec.get("cards", [])
            new_cards = []
            for card in cards:
                if not card or not isinstance(card, dict):
                    continue
                source = card.get("source")
                if not source or not isinstance(source, dict):
                    new_cards.append(card)
                    continue
                source_href = source.get("href", "")
                if tweet_id in source_href:
                    removed_count += 1
                else:
                    new_cards.append(card)
            sec["cards"] = new_cards
    if removed_count > 0:
        print(f"  [JSON] Removidas {removed_count} ferramentas antigas associadas ao tweet {tweet_id} do catalogo.")
        tools_data["totalCount"] = count_total_cards(tools_data)
        try:
            TOOLS_JSON_PATH.write_text(
                json.dumps(tools_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"  [Erro JSON] Falha ao gravar catalogo: {e}")
    return removed_count

def ask_user_action(tweet_id, tools_list):
    print(f"\n=====================================================================")
    print(f"   CONFIRMACAO - Tweet {tweet_id}")
    print(f"=====================================================================")
    if tools_list:
        print(f"   Foram identificadas {len(tools_list)} ferramentas na base de dados:")
        for idx, tool in enumerate(tools_list, 1):
            title = tool.get("title", "Sem nome")
            href = tool.get("href", "Sem link")
            desc = tool.get("desc", "")
            cat = tool.get("category", "")
            sec = tool.get("section", "")
            print(f"     {idx}. {title} -> {href}")
            if desc:
                # Truncar descrição muito longa para não inundar o CMD
                clean_desc = desc[:120] + "..." if len(desc) > 120 else desc
                print(f"        Desc: {clean_desc}")
            if cat or sec:
                print(f"        Destino: {cat} / {sec}")
            print("")
    else:
        print("   Nenhuma ferramenta identificada no catalogo para este tweet.")
    print("---------------------------------------------------------------------")
    print("   [R] Retirar (Fazer Unsave e arquivar)")
    print("   [I] Incompleto (Manter nos marcadores do X para verificacao manual)")
    print("   [A] Avaliar Novamente (Forcar re-analise completa pela IA Gemini)")
    print("---------------------------------------------------------------------")
    while True:
        choice = input("   Escolha uma opcao (R / I / A): ").strip().lower()
        if choice in ['r', 'i', 'a']:
            return choice
        print("   Opcao invalida. Digita R, I ou A.")

# ---------------------------------------------------------------------------
# Integracao Gemini com Rotacao de Chaves
# ---------------------------------------------------------------------------

gemini_api_keys = []
gemini_clients = []
gemini_exhausted = []
current_client_idx = 0

def rotate_gemini_client():
    global current_client_idx
    total = len(gemini_api_keys)
    if total <= 1:
        return False
    start_idx = current_client_idx
    while True:
        current_client_idx = (current_client_idx + 1) % total
        if not gemini_exhausted[current_client_idx]:
            break
        if current_client_idx == start_idx:
            return False
    print(f"  [API Keys] Rotacao de API: Chave #{current_client_idx + 1} de {total} selecionada.")
    return True

def run_gemini_operation(operation_func, *args, **kwargs):
    global current_client_idx, gemini_clients
    if not gemini_api_keys:
        print("  [Erro] Nenhum cliente Gemini configurado.")
        return None
    max_retries = len(gemini_api_keys)
    attempts = 0
    while attempts < max_retries:
        if gemini_exhausted[current_client_idx]:
            if not rotate_gemini_client():
                return None
            continue
        if gemini_clients[current_client_idx] is None:
            key = gemini_api_keys[current_client_idx]
            try:
                gemini_clients[current_client_idx] = genai.Client(api_key=key)
            except Exception as ce:
                print(f"  [API Keys] Falha ao instanciar cliente: {ce}")
                gemini_exhausted[current_client_idx] = True
                attempts += 1
                rotate_gemini_client()
                continue
        client = gemini_clients[current_client_idx]
        try:
            result = operation_func(client, *args, **kwargs)
            return result
        except Exception as e:
            err_str = str(e).lower()
            is_quota_error = any(marker in err_str for marker in ["429", "resource_exhausted", "quota exceeded", "rate limit", "limit", "exhausted"])
            is_auth_error = any(marker in err_str for marker in ["400", "api_key_invalid", "permission_denied", "403"])
            if is_quota_error or is_auth_error:
                reason = "limite de quota" if is_quota_error else "chave invalida"
                print(f"  [API Keys] Chave #{current_client_idx + 1} falhou ({reason}). A rodar...")
                gemini_exhausted[current_client_idx] = True
                attempts += 1
                if not rotate_gemini_client():
                    return None
            else:
                print(f"  [API Keys] Erro temporario na chamada (Chave #{current_client_idx + 1}): {e}")
                time.sleep(2)
                attempts += 1
                rotate_gemini_client()
    return None

def extract_tools_from_post(client, caption, image_paths, author_username="", author_fullname=""):
    contents = []
    prompt = f"""
    Analisa o texto da publicacao do X (Twitter), as imagens fornecidas (slides do post se houver) e a informacao do autor da publicacao:
    - Autor da publicacao (Username): @{author_username}
    - Nome do perfil do autor: {author_fullname}
    - Texto da publicacao (Legenda):
    \"\"\"
    {caption}
    \"\"\"
    
    Identifica todas as plataformas, websites, aplicacoes, ferramentas digitais, SaaS, jogos online, recursos web, de IA, extensoes de browser ou paginas recomendadas.
    
    INSTRUCOES CRITICAS DE EXTRACAO:
    1. ATENCAO AO AUTOR: Se o autor do post for a propria ferramenta (ex: o perfil chama-se "Darwin AI" ou "Neuono" ou "Inspired App"), deves extrair essa ferramenta como o recurso principal, mesmo que nao esteja explicitamente nomeada no texto do post.
    2. FONTE DE VERDADE EM LISTAS (EXTREMAMENTE IMPORTANTE): Se o texto do post contiver uma lista numerada ou explicita de ferramentas (ex: "1. raphael.ai", "2. krea.ai", etc.), a tua fonte de verdade principal DEVE ser essa lista textual. Deves extrair cada uma das ferramentas listadas nesse texto.
    3. EVITA SUB-RECURSOS VISUAIS: Se as imagens anexadas mostrarem capturas de ecra de websites catalogos (ex: Hugging Face Spaces, GitHub, Chrome Web Store, etc.), nao extraias os pequenos projetos, repositorios ou demonstracoes secundarias que aparecem listados visualmente dentro da captura de ecra. As imagens servem apenas para ilustrar/confirmar o recurso principal listado no texto (ex: se o texto diz "24. huggingface.co/spaces", extrai apenas "Hugging Face Spaces" e NAO as ferramentas secundarias que aparecem na imagem).
    4. EVITA APLICACÕES GENERICAS: Nao extraias marcas ou aplicacoes genericas de integracao/comunicacao (como Google Docs, Facebook, WhatsApp, Gmail, Slack, Asana, Discord, Notion, X, Google Sheets, etc.) a menos que a publicacao seja especificamente sobre elas. Foca-te APENAS nas ferramentas inovadoras ou especificas apresentadas.
    5. DETETAR POTENCIAL: Se o texto ou contexto sugerir fortemente que existe uma ferramenta no post ou num video associado (ex: "esta nova IA faz...", "ve como funciona esta app...", etc.), mas nao consegues identificar com certeza o nome ou link dela, define "potential_tool_detected" como true.
    
    Para cada item valido identificado, preenche os campos do objeto na lista "tools":
    - name: O nome oficial ou dominio do website/plataforma/jogo/ferramenta (ex: "Framer", "remove.bg", "Coursera").
    - description: Uma breve explicacao de uma frase sobre o que o recurso faz (com base na legenda/post).
    - website_hint: O link, dominio ou site correspondente mencionado na legenda ou visivel nas imagens (ex: "framer.com"). Se nao houver, tenta prever o link com base no nome.
    
    Devolve a resposta APENAS como um objeto JSON valido com a seguinte estrutura:
    {{
      "tools": [
         {{ "name": "...", "description": "...", "website_hint": "..." }}
      ],
      "potential_tool_detected": true/false
    }}
    
    Nao adiciones marcacoes markdown (ex: ```json) nem qualquer outro texto alem do JSON puro na resposta.
    """
    contents.append(prompt)
    loaded_images = []
    for p in image_paths:
        try:
            img = Image.open(p).convert("RGB")
            loaded_images.append(img)
        except Exception as e:
            print(f"  [Erro Imagem] Falha ao carregar imagem para o Gemini: {e}")
    contents.extend(loaded_images)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    cleaned_text = response.text.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
        cleaned_text = re.sub(r"\n```$", "", cleaned_text)
    return json.loads(cleaned_text.strip())

def refine_tool_data(client, tool_name, desc, website_hint, categories_and_sections):
    prompt = f"""
    Estas a catalogar recursos, websites, jogos online, aplicacoes e ferramentas digitais para um diretorio web em Portugues.
    Encontramos o seguinte item no X (Twitter):
    - Nome original: "{tool_name}"
    - Descricao: "{desc}"
    - Dica de Website: "{website_hint}"
    
    Precisas de estruturar e refinar os dados da seguinte forma:
    1. title: O nome oficial e limpo do site/jogo/ferramenta (ex: "Framer", "Remove.bg", "Poki").
    2. href: O link oficial direto para a pagina inicial correspondente. Deve comecar por http:// ou https://.
    3. domain: O dominio raiz limpo (ex: "framer.com").
    4. desc: Uma descricao profissional, concisa e apelativa em PORTUGUES resumindo o que este recurso faz ou oferece. Deve ter entre 12 a 25 palavras. Nao uses hashtags nem CTAs.
    5. categoryId: O ID da categoria mais adequado a partir da lista fornecida abaixo.
    6. sectionId: O ID da seccao mais adequado a partir da lista fornecida abaixo.
    7. badges: Um array de strings que representa o modelo de precos. Escolhe APENAS entre: "Gratis", "Freemium", "Pago". Se nao for explicito, escolhe "Freemium".
    
    Lista de Categorias e Seccoes disponiveis (usa apenas os IDs indicados):
    {categories_and_sections}
    
    Devolve a resposta APENAS como um objeto JSON valido com as chaves: "title", "href", "domain", "desc", "categoryId", "sectionId", "badges".
    Nao adiciones marcacoes markdown nem outro texto alem do JSON puro na resposta.
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    cleaned_text = response.text.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
        cleaned_text = re.sub(r"\n```$", "", cleaned_text)
    return json.loads(cleaned_text.strip())

# ---------------------------------------------------------------------------
# Geracao de Relatorios PDF
# ---------------------------------------------------------------------------

def generate_pdf_report(processed_results, filepath):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        
        doc = SimpleDocTemplate(
            str(filepath), pagesize=letter,
            rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
        )
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1b2a24'), spaceAfter=10
        )
        meta_style = ParagraphStyle(
            'MetaStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#555555'), spaceAfter=15
        )
        cell_style = ParagraphStyle(
            'CellStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11
        )
        header_style = ParagraphStyle(
            'HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white
        )
        
        story.append(Paragraph("Relatorio de Processamento - X Bookmarks Autofill", title_style))
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        total = len(processed_results)
        added = sum(1 for r in processed_results if "Adicionado" in r["status"])
        ignored = sum(1 for r in processed_results if "Ignorado" in r["status"])
        empty = sum(1 for r in processed_results if "Nenhuma ferramenta" in r["status"])
        errors = sum(1 for r in processed_results if "Erro" in r["status"])
        
        meta_text = (
            f"<b>Data de Execucao:</b> {timestamp}<br/>"
            f"<b>Total de Tweets Processados:</b> {total} | "
            f"<b>Adicionados:</b> {added} | "
            f"<b>Ignorados:</b> {ignored} | "
            f"<b>Sem Ferramentas:</b> {empty} | "
            f"<b>Erros:</b> {errors}"
        )
        story.append(Paragraph(meta_text, meta_style))
        story.append(Spacer(1, 8))
        
        table_data = [[
            Paragraph("<b>Tweet ID</b>", header_style),
            Paragraph("<b>Status / Acao</b>", header_style),
            Paragraph("<b>Ferramentas Encontradas</b>", header_style)
        ]]
        
        for r in processed_results:
            table_data.append([
                Paragraph(r["shortcode"], cell_style),
                Paragraph(r["status"], cell_style),
                Paragraph(r["tools"], cell_style)
            ])
            
        t = Table(table_data, colWidths=[100, 150, 270])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3B0F18')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t)
        doc.build(story)
        print(f"\n[Relatorio] Relatorio PDF guardado com sucesso em: {filepath}")
    except Exception as pe:
        print(f"[Aviso PDF] Falha ao gerar relatorio PDF: {pe}")

# ---------------------------------------------------------------------------
# Orquestrador Principal
# ---------------------------------------------------------------------------

def main():
    print("=====================================================================")
    print("        AUTOFILL X - EXTRACAO DE FERRAMENTAS DOS MARCADORES DO X")
    print("=====================================================================\n")

    # 1. Carregar Chaves Gemini
    api_keys = []
    candidates = [
        LOCAL_GEMINI_KEY_FILE,
        Path("C:/Users/luisf/Downloads") / "gemini_api_key.local.txt",
    ]
    key_file_found = None
    for c in candidates:
        if c.exists():
            key_file_found = c
            break
    if key_file_found:
        try:
            with open(key_file_found, "r", encoding="utf-8") as f:
                for line in f:
                    k = line.strip()
                    if k and not k.startswith("#") and k not in api_keys:
                        api_keys.append(k)
            print(f"[API Keys] Carregadas {len(api_keys)} chaves a partir de: {key_file_found}")
        except Exception as e:
            print(f"[Erro] Falha ao ler ficheiro de chaves: {e}")
            
    if not api_keys:
        print("[Erro] Nenhuma chave Gemini encontrada.")
        sys.exit(1)
        
    global gemini_api_keys, gemini_clients, gemini_exhausted, current_client_idx
    gemini_api_keys = api_keys
    gemini_clients = [None] * len(api_keys)
    gemini_exhausted = [False] * len(api_keys)
    current_client_idx = 0

    # 2. Carregar tools-data.json
    if not TOOLS_JSON_PATH.exists():
        print(f"[Erro] Ficheiro tools-data.json nao encontrado em: {TOOLS_JSON_PATH}")
        sys.exit(1)
        
    try:
        tools_data = json.loads(TOOLS_JSON_PATH.read_text(encoding="utf-8"))
        print(f"[JSON] tools-data.json carregado. totalCount: {tools_data.get('totalCount')}")
    except Exception as e:
        print(f"[Erro] Falha ao carregar tools-data.json: {e}")
        sys.exit(1)
        
    categories_and_sections = get_categories_and_sections_prompt(tools_data)
    progress = load_progress()
    
    # 3. Validar se o Brave esta a correr
    brave_exe = find_brave_executable()
    if not brave_exe:
        print("[Erro] Executavel do Brave nao encontrado.")
        sys.exit(1)
        
    user_data_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware" / "Brave-Browser" / "User Data"
    
    print("\nA verificar se o Brave esta aberto...")
    attempts = 0
    while is_brave_running() and attempts < 60:
        attempts += 1
        print(f"[Brave Aberto] Por favor, FECHA todas as janelas do Brave browser (tentativa {attempts}/60)...", flush=True)
        time.sleep(2)
        
    if is_brave_running():
        print("[Erro] O Brave continuou aberto. Execucao abortada.")
        sys.exit(1)
        
    time.sleep(1.5)
    
    # 4. Inicializar Playwright
    playwright_inst = sync_playwright().start()
    print("\nA abrir o perfil do Brave em modo interativo (headful)...")
    
    processed_results = []
    new_cards_added = 0
    
    try:
        browser_context = playwright_inst.chromium.launch_persistent_context(
            str(user_data_dir),
            executable_path=str(brave_exe),
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        page = browser_context.new_page()
        page.set_viewport_size({"width": 1280, "height": 1000})
        
        print("\nA carregar marcadores do X (Bookmarks)...")
        page.goto("https://x.com/i/bookmarks", timeout=60000)
        page.wait_for_timeout(8000)
        
        if "login" in page.url.lower():
            print("[Erro] Sessao nao iniciada no X (Twitter) no Brave. Execucao abortada.")
            return
            
        POSTS_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        processed_in_this_run = set()
        
        scrolls_without_height_change = 0
        max_scrolls_without_height_change = 10
        last_height = page.evaluate("document.body.scrollHeight")
        
        print("\nA processar tweets dinamicamente dos marcadores (virtual scrolling)...")
        
        while scrolls_without_height_change < max_scrolls_without_height_change:
            tweets = page.locator('article[data-testid="tweet"]').all()
            for tweet_el in tweets:
                # Verificar se a aba principal saiu da pagina de marcadores
                if "bookmarks" not in page.url.lower():
                    print("  [Browser Info] Aba principal fora dos marcadores. A navegar de volta para /i/bookmarks...")
                    page.goto("https://x.com/i/bookmarks", timeout=60000)
                    page.wait_for_timeout(5000)
                    break # Sai do loop 'for' para recomecar o 'for' fresh na pagina de marcadores
                    
                thread_page = None
                try:
                    # Obter URL do tweet
                    link_loc = tweet_el.locator('a[href*="/status/"]').first
                    if link_loc.count() > 0:
                        href = link_loc.get_attribute("href")
                        m = re.search(r"/status/([0-9]+)", href)
                        if m:
                            tweet_id = m.group(1)
                            
                            # Se ja processamos nesta run, saltar
                            if tweet_id in processed_in_this_run:
                                continue
                                
                            post_dir = POSTS_DOWNLOAD_DIR / tweet_id
                            tweet_done = False
                            
                            while not tweet_done:
                                # 1. Se ja foi processado em execucoes anteriores e NAO estamos a reavaliar explicitamente nesta itit
                                if tweet_id in progress.get("processed_shortcodes", []) and (tweet_id not in processed_in_this_run):
                                    tools_found = find_tools_for_tweet(tools_data, tweet_id)
                                    action = ask_user_action(tweet_id, tools_found)
                                    
                                    if action == 'r':
                                        print(f"  A remover dos marcadores (Unsave)...")
                                        remove_bookmark_via_browser(tweet_el)
                                        if tweet_id in progress.get("manual_verification_shortcodes", []):
                                            progress["manual_verification_shortcodes"].remove(tweet_id)
                                            save_progress(progress)
                                        page.wait_for_timeout(1000)
                                        tweet_done = True
                                    elif action == 'i':
                                        print(f"  Mantido nos marcadores (Incompleto/Manual).")
                                        if tweet_id not in progress.setdefault("manual_verification_shortcodes", []):
                                            progress["manual_verification_shortcodes"].append(tweet_id)
                                            save_progress(progress)
                                        tweet_done = True
                                    elif action == 'a':
                                        print(f"  A reavaliar tweet via Gemini...")
                                        if tweet_id in progress.get("processed_shortcodes", []):
                                            progress["processed_shortcodes"].remove(tweet_id)
                                        if tweet_id in progress.get("manual_verification_shortcodes", []):
                                            progress["manual_verification_shortcodes"].remove(tweet_id)
                                        save_progress(progress)
                                        remove_tweet_tools_from_catalog(tools_data, tweet_id)
                                        # Continua no loop local para re-analise
                                        
                                    if tweet_done:
                                        processed_in_this_run.add(tweet_id)
                                        break
                                
                                # 2. Processamento Novo/Reavaliacao
                                print(f"\n[X Bookmarks] A processar tweet {tweet_id}...")
                                post_dir.mkdir(parents=True, exist_ok=True)
                                
                                # Garantir visibilidade
                                try:
                                    tweet_el.scroll_into_view_if_needed()
                                    page.wait_for_timeout(1000)
                                except Exception:
                                    pass
                                    
                                # Criar aba temporaria para descarregar a thread completa online
                                thread_page = browser_context.new_page()
                                thread_page.set_viewport_size({"width": 1280, "height": 1000})
                                
                                tweet_text = ""
                                img_count = 0
                                author_username = ""
                                author_fullname = ""
                                has_video = False
                                
                                try:
                                    tweet_text, img_count, author_username, author_fullname, has_video = download_tweet_thread(
                                        thread_page, post_dir, tweet_id
                                    )
                                    print(f"  Texto (Thread): ~{len(tweet_text)} carateres. Imagens: {img_count}. Autor: @{author_username}. Tem video: {has_video}")
                                except Exception as th_ex:
                                    print(f"  [Thread Info] Falha ao carregar thread online ({th_ex}). Usando dados simplificados dos Bookmarks...")
                                    tweet_text, img_count = download_tweet_media(page, tweet_el, post_dir, tweet_id)
                                    try:
                                        has_video = tweet_el.locator('video, [data-testid="videoPlayer"]').count() > 0
                                    except Exception:
                                        pass
                                    try:
                                        user_loc = tweet_el.locator('div[data-testid="User-Name"]').first
                                        if user_loc.count() > 0:
                                            user_lines = user_loc.inner_text().strip().split("\n")
                                            if len(user_lines) >= 2:
                                                author_fullname = user_lines[0].strip()
                                                author_username = user_lines[1].strip().replace("@", "")
                                    except Exception:
                                        pass
                                    print(f"  Texto (Bookmarks): ~{len(tweet_text)} carateres. Imagens: {img_count}. Autor: @{author_username}. Tem video: {has_video}")
                                    
                                # Salvar metadados do autor localmente
                                metadata_path = post_dir / "metadata.json"
                                metadata_path.write_text(json.dumps({
                                    "author_username": author_username,
                                    "author_fullname": author_fullname,
                                    "tweet_id": tweet_id,
                                    "url": f"https://x.com{href}"
                                }, indent=2, ensure_ascii=False), encoding="utf-8")
                                
                                # Gemini Pass 1: Extrair ferramentas
                                print("  A enviar para o Gemini (Passagem 1 - Extracao)...")
                                jpg_files = list(post_dir.glob("*.jpg")) + list(post_dir.glob("*.jpeg")) + list(post_dir.glob("*.png"))
                                image_paths = [str(f) for f in jpg_files]
                                
                                extracted_data = run_gemini_operation(
                                    extract_tools_from_post, tweet_text, image_paths, 
                                    author_username=author_username, author_fullname=author_fullname
                                )
                                
                                if extracted_data is None:
                                    print(f"  [Erro] Falha na chamada da API do Gemini. A saltar tweet.")
                                    processed_results.append({
                                        "shortcode": tweet_id,
                                        "status": "Erro (Falha na API Gemini)",
                                        "tools": "-"
                                    })
                                    tweet_done = True
                                    break
                                    
                                extracted_tools = extracted_data.get("tools", [])
                                potential_tool_detected = extracted_data.get("potential_tool_detected", False)
                                
                                if len(extracted_tools) == 0:
                                    print("  Nenhuma ferramenta identificada neste tweet.")
                                    status_summary = "Nenhuma ferramenta"
                                    tools_summary = "-"
                                else:
                                    print(f"  Ferramentas encontradas pela IA: {', '.join([t.get('name', 'Sem nome') for t in extracted_tools])}")
                                    
                                    # Gemini Pass 2: Refinar
                                    tools_statuses = []
                                    tools_names_urls = []
                                    
                                    for tool in extracted_tools:
                                        t_name = tool.get("name")
                                        t_desc = tool.get("description")
                                        t_hint = tool.get("website_hint")
                                        if not t_name:
                                            continue
                                            
                                        dummy_href = t_hint if (t_hint and t_hint.startswith("http")) else f"https://{t_hint}" if t_hint else f"https://{t_name.lower().replace(' ', '')}.com"
                                        existing_card = card_exists(tools_data, dummy_href, t_hint or t_name, title=t_name)
                                        if existing_card:
                                            print(f"  [Ignorado] '{t_name}' ja existe no catalogo: {existing_card.get('title')} ({existing_card.get('href')})")
                                            tools_statuses.append(f"Ignorado (Ja existe: {t_name})")
                                            tools_names_urls.append(f"{t_name} ({existing_card.get('href')})")
                                            continue
                                            
                                        print(f"  A refinar dados da ferramenta '{t_name}'...")
                                        refined = run_gemini_operation(refine_tool_data, t_name, t_desc, t_hint, categories_and_sections)
                                        if not refined:
                                            print(f"  [Erro] Falha na refinacao. Saltando ferramenta '{t_name}'.")
                                            continue
                                            
                                        # Validar se o URL refinado ja existe
                                        existing_card = card_exists(tools_data, refined["href"], refined["domain"], title=refined["title"])
                                        if existing_card:
                                            print(f"  [Ignorado] URL refinado '{refined['href']}' ja esta no catalogo.")
                                            tools_statuses.append(f"Ignorado (Ja existe: {refined['title']})")
                                            tools_names_urls.append(f"{refined['title']} ({refined['href']})")
                                            continue
                                            
                                        # Mapear os badges
                                        mapped_badges = []
                                        for b_str in refined.get("badges", []):
                                            if b_str == "Gratis":
                                                mapped_badges.append({"className": "badge-free", "label": "Gr\u00e1tis"})
                                            elif b_str == "Freemium":
                                                mapped_badges.append({"className": "badge-freemium", "label": "Freemium"})
                                            elif b_str == "Pago":
                                                mapped_badges.append({"className": "badge-paid", "label": "Pago"})
                                            else:
                                                mapped_badges.append({"className": "badge-freemium", "label": b_str})
                                        if not mapped_badges:
                                            mapped_badges = [{"className": "badge-freemium", "label": "Freemium"}]
                                            
                                        new_card = {
                                            "title": refined["title"],
                                            "href": refined["href"],
                                            "desc": refined["desc"],
                                            "search": f"{refined['title'].lower()} {refined['domain'].lower()} {refined['desc'].lower()} x.com",
                                            "sectionId": refined["sectionId"],
                                            "favicon": f"https://www.google.com/s2/favicons?domain={refined['domain']}&sz=32",
                                            "domain": refined["domain"],
                                            "badges": mapped_badges,
                                            "source": {
                                                "href": f"https://x.com{href}",
                                                "label": "x.com"
                                            }
                                        }
                                        
                                        cat_id = refined.get("categoryId")
                                        sec_id = refined.get("sectionId")
                                        target_cat = None
                                        target_sec = None
                                        
                                        for cat in tools_data.get("categories", []):
                                            if cat.get("id") == cat_id:
                                                target_cat = cat
                                                for sec in cat.get("sections", []):
                                                    if sec.get("id") == sec_id:
                                                        target_sec = sec
                                                        break
                                                break
                                                
                                        if not target_sec:
                                            print(f"  [Aviso] Seccao '{cat_id}/{sec_id}' nao encontrada. Usando 'outros/recursos_uteis'.")
                                            for cat in tools_data.get("categories", []):
                                                if cat.get("id") == "outros":
                                                    target_cat = cat
                                                    for sec in cat.get("sections", []):
                                                        if sec.get("id") == "recursos_uteis":
                                                            target_sec = sec
                                                            break
                                                    break
                                                    
                                        if target_sec is not None:
                                            target_sec.setdefault("cards", []).append(new_card)
                                            new_cards_added += 1
                                            print(f"  [Adicionado] '{new_card['title']}' adicionado a '{target_sec['label']}'!")
                                            tools_statuses.append(f"Adicionado: {refined['title']}")
                                            tools_names_urls.append(f"{refined['title']} ({refined['href']})")
                                            
                                    status_summary = "; ".join(set(tools_statuses)) if tools_statuses else "Nenhuma ferramenta adicionada"
                                    tools_summary = "; ".join(tools_names_urls) if tools_names_urls else "-"
                                
                                # Gravar JSON das ferramentas (provisoriamente)
                                tools_data["totalCount"] = count_total_cards(tools_data)
                                TOOLS_JSON_PATH.write_text(
                                    json.dumps(tools_data, indent=2, ensure_ascii=False),
                                    encoding="utf-8"
                                )
                                
                                # Obter lista das ferramentas no catalogo e pedir confirmacao
                                tools_found = find_tools_for_tweet(tools_data, tweet_id)
                                action = ask_user_action(tweet_id, tools_found)
                                
                                if action == 'r':
                                    print(f"  A remover dos marcadores (Unsave)...")
                                    unsaved_ok = False
                                    if thread_page is not None and not thread_page.is_closed():
                                        try:
                                            main_tweet_el = thread_page.locator('article[data-testid="tweet"]').first
                                            if main_tweet_el.count() > 0:
                                                unsaved_ok = remove_bookmark_via_browser(main_tweet_el)
                                        except Exception:
                                            pass
                                    if not unsaved_ok:
                                        remove_bookmark_via_browser(tweet_el)
                                    if tweet_id in progress.get("manual_verification_shortcodes", []):
                                        progress["manual_verification_shortcodes"].remove(tweet_id)
                                    tweet_done = True
                                elif action == 'i':
                                    print(f"  Mantido nos marcadores (Incompleto/Manual).")
                                    if tweet_id not in progress.setdefault("manual_verification_shortcodes", []):
                                        progress["manual_verification_shortcodes"].append(tweet_id)
                                    tweet_done = True
                                elif action == 'a':
                                    print(f"  Escolheste reavaliar. A limpar cache local e reiniciar processamento...")
                                    remove_tweet_tools_from_catalog(tools_data, tweet_id)
                                    import shutil
                                    if post_dir.exists():
                                        try:
                                            shutil.rmtree(post_dir)
                                        except Exception:
                                            pass
                                            
                                # Fechar a thread_page temporaria desta iteracao do loop local
                                if thread_page is not None:
                                    try:
                                        if not thread_page.is_closed():
                                            thread_page.close()
                                    except Exception:
                                        pass
                                    thread_page = None
                                    
                                if tweet_done:
                                    processed_results.append({
                                        "shortcode": tweet_id,
                                        "status": status_summary if action == 'r' else "Veric. Manual (Video) + " + status_summary if (has_video and action == 'i') else "Incompleto/Manual",
                                        "tools": tools_summary
                                    })
                                    if tweet_id not in progress["processed_shortcodes"]:
                                        progress["processed_shortcodes"].append(tweet_id)
                                    save_progress(progress)
                                    processed_in_this_run.add(tweet_id)
                                    print(f"  [JSON] Guardado. totalCount: {tools_data['totalCount']}")
                                    page.wait_for_timeout(1500)
                except Exception as ex:
                    print(f"  [Erro Tweet] Ocorreu uma excepção ao processar o tweet: {ex}")
                finally:
                    if thread_page is not None:
                        try:
                            if not thread_page.is_closed():
                                thread_page.close()
                        except Exception:
                            pass
            
            # Scroll down to reveal more / mount virtual elements
            page.evaluate("window.scrollBy(0, 1200)")
            page.wait_for_timeout(2500)
            
            current_height = page.evaluate("document.body.scrollHeight")
            if current_height == last_height:
                scrolls_without_height_change += 1
            else:
                scrolls_without_height_change = 0
                last_height = current_height

        # 6. Fallback local de pastas existentes por processar
        print("\nA verificar fallback local de pastas por processar em x_posts...")
        local_collected = []
        if POSTS_DOWNLOAD_DIR.exists():
            for item in POSTS_DOWNLOAD_DIR.iterdir():
                if item.is_dir():
                    sc = item.name
                    if re.match(r"^[0-9]+$", sc):
                        if sc not in progress["processed_shortcodes"]:
                            local_collected.append(sc)
                            
        if local_collected:
            print(f"Identificados {len(local_collected)} tweets locais para processamento de fallback/reavaliacao...")
            for idx, tweet_id in enumerate(local_collected):
                print(f"\n[Local Fallback/Reavaliacao] [{idx+1}/{len(local_collected)}] A processar tweet local {tweet_id}...")
                post_dir = POSTS_DOWNLOAD_DIR / tweet_id
                
                # Variável de controlo do loop local
                tweet_done = False
                
                # Para sabermos se carregamos online ou offline nesta iteração
                loaded_online = False
                
                while not tweet_done:
                    tweet_text = ""
                    img_count = 0
                    author_username = ""
                    author_fullname = ""
                    has_video = False
                    
                    try:
                        print(f"  A tentar carregar tweet {tweet_id} individualmente no browser...")
                        tweet_text, img_count, author_username, author_fullname, has_video = download_tweet_thread(
                            page, post_dir, tweet_id
                        )
                        # Gravar metadata
                        metadata_path = post_dir / "metadata.json"
                        metadata_path.write_text(json.dumps({
                            "author_username": author_username,
                            "author_fullname": author_fullname,
                            "tweet_id": tweet_id,
                            "url": f"https://x.com/i/status/{tweet_id}"
                        }, indent=2, ensure_ascii=False), encoding="utf-8")
                        
                        loaded_online = True
                        print(f"  [Online] Thread obtida com sucesso: ~{len(tweet_text)} carateres, {img_count} imagens. Autor: @{author_username}. Tem video: {has_video}")
                    except Exception as online_ex:
                        print(f"  [Online Falhou] Nao foi possivel recolher online ({online_ex}). Usando cache local...")
                        
                    if not loaded_online:
                        # Ler dados locais se existirem
                        txt_files = list(post_dir.glob("*.txt"))
                        jpg_files = list(post_dir.glob("*.jpg")) + list(post_dir.glob("*.jpeg")) + list(post_dir.glob("*.png"))
                        
                        if txt_files:
                            tweet_text = txt_files[0].read_text(encoding="utf-8").strip()
                            
                        metadata_path = post_dir / "metadata.json"
                        if metadata_path.exists():
                            try:
                                meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                                author_username = meta.get("author_username", "")
                                author_fullname = meta.get("author_fullname", "")
                            except Exception:
                                pass
                                
                        image_paths = [str(f) for f in jpg_files]
                        print(f"  [Local Cache] Texto: ~{len(tweet_text)} carateres. Imagens locais: {len(image_paths)}. Autor: @{author_username}")
                    
                    # Enviar para o Gemini se houver alguma coisa a processar
                    jpg_files = list(post_dir.glob("*.jpg")) + list(post_dir.glob("*.jpeg")) + list(post_dir.glob("*.png"))
                    image_paths = [str(f) for f in jpg_files]
                    
                    if not tweet_text and not image_paths and not author_username:
                        print("  Sem dados suficientes para processamento. Nenhuma ferramenta identificada.")
                        status_summary = "Nenhuma ferramenta (Dados vazios)"
                        tools_summary = "-"
                        extracted_tools = []
                    else:
                        print("  A enviar para o Gemini (Passagem 1 - Extracao)...")
                        extracted_data = run_gemini_operation(
                            extract_tools_from_post, tweet_text, image_paths, 
                            author_username=author_username, author_fullname=author_fullname
                        )
                        
                        if extracted_data is None:
                            print(f"  [Erro] Falha na chamada da API do Gemini. A saltar.")
                            processed_results.append({
                                "shortcode": tweet_id,
                                "status": "Erro (Falha na API Gemini)",
                                "tools": "-"
                            })
                            tweet_done = True
                            break
                            
                        extracted_tools = extracted_data.get("tools", [])
                        potential_tool_detected = extracted_data.get("potential_tool_detected", False)
                        
                        if len(extracted_tools) == 0:
                            print("  Nenhuma ferramenta identificada neste tweet.")
                            status_summary = "Nenhuma ferramenta"
                            tools_summary = "-"
                        else:
                            print(f"  Ferramentas encontradas: {', '.join([t.get('name', 'Sem nome') for t in extracted_tools])}")
                            
                            # Gemini Pass 2
                            tools_statuses = []
                            tools_names_urls = []
                            
                            for tool in extracted_tools:
                                t_name = tool.get("name")
                                t_desc = tool.get("description")
                                t_hint = tool.get("website_hint")
                                if not t_name:
                                    continue
                                    
                                dummy_href = t_hint if (t_hint and t_hint.startswith("http")) else f"https://{t_hint}" if t_hint else f"https://{t_name.lower().replace(' ', '')}.com"
                                existing_card = card_exists(tools_data, dummy_href, t_hint or t_name, title=t_name)
                                if existing_card:
                                    print(f"  [Ignorado] '{t_name}' ja existe: {existing_card.get('title')} ({existing_card.get('href')})")
                                    tools_statuses.append(f"Ignorado (Ja existe: {t_name})")
                                    tools_names_urls.append(f"{t_name} ({existing_card.get('href')})")
                                    continue
                                    
                                print(f"  A refinar dados da ferramenta '{t_name}'...")
                                refined = run_gemini_operation(refine_tool_data, t_name, t_desc, t_hint, categories_and_sections)
                                if not refined:
                                    print(f"  [Erro] Falha na refinacao.")
                                    continue
                                    
                                existing_card = card_exists(tools_data, refined["href"], refined["domain"], title=refined["title"])
                                if existing_card:
                                    print(f"  [Ignorado] URL refinado '{refined['href']}' ja esta no catalogo.")
                                    tools_statuses.append(f"Ignorado (Ja existe: {refined['title']})")
                                    tools_names_urls.append(f"{refined['title']} ({refined['href']})")
                                    continue
                                    
                                mapped_badges = []
                                for b_str in refined.get("badges", []):
                                    if b_str == "Gratis":
                                        mapped_badges.append({"className": "badge-free", "label": "Gr\u00e1tis"})
                                    elif b_str == "Freemium":
                                        mapped_badges.append({"className": "badge-freemium", "label": "Freemium"})
                                    elif b_str == "Pago":
                                        mapped_badges.append({"className": "badge-paid", "label": "Pago"})
                                    else:
                                        mapped_badges.append({"className": "badge-freemium", "label": b_str})
                                if not mapped_badges:
                                    mapped_badges = [{"className": "badge-freemium", "label": "Freemium"}]
                                    
                                new_card = {
                                    "title": refined["title"],
                                    "href": refined["href"],
                                    "desc": refined["desc"],
                                    "search": f"{refined['title'].lower()} {refined['domain'].lower()} {refined['desc'].lower()} x.com",
                                    "sectionId": refined["sectionId"],
                                    "favicon": f"https://www.google.com/s2/favicons?domain={refined['domain']}&sz=32",
                                    "domain": refined["domain"],
                                    "badges": mapped_badges,
                                    "source": {
                                        "href": f"https://x.com/i/status/{tweet_id}",
                                        "label": "x.com"
                                    }
                                }
                                
                                cat_id = refined.get("categoryId")
                                sec_id = refined.get("sectionId")
                                target_cat = None
                                target_sec = None
                                
                                for cat in tools_data.get("categories", []):
                                    if cat.get("id") == cat_id:
                                        target_cat = cat
                                        for sec in cat.get("sections", []):
                                            if sec.get("id") == sec_id:
                                                target_sec = sec
                                                break
                                        break
                                        
                                if not target_sec:
                                    for cat in tools_data.get("categories", []):
                                        if cat.get("id") == "outros":
                                            target_cat = cat
                                            for sec in cat.get("sections", []):
                                                if sec.get("id") == "recursos_uteis":
                                                    target_sec = sec
                                                    break
                                            break
                                            
                                if target_sec is not None:
                                    target_sec.setdefault("cards", []).append(new_card)
                                    new_cards_added += 1
                                    print(f"  [Adicionado] '{new_card['title']}' adicionado a '{target_sec['label']}'!")
                                    tools_statuses.append(f"Adicionado: {refined['title']}")
                                    tools_names_urls.append(f"{refined['title']} ({refined['href']})")
                                    
                            status_summary = "; ".join(set(tools_statuses)) if tools_statuses else "Nenhuma ferramenta adicionada"
                            tools_summary = "; ".join(tools_names_urls) if tools_names_urls else "-"
                            
                    # Gravar JSON provisoriamente
                    tools_data["totalCount"] = count_total_cards(tools_data)
                    TOOLS_JSON_PATH.write_text(
                        json.dumps(tools_data, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
                    
                    # Pedir confirmacao ao utilizador
                    tools_found = find_tools_for_tweet(tools_data, tweet_id)
                    action = ask_user_action(tweet_id, tools_found)
                    
                    if action == 'r':
                        unsaved_ok = False
                        if loaded_online:
                            try:
                                main_tweet_el = page.locator('article[data-testid="tweet"]').first
                                if main_tweet_el.count() > 0:
                                    unsaved_ok = remove_bookmark_via_browser(main_tweet_el)
                            except Exception:
                                pass
                        if not unsaved_ok:
                            print("  [Unsave Info] Nao foi possivel remover marcador no fallback local.")
                        if tweet_id in progress.get("manual_verification_shortcodes", []):
                            progress["manual_verification_shortcodes"].remove(tweet_id)
                        tweet_done = True
                    elif action == 'i':
                        print(f"  Mantido nos marcadores (Incompleto/Manual).")
                        if tweet_id not in progress.setdefault("manual_verification_shortcodes", []):
                            progress["manual_verification_shortcodes"].append(tweet_id)
                        tweet_done = True
                    elif action == 'a':
                        print(f"  Escolheste reavaliar. A limpar cache local e reiniciar processamento...")
                        remove_tweet_tools_from_catalog(tools_data, tweet_id)
                        import shutil
                        if post_dir.exists():
                            try:
                                shutil.rmtree(post_dir)
                            except Exception:
                                pass
                        # loaded_online recua para tentar carregar online de novo
                        loaded_online = False
                        
                    if tweet_done:
                        processed_results.append({
                            "shortcode": tweet_id,
                            "status": status_summary if action == 'r' else "Veric. Manual (Video) + " + status_summary if (has_video and action == 'i') else "Incompleto/Manual",
                            "tools": tools_summary
                        })
                        if tweet_id not in progress["processed_shortcodes"]:
                            progress["processed_shortcodes"].append(tweet_id)
                        save_progress(progress)
                        print(f"  [JSON] Guardado. totalCount: {tools_data['totalCount']}")
                
        print("\n=====================================================================")
        print(f"Concluido com Sucesso! Novos cards adicionados: {new_cards_added}")
        print("=====================================================================")
        
        # Gerar relatorio PDF
        generate_pdf_report(processed_results, SCRIPT_DIR / "autofill_x_report.pdf")
        
    except Exception as e:
        print(f"\n[Erro Geral] Ocorreu um erro na automacao: {e}")
    finally:
        if 'browser_context' in locals() and browser_context:
            browser_context.close()
        playwright_inst.stop()

if __name__ == "__main__":
    main()
