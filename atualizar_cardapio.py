from playwright.sync_api import sync_playwright
import json
import re
import sys
import time

URL_SITE = "https://cafe-ipiranga.ola.click/products"

# ==============================================================================
# 🛠️ CONFIGURAÇÃO ESTRUTURADA E INTERATIVA DOS ADICIONAIS
# Agora com regras de interatividade (min/max/obrigatório)
# ==============================================================================

# GRUPO: Ponto da Carne (Obrigatório, Escolha 1)
GRP_PONTO_CARNE = {
    "group_name": "Escolha o ponto da carne",
    "required": True,
    "min": 1,
    "max": 1,
    "options": [
        {"name": "Mal Passado", "price": "Grátis"},
        {"name": "Ao Ponto", "price": "Grátis"},
        {"name": "Bem Passado", "price": "Grátis"}
    ]
}

# GRUPO: Bordas de Pizza (Opcional, Escolha 1)
GRP_BORDA = {
    "group_name": "Escolha a Borda",
    "required": False,
    "min": 0,
    "max": 1,
    "options": [
        {"name": "Sem Borda", "price": "Grátis"},
        {"name": "Catupiry", "price": "R$ 12,00"},
        {"name": "Cheddar", "price": "R$ 12,00"},
        {"name": "Chocolate", "price": "R$ 15,00"}
    ]
}

# GRUPO: Extras de Lanche (Opcional, Vários)
GRP_EXTRAS_LANCHE = {
    "group_name": "Turbine seu lanche",
    "required": False,
    "min": 0,
    "max": 5,
    "options": [
        {"name": "Bacon (3 fatias)", "price": "R$ 5,00"},
        {"name": "Queijo Extra", "price": "R$ 2,00"},
        {"name": "Hambúrguer Extra", "price": "R$ 8,00"},
        {"name": "Fritas (100g)", "price": "R$ 10,00"}
    ]
}

# GRUPO: Molhos (Opcional, Vários)
GRP_MOLHOS = {
    "group_name": "Molhos",
    "required": False,
    "min": 0,
    "max": 3,
    "options": [
        {"name": "Maionese da Casa", "price": "Grátis"},
        {"name": "Ketchup", "price": "Grátis"},
        {"name": "Barbecue", "price": "Grátis"},
        {"name": "Mostarda", "price": "Grátis"}
    ]
}

# GRUPO: Adicionais Café (Opcional, Vários)
GRP_EXTRAS_CAFE = {
    "group_name": "Personalize seu café",
    "required": False,
    "min": 0,
    "max": 3,
    "options": [
        {"name": "Leite de Castanha", "price": "R$ 4,00"},
        {"name": "Zero Lactose/Aveia", "price": "R$ 4,00"},
        {"name": "Nutella", "price": "R$ 4,00"},
        {"name": "Chantilly", "price": "R$ 4,00"}
    ]
}

# ==============================================================================

def processar_preco(texto):
    if not texto: return "A consultar"
    limpo = texto.replace('R$', '').replace('Adicionais', '').strip()
    return f"R$ {limpo}"

def extrair_imagem(style):
    if not style: return "https://placehold.co/400x300?text=Sem+Imagem"
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
    if match: return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def extrair_horario(titulo_categoria):
    match = re.search(r'(\d{2}:\d{2})\s*[-àa]\s*(\d{2}:\d{2})', titulo_categoria)
    if match: return match.group(1), match.group(2)
    return "00:00", "23:59"

def obter_adicionais_por_categoria(nome_categoria):
    """
    Lógica 'Cirúrgica': Só adiciona se tiver certeza absoluta.
    Evita colocar adicionais em tudo.
    """
    cat = nome_categoria.upper()
    grupos_finais = []

    # 1. PIZZAS (Apenas Borda)
    if "PIZZA" in cat:
        grupos_finais.append(GRP_BORDA)

    # 2. HAMBÚRGUERES (Ponto + Extras + Molhos)
    # Exclui "Sanduíches" simples dessa regra pesada
    elif "BURGUER" in cat or "PRIME" in cat:
        grupos_finais.append(GRP_PONTO_CARNE)
        grupos_finais.append(GRP_EXTRAS_LANCHE)
        grupos_finais.append(GRP_MOLHOS)

    # 3. CARNES / PRATOS COM STEAK (Ponto + Molhos)
    elif "STEAK" in cat or "MIGNON" in cat or "COSTELA" in cat:
        grupos_finais.append(GRP_PONTO_CARNE)
        # Se quiser molhos no prato, descomente abaixo:
        # grupos_finais.append(GRP_MOLHOS)

    # 4. CAFÉS ESPECIAIS (Cappuccino, Mocha, etc - Evita café simples se quiser)
    elif any(x in cat for x in ["CAPPUCCINO", "CHOCOLATE", "FRAPÊ", "ESPECIAIS"]):
        grupos_finais.append(GRP_EXTRAS_CAFE)

    # 5. LANCHES GERAIS (Só Molhos e Extras leves, sem ponto da carne)
    elif "LANCHE" in cat or "SANDUÍCHE" in cat or "BAURU" in cat:
        # Cria uma versão leve dos extras (sem batata 100g obrigatória, etc)
        grupos_finais.append(GRP_EXTRAS_LANCHE) 
        grupos_finais.append(GRP_MOLHOS)

    # NOTA: Sucos, Drinks, Porções, Salgados NÃO entram aqui. 
    # Ficarão com "addons": []
    
    return grupos_finais

