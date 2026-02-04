from curl_cffi import requests
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
    print(f"🔄 A iniciar acesso via curl_cffi para: {URL}")
    
    try:
        response = requests.get(URL, impersonate="chrome110", timeout=30)
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Erro: O site bloqueou. Código: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # DEBUG: Verifica se o site retornou conteúdo vazio ou pede JS
        if "You need to enable JavaScript" in response.text:
            print("🚨 ALERTA: O site exige JavaScript e não entregou o HTML completo.")
        
        # Tenta encontrar os blocos de categorias
        blocos_categorias = soup.find_all('div', class_='infinite-products')
        
        # Se não achou blocos, imprime o que achou para a gente debugar
        if not blocos_categorias:
            print("⚠️ Aviso: Estrutura 'infinite-products' NÃO encontrada.")
            print("--- INÍCIO DO HTML RECEBIDO ---")
            print(soup.prettify()[:2000]) # Mostra os primeiros 2000 caracteres
            print("--- FIM DO HTML PREVIEW ---")
            return None
        
        print(f"🔍 Encontrados {len(blocos_categorias)} blocos de categorias (infinite-products).")
        
        cardapio = {}
        count_itens = 0
        
        for i, bloco in enumerate(blocos_categorias):
            header = bloco.find('div', class_='category-view-handler')
            if not header:
                print(f"   🔸 Bloco {i} ignorado: sem cabeçalho.")
                continue
                
            titulo_raw = header.find('h2').get_text(strip=True)
            emoji, nome_categoria = extrair_emoji_e_titulo(titulo_raw)
            
            if "Procurar Resultados" in nome_categoria: continue

            itens_categoria = []
            produtos_div = bloco.find('div', class_='products')
            
            if not produtos_div:
                print(f"   🔸 Categoria '{nome_categoria}' ignorada: div 'products' não encontrada.")
                continue
                
            cards = produtos_div.find_all('a', class_='product-card')
            print(f"   🔹 Processando '{nome_categoria}': {len(cards)} cartões encontrados.")
            
            for card in cards:
                try:
                    # Tenta extrair cada campo e avisa se falhar
                    nome_elem = card.find('div', class_='product-card__title')
                    if not nome_elem: raise Exception("Título não encontrado")
                    nome = nome_elem.get_text(strip=True)
                    
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
                except Exception as e:
                    print(f"      ❌ Erro ao ler item: {e}")
                    # print(f"      HTML do erro: {str(card)[:100]}...") # Descomente se precisar de muito detalhe
                    continue
            
            if itens_categoria:
                cardapio[nome_categoria] = {
                    "emoji": emoji,
                    "schedule": {"start": "00:00", "end": "23:59"}, 
                    "items": itens_categoria
                }

        print(f"📊 Total de itens extraídos com sucesso: {count_itens}")
        return cardapio

    except Exception as e:
        print(f"❌ Erro fatal no script: {e}")
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
