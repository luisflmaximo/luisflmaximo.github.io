import json
import os
import sys
import re
import urllib.request
import time
from pathlib import Path

# Ajustar stdout para UTF-8 no Windows
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db_path = Path(r"c:\Users\luisf\Downloads\portefolio\secret\tools-data.json")
key_file = Path(r"c:\Users\luisf\Downloads\portefolio\gemini_api_key.local.txt")

# Obter chave do Gemini
api_key = ""
if key_file.exists():
    try:
        api_key = key_file.read_text(encoding="utf-8").splitlines()[0].strip()
    except Exception as e:
        print(f"Erro ao ler arquivo de chave: {e}")

def call_gemini(prompt):
    if not api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    max_retries = 5
    backoff = 2
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                text = res_data['candidates'][0]['content']['parts'][0]['text']
                return text.strip()
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                print(f"  [Gemini Rate Limit] 429 recebido. A aguardar {backoff}s antes de tentar novamente (tentativa {attempt+1}/{max_retries})...")
                time.sleep(backoff)
                backoff *= 2
            else:
                print(f"  [Gemini Erro] Falha na chamada da API: {e}")
                break
    return None

def get_steam_game_details(app_id):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=pt&l=portuguese"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data and data.get(app_id) and data[app_id].get("success"):
                return data[app_id]["data"]
    except Exception as e:
        print(f"  [Steam API Erro] AppID {app_id}: {e}")
    return None

def fetch_og_image(url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Buscar og:image ou twitter:image
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
            if not match:
                match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
            if not match:
                match = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html)
                
            if match:
                img_url = match.group(1).strip()
                # Resolver URLs relativos básicos
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                return img_url
    except Exception as e:
        pass
    return None

