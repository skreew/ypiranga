from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import sys

# Configurações do Alvo
SLUG = "cafe-ipiranga"
COMPANY_ID = "5020ff7e-3077-4507-911a-7820e15488e3" # Extraído dos logs anteriores
URL_SITE = f"https://{SLUG}.ola.click/products"

# APIs prováveis do OlaClick (v1 e v2)
URL_API_V1 = f"https://api.olaclick.com/v1/companies/{COMPANY_ID}/products"
URL_API_SLUG = f"https://api.olaclick.com/v1/companies/slug/{SLUG}/products"

def buscar_dados_api():
    """Tenta pegar os dados direto da API (mais limpo e confiável)"""
    print(f"🔄 Tentando acesso via API para ID: {COMPANY_ID}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": f"https://{SLUG}.ola.click",
        "Referer": f"https://{SLUG}.ola.click/"
    }

    # Lista de tentativas de URL da API
    urls_tentativa = [URL_API_V1, URL_API_SLUG]

    for url in urls_tentativa:
        try:
            print(f"   📡 Testando endpoint: {url}")
            response = requests.get(url, impersonate="chrome110", headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                # Verifica se retornou uma lista de produtos ou um objeto com 'data'
                produtos = data.get('data', data) if isinstance(data, dict) else data
                
                if produtos and isinstance(produtos, list) and len(produtos) > 0:
                    print(f"   ✅ Sucesso! API retornou {len(produtos)} registros.")
                    return processar_json_api(produtos)
            else:
                print(f"   ⚠️ Falha na API ({response.status_code}).")
        except Exception as e:
            print(f"   ❌ Erro ao conectar na API: {e}")

    return None

def processar_json_api(produtos_raw):
    """Converte o JSON bruto da API para o formato do nosso menu.json"""
    cardapio = {}
    count = 0
    
    # Ordena para garantir consistência
    # A estrutura do OlaClick geralmente tem 'category' dentro do produto ou agrupa
    
    for item in produtos_raw:
        try:
            # Proteção contra campos nulos
            if not item.get('visible', True): continue 

            categoria_obj = item.get('category', {})
            nome_categoria = categoria_obj.get('name', 'Outros') if categoria_obj else 'Outros'
            
            # Remove emojis duplicados do nome da categoria se houver
            nome_categoria = re.sub(r'^[^\w\s]+', '', nome_categoria).strip()
            
            if nome_categoria not in cardapio:
                cardapio[nome_categoria] = {
                    "emoji": "🍽️", # Podemos tentar mapear emojis fixos depois
                    "items": []
                }
            
            # Tratamento de Imagem
            imagem = "https://placehold.co/400x300?text=Sem+Imagem"
            if item.get('image'):
                imagem = item.get('image')
            
            # Tratamento de Preço
            preco = item.get('price', 0)
            preco_str = f"R$ {preco:.2f}".replace('.', ',')

            cardapio[nome_categoria]["items"].append({
                "name": item.get('name', 'Sem Nome').strip(),
                "description": item.get('description', '').strip(),
                "price": preco_str,
                "image": imagem,
                "addons": [] # Futuramente podemos processar os 'optionGroups'
            })
            count += 1
        except Exception as e:
            print(f"Erro ao processar item: {e}")
            continue

    print(f"📊 Processamento concluído: {count} itens organizados.")
    return cardapio

def buscar_dados_html_fallback():
    """Fallback: Tenta encontrar o JSON escondido no HTML (window.__NUXT__)"""
    print("🕵️ API falhou. Tentando extrair estado oculto no HTML...")
    try:
        response = requests.get(URL_SITE, impersonate="chrome110", timeout=30)
        content = response.text
        
        # Procura por JSON de produtos dentro do Javascript
        # Padrão: "products":[ ... ]
        match = re.search(r'["\']products["\']\s*:\s*(\[.*?\])', content)
        if match:
            print("   ✅ Encontrada lista de produtos no HTML!")
            json_str = match.group(1)
            # Tenta limpar o JSON se estiver mal formatado (comum em JS objects)
            try:
                produtos = json.loads(json_str)
                return processar_json_api(produtos)
            except:
                print("   ⚠️ Conteúdo encontrado não é JSON válido.")
        
        return None
    except Exception as e:
        print(f"❌ Erro no fallback: {e}")
        return None

if __name__ == "__main__":
    # 1. Tenta via API (Melhor método)
    dados = buscar_dados_api()
    
    # 2. Se falhar, tenta via HTML Scrape (Backup)
    if not dados:
        dados = buscar_dados_html_fallback()

    if dados and len(dados) > 0:
        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print("\n✨ Sucesso! 'menu.json' atualizado.")
    else:
        print("\n❌ Falha Fatal: Não foi possível obter dados nem por API nem por HTML.")
        sys.exit(1)
