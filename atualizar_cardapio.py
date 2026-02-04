from playwright.sync_api import sync_playwright
import json
import re
import sys
import time

URL_SITE = "https://cafe-ipiranga.ola.click/products"

# ==============================================================================
# 🛠️ CONFIGURAÇÃO DOS ADICIONAIS (Extraídos do HTML do Sistema)
# ==============================================================================

# 1. Adicionais de Cafés e Bebidas Quentes
# Fonte: Categoria "+ ADICIONAIS" do HTML
ADICIONAIS_CAFE = [
    {"name": "Leite de Castanha", "price": "R$ 4,00"},
    {"name": "Aveia e Zero Lactose", "price": "R$ 4,00"},
    {"name": "Nutella", "price": "R$ 4,00"},
    {"name": "Chantilly", "price": "R$ 4,00"}
]

# 2. Adicionais de Lanches e Hambúrgueres
# Fonte: Itens misturados na lista do HTML
ADICIONAIS_LANCHE = [
    {"name": "Bacon 3 fatias", "price": "R$ 5,00"},
    {"name": "Queijo Extra", "price": "R$ 2,00"},
    {"name": "Hambúrguer Extra", "price": "R$ 8,00"},
    {"name": "Fritas 100g", "price": "R$ 10,00"}, # Ótimo upsell encontrado no código
    {"name": "Maionese da Casa", "price": "R$ 3,00"}
]

# 3. Adicionais para Jantar/Pratos
ADICIONAIS_PRATO = [
    {"name": "Taça de Vinho", "price": "R$ 10,00"}, # Item encontrado no HTML
    {"name": "Fritas 100g", "price": "R$ 10,00"}
]

# 4. Ponto da Carne (Categoria "Escolha o ponto da carne" no HTML)
PONTO_CARNE = [
    {"name": "Mal Passado", "price": "Grátis"},
    {"name": "Ao Ponto", "price": "Grátis"},
    {"name": "Bem Passado", "price": "Grátis"}
]

# 5. Molhos (Categoria "Escolha seus molhos" no HTML)
MOLHOS = [
    {"name": "Maionese da Casa", "price": "Grátis"},
    {"name": "Ketchup", "price": "Grátis"},
    {"name": "Barbecue", "price": "Grátis"},
    {"name": "Mostarda", "price": "Grátis"}
]

# 6. Bordas de Pizza (Padrão de mercado, mantido pois não estava expandido no HTML)
BORDAS_PIZZA = [
    {"name": "Borda de Catupiry", "price": "R$ 12,00"},
    {"name": "Borda de Cheddar", "price": "R$ 12,00"},
    {"name": "Borda de Chocolate", "price": "R$ 15,00"},
    {"name": "Massa Integral", "price": "R$ 5,00"}
]

# 7. Drinks (Padrão)
ADICIONAIS_DRINK = [
    {"name": "Gelo Extra", "price": "Grátis"},
    {"name": "Adoçante", "price": "Grátis"},
    {"name": "Sem Açúcar", "price": "Grátis"}
]

# ==============================================================================

def processar_preco(texto):
    if not texto: return "A consultar"
    limpo = texto.replace('R$', '').replace('Adicionais', '').strip()
    return f"R$ {limpo}"

def extrair_imagem(style):
    if not style: return "https://placehold.co/400x300?text=Sem+Imagem"
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
    if match:
        return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def extrair_horario(titulo_categoria):
    match = re.search(r'(\d{2}:\d{2})\s*[-àa]\s*(\d{2}:\d{2})', titulo_categoria)
    if match:
        return match.group(1), match.group(2)
    return "00:00", "23:59"

def obter_adicionais_por_categoria(nome_categoria):
    """Define quais adicionais vão para qual categoria baseado no nome"""
    cat = nome_categoria.upper()
    
    adicionais = []

    # --- Lógica de Distribuição ---
    
    # Bebidas Quentes e Frias
    if any(x in cat for x in ["CAFÉ", "CAPPUCCINO", "CHOCOLATE", "FRAPÊ", "SHAKE", "GELADO"]):
        adicionais.extend(ADICIONAIS_CAFE)

    # Carnes e Hambúrgueres (Adiciona Ponto + Molhos + Extras de Lanche)
    if any(x in cat for x in ["STEAK", "BURGUER", "MIGNON", "CARNE"]):
        if "BURGUER" in cat:
            adicionais.extend(ADICIONAIS_LANCHE) # Bacon, Queijo, etc
        adicionais.extend(PONTO_CARNE)
        adicionais.extend(MOLHOS)

    # Sanduíches e Lanches Diversos
    elif any(x in cat for x in ["LANCHE", "SANDUÍCHE", "BAURU", "MISTO", "CROQUE"]):
        adicionais.extend(ADICIONAIS_LANCHE)
        adicionais.extend(MOLHOS)

    # Pratos Principais (Jantar)
    elif any(x in cat for x in ["PRATO", "RISOTO", "ESPAGUETE", "COSTELA", "POLPETONE"]):
        adicionais.extend(ADICIONAIS_PRATO) # Vinho e Fritas
        if "COSTELA" in cat or "STEAK" in cat:
            adicionais.extend(PONTO_CARNE)

    # Porções
    elif any(x in cat for x in ["PORÇ", "FRITAS", "BOLINHO", "TIRA"]):
        adicionais.extend(MOLHOS)
        # Adiciona opção de Queijo extra nas porções também
        adicionais.append({"name": "Queijo Extra", "price": "R$ 2,00"})

    # Pizzas
    elif "PIZZA" in cat:
        adicionais.extend(BORDAS_PIZZA)

    # Drinks
    elif any(x in cat for x in ["DRINK", "CAIPIRINHA", "SODA", "SUCO", "VINHO"]):
        adicionais.extend(ADICIONAIS_DRINK)

    return adicionais

def run():
    print("🔥 Iniciando Atualização (Modo Final + Adicionais Extraídos)...")
    
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
                print("⚠️ Demorou para carregar, mas seguindo...")

            banco_dados_mestre = {}
            previous_height = 0
            no_change_count = 0
            
            print("🚜 Rolando página para capturar tudo...")
            
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
                        
                        nome_limpo = re.sub(r'\d{2}:\d{2}.*', '', nome_raw).strip()
                        nome_limpo = nome_limpo.replace('-', '').strip()
                        
                        banco_dados_mestre[nome_raw] = {
                            "clean_name": nome_limpo,
                            "emoji": cat['emoji'],
                            "start": inicio,
                            "end": fim,
                            "items_dict": {}
                        }
                    
                    for item in cat['items']:
                        nome_item = item['name']
                        if nome_item not in banco_dados_mestre[nome_raw]["items_dict"]:
                            banco_dados_mestre[nome_raw]["items_dict"][nome_item] = item

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

            print("📦 Inserindo adicionais personalizados e salvando...")
            cardapio_final = {}
            total_items_count = 0
            
            for key_cat, dados_cat in banco_dados_mestre.items():
                nome_categoria = dados_cat["clean_name"]
                adicionais_cat = obter_adicionais_por_categoria(nome_categoria)
                
                items_lista = []
                for nome_item, item_raw in dados_cat["items_dict"].items():
                    items_lista.append({
                        "name": item_raw['name'],
                        "description": item_raw['description'],
                        "price": processar_preco(item_raw['price']),
                        "image": extrair_imagem(item_raw['imageStyle']),
                        "addons": adicionais_cat
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
