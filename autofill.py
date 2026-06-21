"""
Autofill - Extração e Catalogação Automática de Ferramentas do Instagram via Playwright Browser
Este script abre o Brave Browser de forma segura e visível, navega pelas tuas publicações guardadas,
descarrega a legenda e as imagens de posts novos, e envia-as ao Gemini para catalogar.
Após o processamento bem sucedido de cada post, ele desmarca (unsave) o post no ecrã em tempo real!

Requisitos:
    pip install openpyxl pillow google-genai requests reportlab playwright
    playwright install chromium
"""

import argparse
import json
import os
import platform
import re
import shutil
import sys
import time
import urllib.request
import subprocess
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright

# Configurações Globais
PROGRESS_FILE = Path(__file__).parent / "autofill_progress.json"
POSTS_DOWNLOAD_DIR = Path(__file__).parent / "instagram_posts"
LOCAL_GEMINI_KEY_FILE = Path(__file__).parent / "gemini_api_key.local.txt"

# ---------------------------------------------------------------------------
# Funções Auxiliares de Sistema e Decoração
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

def download_post_media_browser(page, post_dir, shortcode):
    post_dir.mkdir(parents=True, exist_ok=True)
    
    caption = ""
    try:
        meta_desc = page.locator('meta[property="og:description"]').get_attribute('content')
        if meta_desc:
            m = re.search(r":\s*['\"](.*?)['\"]$", meta_desc)
            if m:
                caption = m.group(1)
            else:
                parts = meta_desc.split(":", 1)
                if len(parts) > 1:
                    caption = parts[1].strip()
                else:
                    caption = meta_desc
    except Exception:
        pass
    
    if not caption:
        try:
            spans = page.locator('span._ap3a._aaco._aacw._aacx._aad7._aade').all()
            if spans:
                caption = spans[0].inner_text()
        except Exception:
            pass
            
    txt_path = post_dir / f"{shortcode}.txt"
    txt_path.write_text(caption, encoding="utf-8")
    
    image_urls = set()
    try:
        meta_img = page.locator('meta[property="og:image"]').get_attribute('content')
        if meta_img:
            image_urls.add(meta_img)
    except Exception:
        pass
        
    try:
        next_btn_selector = 'button:has(svg[aria-label*="Next"]), button:has(svg[aria-label*="Seguinte"]), button:has(svg[aria-label*="Avançar"]), button[aria-label*="Next"], button[aria-label*="Seguinte"], button[aria-label*="Avançar"]'
        carousel_images = set()
        for slide_step in range(10):
            imgs = page.locator('article img').all()
            for img in imgs:
                src = img.get_attribute('src')
                if src and 'cdninstagram.com' in src:
                    carousel_images.add(src)
            next_btn = page.locator(next_btn_selector)
            if next_btn.count() > 0 and next_btn.first.is_visible():
                next_btn.first.click()
                page.wait_for_timeout(1000)
            else:
                break
        if carousel_images:
            image_urls.update(carousel_images)
    except Exception:
        pass
        
    if not image_urls:
        imgs = page.locator('img').all()
        for img in imgs:
            src = img.get_attribute('src')
            if src and 'cdninstagram.com' in src:
                image_urls.add(src)
                
    img_count = 0
    for img_url in image_urls:
        img_count += 1
        img_name = f"{shortcode}_{img_count}.jpg"
        img_path = post_dir / img_name
        download_file(img_url, img_path)
            
    return caption, img_count

def unsave_post_via_browser(page):
    try:
        selectors = [
            'svg[aria-label="Desmarcar"]',
            'svg[aria-label="Remover"]',
            'svg[aria-label="Remove"]',
            'svg[aria-label="Undo Save"]',
            'svg[aria-label="Saved"]'
        ]
        button_clicked = False
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                print("  [Unsave] Botão de desmarcar guardado clicado no browser.")
                button_clicked = True
                break
        if not button_clicked:
            print("  [Unsave Warning] Botão de desmarcar guardado não encontrado na página.")
        return button_clicked
    except Exception as e:
        print(f"  [Unsave Error] Falha ao desmarcar via browser: {e}")
        return False

# ---------------------------------------------------------------------------
# Funções Auxiliares do Catálogo e API Keys
# ---------------------------------------------------------------------------

