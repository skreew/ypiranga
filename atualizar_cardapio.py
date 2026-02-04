import requests
from bs4 import BeautifulSoup
import json
import re
import os

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
    match = re.search(r'url\("?'?([^"')]+)"?'?\)', style_attr)
    if match: return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def buscar_dados():
    print("🔄 Acessando OlaClick...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(URL, headers=headers)
        if response.status_code != 200: return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        cardapio = {}
        
        blocos_categorias = soup.find_all('div', class_='infinite-products')
        
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
                except: continue
            
            if itens_categoria:
                cardapio[nome_categoria] = {
                    "emoji": emoji,
                    "schedule": {"start": "00:00", "end": "23:59"}, 
                    "items": itens_categoria
                }
                print(f"✅ Processado: {nome_categoria}")

        return cardapio

    except Exception as e:
        print(f"Erro: {e}")
        return None

if __name__ == "__main__":
    dados = buscar_dados()
    if dados:
        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print("✨ Sucesso! menu.json atualizado.")
    else:
        print("❌ Falha.")
        exit(1)
