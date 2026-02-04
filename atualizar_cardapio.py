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

def buscar_dados():
    print(f"🔄 Acessando: {URL}")
    
    try:
        # Tenta imitar um navegador mobile para garantir que o site carregue versão leve
        response = requests.get(
            URL, 
            impersonate="chrome110", 
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Erro: Status {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        cardapio = {}
        count_itens = 0

        # --- TENTATIVA 1: Busca Genérica por HTML (ignorando estrutura antiga) ---
        print("🔎 Tentando encontrar cartões de produto no HTML...")
        all_cards = soup.select('a.product-card') # Procura links com classe product-card em qualquer lugar
        
        if all_cards:
            print(f"✅ Encontrados {len(all_cards)} cartões via busca genérica.")
            
            # Agrupa tudo em uma categoria "Geral" temporária se não conseguir separar
            itens_processados = []
            for card in all_cards:
                try:
                    nome = card.find('div', class_='product-card__title').get_text(strip=True)
                    desc = card.find('div', class_='product-card__description')
                    descricao = desc.get_text(strip=True) if desc else ""
                    
                    preco_el = card.find('span', class_='product__price')
                    preco = preco_el.get_text(strip=True).strip() if preco_el else "A consultar"
                    
                    img_div = card.find('div', class_='v-image__image')
                    imagem = "https://placehold.co/400x300?text=Sem+Imagem"
                    if img_div and img_div.get('style'):
                        match_img = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', img_div.get('style'))
                        if match_img: imagem = match_img.group(1)

                    itens_processados.append({
                        "name": nome,
                        "description": descricao,
                        "price": preco,
                        "image": imagem,
                        "addons": []
                    })
                    count_itens += 1
                except: continue
            
            if itens_processados:
                # Tenta agrupar por categorias se possível, senão joga em Destaques
                cardapio["Destaques"] = {
                    "emoji": "⭐",
                    "schedule": {"start": "00:00", "end": "23:59"},
                    "items": itens_processados
                }
                return cardapio

        # --- TENTATIVA 2: Busca por JSON (Dados ocultos) ---
        print("🕵️ HTML vazio de produtos. Procurando dados JSON ocultos...")
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and ('products' in script.string or 'menu' in script.string):
                # Aqui tentariamos extrair JSON complexo, mas por enquanto vamos apenas avisar
                print("   ⚠️ Encontrado script suspeito contendo 'products'.")
        
        # --- FALHA: Imprime HTML para debug ---
        if count_itens == 0:
            print("\n❌ NENHUM PRODUTO ENCONTRADO.")
            print("👇 DUMP DO HTML (Copie isso se precisar de ajuda):")
            print("-" * 20)
            print(soup.prettify()[:4000]) # Imprime os primeiros 4000 caracteres
            print("-" * 20)
            print("👆 FIM DO DUMP")
            return None

        return cardapio

    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        return None

if __name__ == "__main__":
    dados = buscar_dados()
    if dados:
        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print("\n✨ Sucesso! menu.json salvo.")
    else:
        sys.exit(1)