def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("====== MODO DRY-RUN: NENHUMA ALTERAÇÃO SERÁ SALVA ======")
    else:
        print("====== EXECUTANDO ALTERAÇÕES REAIS NO BANCO DE DADOS ======")
        
    if not db_path.exists():
        print(f"Erro: Arquivo {db_path} não encontrado.")
        sys.exit(1)
        
    with open(db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    categories = data.get("categories", [])
    
    total_games = 0
    games_with_source_removed = 0
    favicons_updated = 0
    unreleased_updated = 0
    descriptions_corrected = 0
    
    for cat in categories:
        cat_id = cat.get("id")
        for sec in cat.get("sections", []):
            for card in sec.get("cards", []):
                href = card.get("href", "")
                title = card.get("title", "")
                
                # Se for jogo, aplicar regras de jogos
                if cat_id == "jogos":
                    total_games += 1
                    
                    # A. Remover source dos jogos
                    if card.get("source") is not None:
                        games_with_source_removed += 1
                        if not dry_run:
                            card["source"] = None
                            
                    # B. Atualizar favicon de jogos
                    favicon = card.get("favicon", "")
                    domain = card.get("domain", "")
                    
                    if "store.steampowered.com" in href:
                        match = re.search(r'/app/(\d+)', href)
                        if match:
                            app_id = match.group(1)
                            steam_capsule = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app_id}/capsule_231x87.jpg"
                            if favicon != steam_capsule:
                                favicons_updated += 1
                                print(f"[{title}] Atualizando favicon para banner do Steam: {steam_capsule}")
                                if not dry_run:
                                    card["favicon"] = steam_capsule
                                    
                            # C. Verificar se o jogo é Coming Soon e atualizar o badge
                            badges = card.get("badges", [])
                            has_ver_preco = False
                            price_badge_index = -1
                            for idx, b in enumerate(badges):
                                if isinstance(b, dict):
                                    lbl = b.get("label", "").lower()
                                else:
                                    lbl = str(b).lower()
                                if lbl in ["ver preço", "ver preco"]:
                                    has_ver_preco = True
                                    price_badge_index = idx
                                    break
                                    
                            if has_ver_preco:
                                steam_data = get_steam_game_details(app_id)
                                if steam_data:
                                    coming_soon = steam_data.get("release_date", {}).get("coming_soon", False)
                                    if coming_soon:
                                        unreleased_updated += 1
                                        print(f"[{title}] Jogo não lançado detetado! Alterando badge para 'Em breve'.")
                                        if not dry_run:
                                            # Substituir badge de preço por badge-soon com label "Em breve"
                                            new_badge = {"className": "badge-soon", "label": "Em breve"}
                                            if price_badge_index != -1:
                                                badges[price_badge_index] = new_badge
                                            else:
                                                badges.append(new_badge)
                                            card["badges"] = badges
                                            
                                            # Se a descrição estiver truncada, carregar a descrição curta oficial
                                            desc = card.get("desc", "").strip()
                                            if desc.endswith("...") or desc.endswith("..") or len(desc) < 30:
                                                short_desc = steam_data.get("short_description", "").strip()
                                                if short_desc:
                                                    print(f"  -> Corrigindo descrição truncada usando dados oficiais do Steam.")
                                                    card["desc"] = short_desc
                                                    descriptions_corrected += 1
                                    else:
                                        # Se já lançou e tem preço na Steam, atualizar o preço!
                                        price_overview = steam_data.get("price_overview")
                                        if price_overview and not dry_run:
                                            final_price = price_overview.get("final_formatted")
                                            discount = price_overview.get("discount_percent", 0)
                                            if final_price:
                                                new_badges = []
                                                for b in badges:
                                                    lbl = b.get("label", "") if isinstance(b, dict) else str(b)
                                                    cname = b.get("className", "") if isinstance(b, dict) else ""
                                                    if "price" not in cname.lower() and "check" not in cname.lower() and "discount" not in cname.lower() and lbl.lower() not in ["pago", "grátis", "gratis"]:
                                                        new_badges.append(b)
                                                
                                                if discount > 0:
                                                    new_badges.append({"className": "badge-discount", "label": f"-{discount}%"})
                                                new_badges.append({"className": "badge-price", "label": final_price})
                                                card["badges"] = new_badges
                                                print(f"[{title}] Preço atualizado para {final_price} (Desconto: {discount}%)")
                    else:
                        # Outras plataformas de jogos (Nintendo, Itch.io)
                        if "nintendo" in domain or "itch.io" in domain or "poki" in domain:
                            if "favicons?domain=" in favicon or not favicon:
                                og_img = fetch_og_image(href)
                                if og_img:
                                    favicons_updated += 1
                                    print(f"[{title}] Favicon genérico detetado. Atualizando para og:image: {og_img}")
                                    if not dry_run:
                                        card["favicon"] = og_img
                                        
                # 2. Correção de Descrições Truncadas / Mal Formadas para todos os cards
                desc = card.get("desc", "").strip()
                is_truncated = desc.endswith("...") or desc.endswith("..")
                is_incomplete = not re.search(r'[.!?\"\'»]$', desc) and len(desc) > 30 and cat_id != "universidade"
                
                if (is_truncated or is_incomplete) and cat_id != "jogos":
                    print(f"[{title}] Descrição suspeita detetada: '{desc}'")
                    prompt = f"Corrige e completa a seguinte descrição de ferramenta/recurso em português de Portugal (PT-PT) correto e natural. A frase deve ser bem escrita, completa e terminar com pontuação final adequada (. ! ou ?). Retorna apenas a descrição corrigida, sem explicações adicionais, sem aspas adicionais e sem formatação markdown:\n\n{desc}"
                    corrected = call_gemini(prompt)
                    if corrected:
                        descriptions_corrected += 1
                        print(f"  -> Corrigida: '{corrected}'")
                        if not dry_run:
                            card["desc"] = corrected
                            
                # Reconstruir o campo 'search' para garantir consistência
                if not dry_run:
                    src_obj = card.get("source")
                    src_label = src_obj.get("label", "") if isinstance(src_obj, dict) else ""
                    card["search"] = " ".join([
                        card.get("title", ""),
                        card.get("domain", ""),
                        card.get("desc", ""),
                        src_label
                    ]).lower().strip()
                    
    print("\n====== RESUMO DA AUDITORIA ======")
    print(f"Total de jogos analisados: {total_games}")
    print(f"Jogos com source removido: {games_with_source_removed}")
    print(f"Favicons/Miniaturas atualizados: {favicons_updated}")
    print(f"Jogos não lançados atualizados para 'Em breve': {unreleased_updated}")
    print(f"Descrições corrigidas/completadas: {descriptions_corrected}")
    
    if not dry_run:
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("\nAlterações guardadas com sucesso em tools-data.json!")
        
if __name__ == "__main__":
    main()
