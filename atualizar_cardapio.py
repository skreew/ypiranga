import requests
from bs4 import BeautifulSoup
import json
import re
import sys

# URL do cardápio original
URL = "https://cafe-ipiranga.ola.click/products"

def extrair_emoji_e_titulo(texto):
    # Tenta separar o emoji do texto (ex: "☕ CAFÉS")
    match = re.match(r'([^\w\s]+)?\s*(.*)', texto)
    if match:
        emoji = match.group(1) if match.group(1) else "🍽️"
        titulo = match.group(2)
        return emoji, titulo
    return "🍽️", texto

def limpar_preco(texto_preco):
    # Remove espaços extras do preço
    return texto_preco.strip()

def extrair_imagem(style_attr):
    # Extrai a URL de dentro de style="background-image: url('...')"
    if not style_attr:
        return "https://placehold.co/400x300?text=Sem+Imagem"
    
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style_attr)
    if match:
        return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def buscar_dados():
    print(f"🔄 A tentar aceder: {URL}")
    
    # Cabeçalhos completos para parecer um navegador real
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    try:
        session = requests.Session()
        response = session.get(URL, headers=headers, timeout=20)
        
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Erro: O site bloqueou ou não respondeu. Código: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        cardapio = {}
        
        # O site usa 'infinite-products' para agrupar categorias
        blocos_categorias = soup.find_all('div', class_='infinite-products')
        
        if not blocos_categorias:
            print("⚠️ Aviso: A página carregou, mas não encontrei a estrutura 'infinite-products'.")
            print("Pode ser um bloqueio de JavaScript ou mudança de layout.")
            # Tenta imprimir um pedaço do HTML para debug (opcional)
            # print(soup.prettify()[:1000]) 
            return None
        
        count_itens = 0
        
        for bloco in blocos_categorias:
            # Achar titulo da categoria
            header = bloco.find('div', class_='category-view-handler')
            if not header:
                continue
                
            titulo_raw = header.find('h2').get_text(strip=True)
            emoji, nome_categoria = extrair_emoji_e_titulo(titulo_raw)
            
            # Ignorar categoria de busca interna deles
            if "Procurar Resultados" in nome_categoria:
                continue

            itens_categoria = []
            
            # Achar produtos dentro desta categoria
            produtos_div = bloco.find('div', class_='products')
            if not produtos_div:
                continue
                
            cards = produtos_div.find_all('a', class_='product-card')
            
            for card in cards:
                try:
                    # Nome
                    nome_div = card.find('div', class_='product-card__title')
                    if not nome_div: continue
                    nome = nome_div.get_text(strip=True)
                    
                    # Descrição (alguns não têm)
                    desc_div = card.find('div', class_='product-card__description')
                    descricao = desc_div.get_text(strip=True) if desc_div else ""
                    
                    # Preço
                    preco_div = card.find('span', class_='product__price')
                    preco = limpar_preco(preco_div.get_text(strip=True)) if preco_div else "A consultar"
                    
                    # Imagem
                    img_div = card.find('div', class_='v-image__image')
                    style = img_div.get('style') if img_div else ""
                    imagem = extrair_imagem(style)
                    
                    # Monta o objeto do produto
                    itens_categoria.append({
                        "name": nome,
                        "description": descricao,
                        "price": preco,
                        "image": imagem,
                        "addons": [] 
                    })
                    count_itens += 1
                    
                except Exception as e:
                    # Ignora erros num produto específico para não parar tudo
                    continue
            
            if itens_categoria:
                cardapio[nome_categoria] = {
                    "emoji": emoji,
                    "schedule": {"start": "00:00", "end": "23:59"}, 
                    "items": itens_categoria
                }
                print(f"✅ Processado: {nome_categoria} ({len(itens_categoria)} itens)")

        print(f"📊 Total de itens encontrados: {count_itens}")
        return cardapio

    except Exception as e:
        print(f"❌ Erro fatal no script: {e}")
        return None

if __name__ == "__main__":
    dados = buscar_dados()
    
    if dados and len(dados) > 0:
        # Salva o arquivo json
        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print("\n✨ Sucesso! Arquivo 'menu.json' atualizado.")
    else:
        print("\n❌ Falha: Nenhum dado foi extraído. O menu.json não será alterado.")
        sys.exit(1) # Força erro no GitHub Actions para avisar que falhou
