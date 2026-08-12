from playwright.sync_api import sync_playwright
import json
import re
import sys
import time

URL_SITE = "https://cafe-ipiranga.ola.click/products"

# ==============================================================================
# 🛠️ CONFIGURAÇÃO ESTRUTURADA DOS ADICIONAIS
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

SEM_IMAGEM = "https://placehold.co/400x300?text=Sem+Imagem"

def url_valida(url):
    """Ignora src vazio, base64 (placeholder de lazy-load) e pixels transparentes."""
    if not url: return False
    return url.startswith("http")

def extrair_imagem(src, style=""):
    """
    O site usa <img src="..."> nos cards.
    O background-image (layout antigo, Vuetify) fica como fallback.
    """
    if url_valida(src): return src

    if style:
        match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
        if match and url_valida(match.group(1)): return match.group(1)

    return SEM_IMAGEM

def extrair_horario(titulo_categoria):
    match = re.search(r'(\d{2}:\d{2})\s*[-àa]\s*(\d{2}:\d{2})', titulo_categoria)
    if match: return match.group(1), match.group(2)
    return "00:00", "23:59"

def obter_adicionais(nome_categoria, nome_item):
    """
    Define os adicionais baseados na Categoria E no Nome do Item.
    Isso evita colocar 'Ponto da Carne' num Espaguete só porque está na categoria Pratos.
    """
    cat = nome_categoria.upper()
    item = nome_item.upper()
    grupos = []

    # 1. PIZZAS
    if "PIZZA" in cat:
        grupos.append(GRP_BORDA)
        return grupos

    # 2. CARNES E HAMBÚRGUERES (Detecta por nome do item ou categoria específica)
    # Palavras-chave que indicam carne que precisa de ponto
    tem_carne_ponto = any(x in item for x in ["BURGUER", "STEAK", "MIGNON", "COSTELA", "PICANHA", "BIFE", "CHORIZO", "ANCHO"])
    
    # Se for hambúrguer ou carne de corte, adiciona PONTO DA CARNE
    if tem_carne_ponto:
        grupos.append(GRP_PONTO_CARNE)
        
        # Se for especificamente Burguer ou estiver numa categoria de lanche/burger, adiciona extras
        if "BURGUER" in item or "LANCHE" in cat or "SANDUÍCHE" in cat or "BURGUER" in cat:
             grupos.append(GRP_EXTRAS_LANCHE)
             grupos.append(GRP_MOLHOS)
        
        return grupos

    # 3. CAFÉS E BEBIDAS QUENTES
    # Detecta "CAFÉ" na categoria (ex: CAFÉS, CAFÉS GELADOS) ou no item
    eh_cafe_cat = any(x in cat for x in ["CAFÉ", "CAPPUCCINO", "CHOCOLATE", "FRAPÊ", "ESPECIAIS"])
    if eh_cafe_cat:
        grupos.append(GRP_EXTRAS_CAFE)
        return grupos

    # 4. LANCHES GERAIS (Sem ponto da carne - ex: Misto Quente)
    # Só entra aqui se NÃO caiu na regra de carne acima
    if "LANCHE" in cat or "SANDUÍCHE" in cat or "BAURU" in cat:
        grupos.append(GRP_EXTRAS_LANCHE)
        grupos.append(GRP_MOLHOS)
        return grupos

    return grupos

def run():
    print("🔥 Iniciando Atualização (Modo Inteligente)...")
    
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

                            // Layout atual: <img src="..."> dentro do card.
                            const imgEl = p.querySelector('.product-card__image-container img, img.product-image, img');
                            const imgSrc = imgEl?.currentSrc || imgEl?.getAttribute('src') || imgEl?.getAttribute('data-src') || '';

                            // Layout antigo (Vuetify): background-image num div.
                            const imgStyle = p.querySelector('.v-image__image')?.getAttribute('style');

                            if (nome) {
                                items.push({
                                    name: nome,
                                    description: desc || '',
                                    price: price || 'A consultar',
                                    imageSrc: imgSrc,
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
                        # Limpeza profunda do nome da categoria
                        nome_limpo = re.sub(r'\d{2}:\d{2}.*', '', nome_raw).strip().replace('-', '').strip()
                        
                        banco_dados_mestre[nome_raw] = {
                            "clean_name": nome_limpo,
                            "emoji": cat['emoji'],
                            "start": inicio,
                            "end": fim,
                            "items_dict": {}
                        }
                    
                    for item in cat['items']:
                        itens = banco_dados_mestre[nome_raw]["items_dict"]
                        existente = itens.get(item['name'])

                        if existente is None:
                            itens[item['name']] = item
                        elif not url_valida(existente.get('imageSrc')) and url_valida(item.get('imageSrc')):
                            # Item foi capturado antes do lazy-load da imagem: completa agora.
                            existente['imageSrc'] = item['imageSrc']

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
                
                items_lista = []
                for nome_item, item_raw in dados_cat["items_dict"].items():
                    
                    # AGORA CALCULAMOS ADICIONAIS POR ITEM, NÃO SÓ POR CATEGORIA
                    grupos_adicionais = obter_adicionais(nome_categoria, nome_item)

                    items_lista.append({
                        "name": item_raw['name'],
                        "description": item_raw['description'],
                        "price": processar_preco(item_raw['price']),
                        "image": extrair_imagem(item_raw.get('imageSrc'), item_raw.get('imageStyle')),
                        "addons": grupos_adicionais
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

            sem_foto = sum(
                1 for c in cardapio_final.values()
                for i in c['items'] if i['image'] == SEM_IMAGEM
            )
            print(f"📊 Total extraído: {total_items_count} itens ({total_items_count - sem_foto} com foto, {sem_foto} sem).")
            if total_items_count and sem_foto == total_items_count:
                print("❌ Nenhum item veio com foto — o seletor de imagem provavelmente quebrou.")
                sys.exit(1)

            with open('menu.json', 'w', encoding='utf-8') as f:
                json.dump(cardapio_final, f, ensure_ascii=False, indent=4)
            print("✨ Sucesso. Menu atualizado!")

        except Exception as e:
            print(f"❌ Erro fatal: {e}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
