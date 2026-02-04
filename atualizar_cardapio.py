import cloudscraper
from bs4 import BeautifulSoup
import json
import re
import sys

# URL do cardápio
URL = "https://cafe-ipiranga.ola.click/products"

def extrair_emoji_e_titulo(texto):
    match = re.match(r'([^\w\s]+)?\s*(.*)', texto)
    if match:
        emoji = match.group(1) if match.group(1) else "🍽️"
        titulo = match.group(2)
        return emoji, titulo
    return "🍽️", texto

def limpar_preco(texto_preco):
    return texto_preco.strip()

def extrair_imagem(style_attr):
    if not style_attr: return "https://placehold.co/400x300?text=Sem+Imagem"
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style_attr)
    if match: return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def buscar_dados():
    print(f"🔄 A iniciar CloudScraper para: {URL}")
    
    # Cria um raspador que simula um browser real (Chrome) para passar proteções
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    try:
        response = scraper.get(URL)
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Erro: Bloqueio persistente. Código: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        cardapio = {}
        
        # O site usa 'infinite-products'
        blocos_categorias = soup.find_all('div', class_='infinite-products')
        
        if not blocos_categorias:
            print("⚠️ Aviso: HTML carregado, mas estrutura não encontrada.")
            # Debug: Salva o HTML para você ver o que o robô viu (opcional)
            # print(soup.prettify()[:500])
            return None
        
        count_itens = 0
        
        for bloco in blocos_categorias:
            header = bloco.find('div', class_='category-view-handler')
            if not header: continue
                
            titulo_raw = header.find('h2').get_text(strip=True)
            emoji, nome_categoria = extrair_emoji_e_titulo(titulo_raw)
            
            if "Procurar Resultados" in nome_categoria: continue

            itens_categoria = []
            produtos_div = bloco.find('div', class_='products')
            if not produtos_div: continue
                
            cards = produtos_div.find_all('a', class_='product-card')
            
            for card in cards:
                try:
                    nome = card.find('div', class_='product-card__title').get_text(strip=True)
                    
                    desc_div = card.find('div', class_='product-card__description')
                    descricao = desc_div.get_text(strip=True) if desc_div else ""
                    
                    preco_div = card.find('span', class_='product__price')
                    preco = limpar_preco(preco_div.get_text(strip=True)) if preco_div else "A consultar"
                    
                    img_div = card.find('div', class_='v-image__image')
                    style = img_div.get('style') if img_div else ""
                    imagem = extrair_imagem(style)
                    
                    itens_categoria.append({
                        "name": nome,
                        "description": descricao,
                        "price": preco,
                        "image": imagem,
                        "addons": []
                    })
                    count_itens += 1
                except: continue
            
            if itens_categoria:
                cardapio[nome_categoria] = {
                    "emoji": emoji,
                    "schedule": {"start": "00:00", "end": "23:59"}, 
                    "items": itens_categoria
                }
                print(f"✅ Processado: {nome_categoria} ({len(itens_categoria)} itens)")

        print(f"📊 Total de itens extraídos: {count_itens}")
        return cardapio

    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        return None

if __name__ == "__main__":
    dados = buscar_dados()
    
    if dados and len(dados) > 0:
        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print("\n✨ Sucesso! 'menu.json' atualizado.")
    else:
        print("\n❌ Falha: Nenhum dado extraído.")
        sys.exit(1)
