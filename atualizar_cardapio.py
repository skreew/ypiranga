from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import sys
import time

# ================= CONFIGURAÇÕES =================
URL_SITE = "https://cafe-ipiranga.ola.click/products"
URL_API = "https://api.olaclick.com/v1/companies/slug/cafe-ipiranga/products"

# Cabeçalhos para parecer um navegador real (evita 403)
HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
]

# ================= FERRAMENTAS AUXILIARES =================

def limpar_texto(texto):
    """Remove caracteres estranhos e decodifica unicode"""
    if not texto: return ""
    try:
        texto = texto.encode('utf-8').decode('unicode_escape')
        return texto.strip().strip('"').strip("'")
    except:
        return texto

def salvar_menu(dados):
    if dados and len(dados) > 0:
        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print(f"\n✨ SUCESSO! Dados salvos em menu.json.")
        return True
    return False

# ================= ESTRATÉGIAS DE BUSCA =================

def estrategia_1_regex_scanner(html_content):
    print("\n⚔️ [Estratégia 1] Scanner Regex (Força Bruta)...")
    try:
        # Procura por padrões name:"..." e price:123 soltos no HTML
        produtos = []
        matches = re.finditer(r'name\s*:\s*"(?P<name>[^"]+)".*?price\s*:\s*(?P<price>[\d\.]+)', html_content, re.DOTALL | re.IGNORECASE)
        
        seen_names = set()
        
        for match in matches:
            nome = limpar_texto(match.group('name'))
            if nome in seen_names or nome in ["Search Results", "Procurar Resultados"]: continue
            
            # Contexto para buscar descrição e imagem (600 chars ao redor)
            start = match.start()
            end = match.end() + 600
            contexto = html_content[start:end]
            
            desc_match = re.search(r'description\s*:\s*"(?P<desc>[^"]+)"', contexto)
            descricao = limpar_texto(desc_match.group('desc')) if desc_match else ""
            
            img_match = re.search(r'image\s*:\s*"(?P<img>[^"]+)"', contexto)
            imagem = limpar_texto(img_match.group('img')) if img_match else "https://placehold.co/400x300?text=Sem+Imagem"
            
            try:
                p = float(match.group('price'))
                preco = f"R$ {p:.2f}".replace('.', ',')
            except:
                preco = "A consultar"
                
            produtos.append({
                "name": nome,
                "description": descricao,
                "price": preco,
                "image": imagem,
                "addons": []
            })
            seen_names.add(nome)
            
        if produtos:
            print(f"   ✅ Encontrados {len(produtos)} produtos via Regex.")
            # Agrupa tudo em uma categoria geral
            return {"Cardápio": {"emoji": "📋", "items": produtos}}
            
    except Exception as e:
        print(f"   ❌ Erro na Estratégia 1: {e}")
    
    print("   ⚠️ Nenhum produto encontrado com Regex.")
    return None

def estrategia_2_nuxt_state(html_content):
    print("\n🧠 [Estratégia 2] Extração de Estado Nuxt...")
    try:
        match = re.search(r'window\.__NUXT__\s*=\s*\((.*?)\);', html_content)
        if match:
            conteudo_nuxt = match.group(1)
            print("   ✅ Estado Nuxt encontrado. Aplicando Scanner nele...")
            return estrategia_1_regex_scanner(conteudo_nuxt)
    except Exception as e:
        print(f"   ❌ Erro na Estratégia 2: {e}")
    return None

def estrategia_3_api():
    print("\n📡 [Estratégia 3] Acesso Direto à API...")
    try:
        response = requests.get(URL_API, impersonate="chrome110", headers=HEADERS_LIST[0], timeout=15)
        if response.status_code == 200:
            data = response.json()
            items_raw = data.get('data', [])
            produtos = []
            
            for item in items_raw:
                if not item.get('visible', True): continue
                produtos.append({
                    "name": item.get('name'),
                    "description": item.get('description', ''),
                    "price": f"R$ {item.get('price', 0):.2f}".replace('.', ','),
                    "image": item.get('image', "https://placehold.co/400x300?text=Sem+Imagem"),
                    "addons": []
                })
            
            if produtos:
                print(f"   ✅ API funcionou! {len(produtos)} itens.")
                return {"Cardápio API": {"emoji": "⚡", "items": produtos}}
        else:
            print(f"   ⚠️ API bloqueada. Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro na API: {e}")
    return None

# ================= FLUXO PRINCIPAL =================

def main():
    print("🚀 Iniciando robô (Versão Final All-in-One)...")
    
    # 1. Tenta API primeiro (Dados mais limpos)
    dados = estrategia_3_api()
    if salvar_menu(dados): return

    # 2. Se falhar, baixa HTML e tenta Scanner e Nuxt
    html_content = ""
    try:
        print(f"📥 Baixando HTML de: {URL_SITE}")
        resp = requests.get(URL_SITE, impersonate="chrome110", headers=HEADERS_LIST[0], timeout=30)
        if resp.status_code == 200:
            html_content = resp.text
            print(f"   📦 HTML baixado ({len(html_content)} chars).")
            
            dados = estrategia_1_regex_scanner(html_content)
            if salvar_menu(dados): return
            
            dados = estrategia_2_nuxt_state(html_content)
            if salvar_menu(dados): return
            
        else:
            print(f"   ❌ Falha download HTML: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Erro fatal: {e}")

    print("\n💀 FALHA TOTAL: Nenhuma estratégia funcionou.")
    sys.exit(1)

if __name__ == "__main__":
    main()