def load_gemini_key():
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    if LOCAL_GEMINI_KEY_FILE.exists():
        return LOCAL_GEMINI_KEY_FILE.read_text(encoding="utf-8").strip()
    downloads_key = Path(os.path.expanduser("~/Downloads/gemini_api_key.local.txt"))
    if downloads_key.exists():
        return downloads_key.read_text(encoding="utf-8").strip()
    return ""

def load_progress():
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"processed_shortcodes": []}
    return {"processed_shortcodes": []}

def save_progress(progress):
    PROGRESS_FILE.write_text(
        json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8"
    )

def migrate_existing_folders():
    cwd = Path(".")
    POSTS_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in cwd.iterdir():
        if item.is_dir() and (item.name.startswith("instagram_posts﹨") or item.name.startswith("instagram_posts\\")):
            parts = item.name.split("﹨")
            if len(parts) < 2:
                parts = item.name.split("\\")
            shortcode = parts[-1]
            dest = POSTS_DOWNLOAD_DIR / shortcode
            if dest.exists():
                try:
                    shutil.rmtree(dest)
                except Exception:
                    pass
            try:
                shutil.move(str(item), str(dest))
                count += 1
            except Exception as e:
                print(f"[Aviso] Falha ao migrar {item.name}: {e}")
    if count > 0:
        print(f"[Migração] Migradas {count} pastas de posts para a nova estrutura nested.")

def get_categories_and_sections_prompt(tools_data):
    lines = []
    for cat in tools_data.get("categories", []):
        cat_id = cat.get("id")
        cat_label = cat.get("label")
        lines.append(f"- Categoria: {cat_id} ({cat_label})")
        lines.append("  Secções:")
        for sec in cat.get("sections", []):
            sec_id = sec.get("id")
            sec_label = sec.get("label")
            lines.append(f"    - {sec_id} ({sec_label})")
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

def count_total_cards(tools_data):
    total = 0
    for cat in tools_data.get("categories", []):
        for sec in cat.get("sections", []):
            for card in sec.get("cards", []):
                if card and isinstance(card, dict):
                    total += 1
    return total

def get_existing_shortcodes(tools_data):
    shortcodes = set()
    for cat in tools_data.get("categories", []):
        for sec in cat.get("sections", []):
            for card in sec.get("cards", []):
                if not card or not isinstance(card, dict):
                    continue
                source = card.get("source")
                if not isinstance(source, dict):
                    continue
                src_href = source.get("href")
                if not src_href or not isinstance(src_href, str):
                    continue
                m = re.search(r"/(?:p|reels?|tv)/([A-Za-z0-9_-]+)/?", src_href)
                if m:
                    shortcodes.add(m.group(1))
    return shortcodes

# ---------------------------------------------------------------------------
# Integração Gemini com Rotação de Chaves
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
            
    print(f"  [API Keys] Rotação de API: Chave #{current_client_idx + 1} de {total} selecionada.")
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
            print(f"  [API Keys] A inicializar cliente Gemini para chave #{current_client_idx + 1} de {len(gemini_api_keys)}...")
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
                reason = "limite de quota" if is_quota_error else "chave inválida"
                print(f"  [API Keys] Chave #{current_client_idx + 1} falhou ({reason}). A rodar...")
                gemini_exhausted[current_client_idx] = True
                attempts += 1
                if not rotate_gemini_client():
                    return None
            else:
                print(f"  [API Keys] Erro temporário na chamada (Chave #{current_client_idx + 1}): {e}")
                time.sleep(2)
                attempts += 1
                rotate_gemini_client()
    return None

def extract_tools_from_post(client, caption, image_paths, author_username="", author_fullname=""):
    contents = []
    prompt = f"""
    Analisa o texto da legenda do post do Instagram, as imagens fornecidas (slides do post) e a informação do autor do post:
    - Autor do post (Username): @{author_username}
    - Nome do perfil do autor: {author_fullname}
    - Texto da legenda (Caption):
    \"\"\"
    {caption}
    \"\"\"
    
    Identifica todas as plataformas, websites, aplicações, ferramentas digitais, SaaS, jogos online, recursos web, bibliotecas, extensões, coleções de prompts (de IA ou outras), ou páginas recomendadas ou mencionadas neste post.
    Isto inclui sites de utilidade geral, recursos educativos, entretenimento, jogos, ferramentas de design/produtividade, bem como dicas de apps, tutoriais de ferramentas, truques de software, prompts úteis para ChatGPT/Midjourney/outras IAs ou sugestões de sites.
    
    Para cada item identificado, devolve:
    - name: O nome oficial ou domínio do website/plataforma/jogo/ferramenta (ex: "Framer", "Poki", "remove.bg", "Coursera").
    - description: Uma breve explicação de uma frase sobre o que o recurso faz ou oferece (com base no post).
    - website_hint: O link, domínio ou site correspondente mencionado na legenda ou visível das imagens (ex: "poki.com", "framer.com"). Se não houver, deixa em branco.
    
    Devolve a resposta APENAS como um array JSON válido de objetos com as chaves "name", "description", "website_hint".
    Não adiciones marcações markdown (ex: ```json) nem qualquer outro texto além do JSON puro na resposta.
    """
    contents.append(prompt)
    loaded_images = []
    for p in image_paths:
        try:
            img = Image.open(p).convert("RGB")
            loaded_images.append(img)
        except Exception as e:
            print(f"  [Erro] Falha ao carregar imagem para o Gemini: {e}")
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