def run():
    print("🔥 Iniciando Atualização (Modo Limpo e Interativo)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            viewport={'width': 390, 'height': 844},
            device_scale_factor=2
        )
        
        page = context.new_page()
        
        try:
            print(f"🔄 Acessando: {URL_SITE}")
            page.goto(URL_SITE, timeout=90000, wait_until="domcontentloaded")
            
            try:
                page.wait_for_selector('.product-card', timeout=20000)
            except:
                print("⚠️ Demorou para carregar...")

            banco_dados_mestre = {}
            previous_height = 0
            no_change_count = 0
            
            print("🚜 Rolando página...")
            
            while True:
                dados_tela = page.evaluate("""() => {
                    const dados = [];
                    const cats = document.querySelectorAll('.infinite-products');
                    
                    cats.forEach(cat => {
                        const titleEl = cat.querySelector('.category-view-handler h2');
                        if (!titleEl) return;
                        
                        let catName = titleEl.innerText.trim();
                        if (catName.includes('Procurar Resultados')) return;
                        
                        let emoji = "🍽️";
                        const emojiMatch = catName.match(/^([^\w\s]+)?\s*(.*)/);
                        if (emojiMatch) {
                            if(emojiMatch[1]) emoji = emojiMatch[1];
                            catName = emojiMatch[2] ? emojiMatch[2] : catName;
                        }

                        const items = [];
                        const products = cat.querySelectorAll('.product-card');
                        
                        products.forEach(p => {
                            const nome = p.querySelector('.product-card__title')?.innerText.trim();
                            const desc = p.querySelector('.product-card__description')?.innerText.trim();
                            const price = p.querySelector('.product__price')?.innerText.trim();
                            const imgStyle = p.querySelector('.v-image__image')?.getAttribute('style');
                            
                            if (nome) {
                                items.push({
                                    name: nome,
                                    description: desc || '',
                                    price: price || 'A consultar',
                                    imageStyle: imgStyle || ''
                                });
                            }
                        });

                        if (items.length > 0) {
                            dados.push({
                                category: catName,
                                emoji: emoji,
                                items: items
                            });
                        }
                    });
                    return dados;
                }""")

                for cat in dados_tela:
                    nome_raw = cat['category']
                    if nome_raw not in banco_dados_mestre:
                        inicio, fim = extrair_horario(nome_raw)
                        nome_limpo = re.sub(r'\d{2}:\d{2}.*', '', nome_raw).strip().replace('-', '').strip()
                        
                        banco_dados_mestre[nome_raw] = {
                            "clean_name": nome_limpo,
                            "emoji": cat['emoji'],
                            "start": inicio,
                            "end": fim,
                            "items_dict": {}
                        }
                    
                    for item in cat['items']:
                        if item['name'] not in banco_dados_mestre[nome_raw]["items_dict"]:
                            banco_dados_mestre[nome_raw]["items_dict"][item['name']] = item

                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(1.5)

                new_height = page.evaluate("window.scrollY + window.innerHeight")
                total_height = page.evaluate("document.body.scrollHeight")
                
                print(f"   ⬇️  Scroll: {int(new_height)} / {int(total_height)}")

                if new_height >= total_height:
                    time.sleep(3)
                    if page.evaluate("document.body.scrollHeight") == total_height:
                        break
                
                if previous_height == new_height:
                    no_change_count += 1
                    if no_change_count > 5: break
                else:
                    no_change_count = 0
                previous_height = new_height

            print("📦 Aplicando regras de adicionais...")
            cardapio_final = {}
            total_items_count = 0
            
            for key_cat, dados_cat in banco_dados_mestre.items():
                nome_categoria = dados_cat["clean_name"]
                
                # AQUI É O PULO DO GATO:
                # Pegamos os grupos estruturados (obrigatório/opcional)
                grupos_adicionais = obter_adicionais_por_categoria(nome_categoria)
                
                items_lista = []
                for nome_item, item_raw in dados_cat["items_dict"].items():
                    items_lista.append({
                        "name": item_raw['name'],
                        "description": item_raw['description'],
                        "price": processar_preco(item_raw['price']),
                        "image": extrair_imagem(item_raw['imageStyle']),
                        "addons": grupos_adicionais # Lista de grupos, não de itens soltos
                    })
                
                if items_lista:
                    cardapio_final[nome_categoria] = {
                        "emoji": dados_cat['emoji'],
                        "schedule": {
                            "start": dados_cat['start'],
                            "end": dados_cat['end']
                        },
                        "items": items_lista
                    }
                    total_items_count += len(items_lista)

            print(f"📊 Total extraído: {total_items_count} itens.")
            
            with open('menu.json', 'w', encoding='utf-8') as f:
                json.dump(cardapio_final, f, ensure_ascii=False, indent=4)
            print("✨ Sucesso.")

        except Exception as e:
            print(f"❌ Erro fatal: {e}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