def refine_tool_data(client, tool_name, instagram_desc, website_hint, categories_and_sections):
    prompt = f"""
    Estás a catalogar recursos, websites, jogos online, aplicações e ferramentas digitais para um diretório web em Português.
    Encontrámos o seguinte item no Instagram:
    - Nome original: "{tool_name}"
    - Descrição do Instagram: "{instagram_desc}"
    - Dica de Website: "{website_hint}"
    
    Precisas de estruturar e refinar os dados da seguinte forma:
    1. title: O nome oficial e limpo do site/jogo/ferramenta (ex: "Framer", "Remove.bg", "Poki").
    2. href: O link oficial direto para a página inicial correspondente. Deve começar por http:// ou https://.
    3. domain: O domínio raiz limpo (ex: "framer.com").
    4. desc: Uma descrição profissional, concisa e apelativa em PORTUGUÊS resumindo o que este recurso faz ou oferece. Deve ter entre 12 a 25 palavras. Não uses hashtags nem CTAs.
    5. categoryId: O ID da categoria mais adequado a partir da lista fornecida abaixo.
    6. sectionId: O ID da secção mais adequado a partir da lista fornecida abaixo.
    7. badges: Um array de strings que representa o modelo de preços. Escolhe APENAS entre: "Grátis", "Freemium", "Pago". Se não for explícito, escolhe "Freemium".
    
    Lista de Categorias e Secções disponíveis (usa apenas os IDs indicados):
    {categories_and_sections}
    
    Devolve a resposta APENAS como um objeto JSON válido com as chaves: "title", "href", "domain", "desc", "categoryId", "sectionId", "badges".
    Não adiciones marcações markdown nem outro texto além do JSON puro na resposta.
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
# Geração de Relatórios PDF com ReportLab
# ---------------------------------------------------------------------------

def generate_pdf_report(processed_results, filepath):
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
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1b2a24'),
        spaceAfter=10
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
    
    story.append(Paragraph("Relatório de Processamento - Instagram Autofill Tools", title_style))
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    total = len(processed_results)
    added = sum(1 for r in processed_results if "Adicionado" in r["status"])
    ignored = sum(1 for r in processed_results if "Ignorado" in r["status"])
    empty = sum(1 for r in processed_results if "Sem ferramentas" in r["status"])
    errors = sum(1 for r in processed_results if "Erro" in r["status"])
    
    meta_text = (
        f"<b>Data de Execução:</b> {timestamp}<br/>"
        f"<b>Total de Posts Processados:</b> {total} | "
        f"<b>Adicionados:</b> {added} | "
        f"<b>Ignorados (Duplicados):</b> {ignored} | "
        f"<b>Sem Ferramentas:</b> {empty} | "
        f"<b>Erros:</b> {errors}"
    )
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 8))
    
    table_data = [[
        Paragraph("<b>Post (Shortcode)</b>", header_style),
        Paragraph("<b>Status / Ação</b>", header_style),
        Paragraph("<b>Ferramentas Encontradas (Link Oficial)</b>", header_style)
    ]]
    
    for r in processed_results:
        link_html = f"<font color='#34495e'><a href='{r['url']}'>{r['shortcode']}</a></font>"
        status_color = "#27ae60"
        if "Erro" in r["status"]:
            status_color = "#c0392b"
        elif "Ignorado" in r["status"]:
            status_color = "#d35400"
        elif "Sem ferramentas" in r["status"]:
            status_color = "#7f8c8d"
            
        status_html = f"<font color='{status_color}'><b>{r['status']}</b></font>"
        table_data.append([
            Paragraph(link_html, cell_style),
            Paragraph(status_html, cell_style),
            Paragraph(r["tools"], cell_style)
        ])
        
    col_widths = [120, 160, 260]
    t = Table(table_data, colWidths=col_widths)
    
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1b2a24')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#d1d5db')),
    ])
    for i in range(1, len(table_data)):
        bg = colors.HexColor('#f9fafb') if i % 2 == 0 else colors.white
        t_style.add('BACKGROUND', (0, i), (-1, i), bg)
        t_style.add('TOPPADDING', (0, i), (-1, i), 5)
        t_style.add('BOTTOMPADDING', (0, i), (-1, i), 5)
    t.setStyle(t_style)
    story.append(t)
    doc.build(story)
    print(f"\n[Relatório PDF] Ficheiro PDF principal gerado em: {filepath}")

def generate_manual_verification_pdf(empty_or_error_results, filepath):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    if not empty_or_error_results:
        return
    doc = SimpleDocTemplate(
        str(filepath), pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#7f8c8d'), spaceAfter=10
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
    story.append(Paragraph("Verificação Manual - Posts sem Ferramentas ou com Erros", title_style))
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    meta_text = (
        f"<b>Data de Execução:</b> {timestamp}<br/>"
        f"<b>Total de Posts para Verificação Manual:</b> {len(empty_or_error_results)}<br/>"
    )
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 8))
    table_data = [[
        Paragraph("<b>Post (Shortcode)</b>", header_style),
        Paragraph("<b>Status / Motivo</b>", header_style),
        Paragraph("<b>Legenda Original (Snippet)</b>", header_style)
    ]]
    for r in empty_or_error_results:
        link_html = f"<font color='#2980b9'><a href='{r['url']}'>{r['shortcode']}</a></font>"
        status_color = "#7f8c8d"
        if "Erro" in r["status"]:
            status_color = "#c0392b"
        status_html = f"<font color='{status_color}'><b>{r['status']}</b></font>"
        caption_snip = r.get("caption_snippet", "-")
        table_data.append([
            Paragraph(link_html, cell_style),
            Paragraph(status_html, cell_style),
            Paragraph(caption_snip, cell_style)
        ])
    col_widths = [120, 120, 300]
    t = Table(table_data, colWidths=col_widths)
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7f8c8d')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#d1d5db')),
    ])
    for i in range(1, len(table_data)):
        bg = colors.HexColor('#f9fafb') if i % 2 == 0 else colors.white
        t_style.add('BACKGROUND', (0, i), (-1, i), bg)
        t_style.add('TOPPADDING', (0, i), (-1, i), 5)
        t_style.add('BOTTOMPADDING', (0, i), (-1, i), 5)
    t.setStyle(t_style)
    story.append(t)
    doc.build(story)
    print(f"[Relatório PDF] Ficheiro PDF de verificação manual gerado em: {filepath}")

# ---------------------------------------------------------------------------
# Função Principal (Orquestrador)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Autofill tools catalog from Instagram saved posts via Playwright Browser.")
    parser.add_argument("--username", required=True, help="Instagram username.")
    parser.add_argument(
        "--tools-json",
        default=str(Path(__file__).parent / "secret" / "tools-data.json"),
        help="Caminho para o ficheiro tools-data.json"
    )
    parser.add_argument("--limit", type=int, default=0, help="Limite de posts a processar (0 = sem limite)")
    parser.add_argument("--dry-run", action="store_true", help="Executa o processo sem gravar alterações no JSON")
    parser.add_argument("--clear-progress", action="store_true", help="Limpa o histórico de progresso de posts já processados antes de começar")
    args = parser.parse_args()

    # 1. Carregar Chaves Gemini
    api_keys = []
    candidates = [
        LOCAL_GEMINI_KEY_FILE,
        Path("C:/Users/luisf/Downloads") / LOCAL_GEMINI_KEY_FILE,
        Path("C:/Users/luisf/Downloads/Noticias-de-ontem-pt") / LOCAL_GEMINI_KEY_FILE,
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
            print(f"[Erro] Falha ao ler ficheiro de chaves {key_file_found}: {e}")
            
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        for line in env_key.strip().splitlines():
            k = line.strip()
            if k and not k.startswith("#") and k not in api_keys:
                api_keys.append(k)
    if not api_keys:
        print("[Erro] Nenhuma chave GEMINI_API_KEY encontrada.")
        sys.exit(1)
        
    global gemini_api_keys, gemini_clients, gemini_exhausted, current_client_idx
    gemini_api_keys = api_keys
    gemini_clients = [None] * len(api_keys)
    gemini_exhausted = [False] * len(api_keys)
    current_client_idx = 0

    # 2. Carregar tools-data.json
    tools_json_path = Path(args.tools_json)
    if not tools_json_path.exists():
        print(f"[Erro] Ficheiro tools-data.json não encontrado em: {tools_json_path}")
        sys.exit(1)
    try:
        tools_data = json.loads(tools_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[Erro] Falha ao carregar tools-data.json: {e}")
        sys.exit(1)

    categories_and_sections = get_categories_and_sections_prompt(tools_data)
    existing_shortcodes = get_existing_shortcodes(tools_data)
    
    migrate_existing_folders()
    
    progress = load_progress()
    if args.clear_progress:
        progress["processed_shortcodes"] = []
        save_progress(progress)
        print("[Progresso] Histórico de posts processados foi limpo e reiniciado!")

    print(f"Total de cards atualmente no catálogo: {count_total_cards(tools_data)}")
    print(f"Shortcodes já no catálogo: {len(existing_shortcodes)}")
    print(f"Shortcodes marcados como processados anteriormente: {len(progress['processed_shortcodes'])}")

    # 3. Inicializar Playwright e abrir o Brave em modo visível
    brave_exe = find_brave_executable()
    if not brave_exe:
        print("❌ Executável do Brave não encontrado.")
        sys.exit(1)
        
    user_data_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware" / "Brave-Browser" / "User Data"
    
    print("\nA verificar se o Brave está aberto...")
    attempts = 0
    max_attempts = 150
    while is_brave_running() and attempts < max_attempts:
        attempts += 1
        print(f"⚠️ [Brave Aberto] O Brave browser está a correr.")
        print(f"👉 Por favor, FECHA todas as janelas do Brave browser (tentativa {attempts}/{max_attempts})...", flush=True)
        time.sleep(2)
        
    if is_brave_running():
        print("❌ O Brave continuou aberto. Execução abortada.")
        sys.exit(1)
        
    time.sleep(1.5)
    
    playwright_inst = sync_playwright().start()
    print("A abrir o perfil do Brave em modo interativo (headful)...")
    browser_context = None
    try:
        browser_context = playwright_inst.chromium.launch_persistent_context(
            str(user_data_dir),
            executable_path=str(brave_exe),
            headless=False, # Abre a janela para poderes ver os posts a serem desmarcados!
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        page = browser_context.new_page()
        page.set_viewport_size({"width": 1280, "height": 1000})
        
        print("A carregar publicações guardadas (Todas as publicações)...")
        page.goto("https://www.instagram.com/luisflmaximo/saved/all-posts/", timeout=60000)
        page.wait_for_timeout(6000)
        
        if "login" in page.url.lower():
            print("❌ Erro: Sessão não iniciada no Instagram no Brave. Execução abortada.")
            return
            
        # Scroll para carregar os posts mais recentes
        for i in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            
        links = page.locator("a").all()
        shortcodes_on_page = []
        for link in links:
            href = link.get_attribute("href")
            if href:
                m = re.search(r"/(?:p|reel)/([A-Za-z0-9_-]+)/?", href)
                if m:
                    sc = m.group(1)
                    if sc not in shortcodes_on_page:
                        shortcodes_on_page.append(sc)
                        
        print(f"Detetados {len(shortcodes_on_page)} posts na página do Instagram.")
        
        collected_posts = []
        for sc in shortcodes_on_page:
            is_processed = sc in progress["processed_shortcodes"]
            if not is_processed:
                collected_posts.append((None, sc))
                
        print(f"\nPosts novos identificados: {len(collected_posts)}")
        if not collected_posts:
            # Fallback para pastas locais existentes que possam ter sobrado
            print("Nenhum post novo na página. A verificar fallback local de pastas por processar...")
            if POSTS_DOWNLOAD_DIR.exists():
                for item in POSTS_DOWNLOAD_DIR.iterdir():
                    if item.is_dir():
                        sc = item.name
                        if re.match(r"^[A-Za-z0-9_-]+$", sc):
                            is_processed = sc in progress["processed_shortcodes"]
                            if not is_processed:
                                collected_posts.append((None, sc))
            print(f"Posts locais de fallback identificados: {len(collected_posts)}")
            if not collected_posts:
                print("Não há posts novos para processar. Concluído!")
                return
                
        POSTS_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        processed_results = []
        empty_or_error_results = []
        new_cards_added = 0

        # 6. Processar cada post
        for idx, (post, shortcode) in enumerate(collected_posts):
            print(f"\n[{idx+1}/{len(collected_posts)}] A processar post {shortcode}...")
            post_dir = POSTS_DOWNLOAD_DIR / shortcode
            
            # Navegar para o post no browser se não estivermos no fallback local puro
            try:
                page.goto(f"https://www.instagram.com/p/{shortcode}/", timeout=60000)
                page.wait_for_timeout(4000)
                download_success = True
            except Exception as ne:
                print(f"  ❌ Erro ao navegar para o post {shortcode}: {ne}")
                download_success = False
                
            txt_files = list(post_dir.glob("*.txt"))
            jpg_files = list(post_dir.glob("*.jpg")) + list(post_dir.glob("*.jpeg")) + list(post_dir.glob("*.png")) + list(post_dir.glob("*.webp"))
            
            caption = ""
            
            if download_success:
                if txt_files and jpg_files:
                    print(f"  [Arquivo] A utilizar ficheiros locais existentes em: {post_dir}")
                    try:
                        caption = txt_files[0].read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
                else:
                    print(f"  [Download] A descarregar média e legenda via Playwright...")
                    try:
                        caption, img_count = download_post_media_browser(page, post_dir, shortcode)
                        txt_files = list(post_dir.glob("*.txt"))
                        jpg_files = list(post_dir.glob("*.jpg")) + list(post_dir.glob("*.jpeg")) + list(post_dir.glob("*.png")) + list(post_dir.glob("*.webp"))
                    except Exception as de:
                        print(f"  [Erro] Falha ao descarregar post {shortcode}: {de}")
                        download_success = False
            else:
                # Se a navegação falhou, verificar se temos cache local completo
                if txt_files and jpg_files:
                    print(f"  [Arquivo Fallback] A utilizar cache local para post inacessível: {post_dir}")
                    caption = txt_files[0].read_text(encoding="utf-8").strip()
                    download_success = True

            if not download_success:
                processed_results.append({
                    "shortcode": shortcode,
                    "url": f"https://www.instagram.com/p/{shortcode}/",
                    "status": "Erro (Falha ao descarregar)",
                    "tools": "-"
                })
                continue

            print(f"  Legenda obtida (~{len(caption)} carateres). Imagens locais: {len(jpg_files)}")

            # 6.2. Gemini Pass 1: Extrair Ferramentas
            print("  A enviar para o Gemini (Passagem 1 - Extração)...")
            image_paths = [str(f) for f in jpg_files]
            
            # Tentar obter username/nome real do autor a partir da página
            author_username = ""
            author_fullname = ""
            try:
                author_el = page.locator('header a').first
                if author_el.count() > 0:
                    author_username = author_el.inner_text().strip()
            except Exception:
                pass
                
            extracted_tools = run_gemini_operation(extract_tools_from_post, caption, image_paths, author_username=author_username, author_fullname=author_fullname)

            if extracted_tools is None:
                print(f"  ❌ [Erro Crítico] A chamada da API do Gemini falhou para o post {shortcode}. A interromper.")
                sys.exit(1)

            if len(extracted_tools) == 0:
                print("  Nenhuma ferramenta identificada neste post.")
                progress["processed_shortcodes"].append(shortcode)
                save_progress(progress)
                processed_results.append({
                    "shortcode": shortcode,
                    "url": f"https://www.instagram.com/p/{shortcode}/",
                    "status": "Sem ferramentas",
                    "tools": "-"
                })
                if not args.dry_run:
                    unsave_post_via_browser(page)
                continue

            print(f"  Ferramentas encontradas: {', '.join([t.get('name', 'Sem nome') for t in extracted_tools])}")

            # 6.3. Gemini Pass 2: Refinar e Categorizar cada ferramenta
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
                    print(f"  [Ignorado] A ferramenta '{t_name}' já existe: {existing_card.get('title')} ({existing_card.get('href')})")
                    tools_statuses.append(f"Ignorado (Já existe: {t_name})")
                    tools_names_urls.append(f"{t_name} ({existing_card.get('href')})")
                    continue

                print(f"  A refinar dados da ferramenta '{t_name}'...")
                refined = run_gemini_operation(refine_tool_data, t_name, t_desc, t_hint, categories_and_sections)
                if not refined:
                    print(f"  ❌ [Erro Crítico] Todas as chaves da API do Gemini falharam. A interromper.")
                    sys.exit(1)

                existing_card = card_exists(tools_data, refined["href"], refined["domain"], title=refined["title"])
                if existing_card:
                    print(f"  [Ignorado] O URL refinado '{refined['href']}' já está no catálogo.")
                    tools_statuses.append(f"Ignorado (Já existe: {refined['title']})")
                    tools_names_urls.append(f"{refined['title']} ({refined['href']})")
                    continue

                new_card = {
                    "title": refined["title"],
                    "href": refined["href"],
                    "desc": refined["desc"],
                    "search": f"{refined['title'].lower()} {refined['domain'].lower()} {refined['desc'].lower()} instagram.com",
                    "sectionId": refined["sectionId"],
                    "favicon": f"https://www.google.com/s2/favicons?domain={refined['domain']}&sz=32",
                    "domain": refined["domain"],
                    "badges": refined["badges"],
                    "source": {
                        "href": f"https://www.instagram.com/p/{shortcode}/",
                        "label": "instagram.com"
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
                    print(f"  [Aviso] Categoria/Secção '{cat_id}/{sec_id}' não encontrada. Usando 'outros/recursos_uteis'.")
                    for cat in tools_data.get("categories", []):
                        if cat.get("id") == "outros":
                            target_cat = cat
                            for sec in cat.get("sections", []):
                                if sec.get("id") == "recursos_uteis":
                                    target_sec = sec
                                    break
                            break

                if target_sec is not None:
                    if args.dry_run:
                        print(f"  [Dry-Run] Adicionaria '{new_card['title']}' na secção '{target_sec['label']}'")
                        tools_statuses.append(f"Dry-Run: {refined['title']}")
                    else:
                        target_sec.setdefault("cards", []).append(new_card)
                        new_cards_added += 1
                        print(f"  [Adicionado] '{new_card['title']}' na secção '{target_sec['label']}'!")
                        tools_statuses.append(f"Adicionado: {refined['title']}")
                    tools_names_urls.append(f"{refined['title']} ({refined['href']})")

            status_summary = "; ".join(set(tools_statuses)) if tools_statuses else "Nenhuma ferramenta processada"
            tools_summary = "; ".join(tools_names_urls) if tools_names_urls else "-"
            processed_results.append({
                "shortcode": shortcode,
                "url": f"https://www.instagram.com/p/{shortcode}/",
                "status": status_summary,
                "tools": tools_summary
            })

            # 6.4. Unsave do post (Remover dos guardados) no ecrã
            has_added_or_exists = False
            if extracted_tools:
                has_error = any("Erro" in s for s in tools_statuses)
                if not has_error:
                    has_added_or_exists = True

            if has_added_or_exists and not args.dry_run:
                unsave_post_via_browser(page)

            progress["processed_shortcodes"].append(shortcode)
            if not args.dry_run:
                tools_data["totalCount"] = count_total_cards(tools_data)
                tools_json_path.write_text(
                    json.dumps(tools_data, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                save_progress(progress)
                print(f"  Base de dados guardada. Total global de cards: {tools_data['totalCount']}")

        print(f"\nProcessamento concluído com sucesso!")
        print(f"Novos cards adicionados nesta execução: {new_cards_added}")

        # 7. Gerar relatórios PDF
        pdf_path = Path("C:\\Users\\luisf\\Downloads\\autofill_report.pdf")
        try:
            generate_pdf_report(processed_results, pdf_path)
        except Exception as pe:
            print(f"[Erro] Falha ao gerare PDF de relatório principal: {pe}")

        pdf_manual_path = Path("C:\\Users\\luisf\\Downloads\\autofill_manual_verification.pdf")
        try:
            generate_manual_verification_pdf(empty_or_error_results, pdf_manual_path)
        except Exception as pe:
            print(f"[Erro] Falha ao gerar PDF de verificação manual: {pe}")

    finally:
        if browser_context:
            try:
                browser_context.close()
            except Exception:
                pass
        if playwright_inst:
            try:
                playwright_inst.stop()
            except Exception:
                pass


if __name__ == "__main__":
    main()
