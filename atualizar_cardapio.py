from playwright.sync_api import sync_playwright
import json
import re
import sys
import time

URL_SITE = "https://cafe-ipiranga.ola.click/products"

def processar_preco(texto):
    if not texto: return "A consultar"
    # Limpa sujeira do texto (R$, Adicionais, espaços)
    limpo = texto.replace('R$', '').replace('Adicionais', '').strip()
    return f"R$ {limpo}"

def extrair_imagem(style):
    if not style: return "https://placehold.co/400x300?text=Sem+Imagem"
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
    if match:
        return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def extrair_horario(titulo_categoria):
    # Procura por padrões como "18:00-21:45" ou "18:00 as 23:00"
    match = re.search(r'(\d{2}:\d{2})\s*[-àa]\s*(\d{2}:\d{2})', titulo_categoria)
    if match:
        return match.group(1), match.group(2)
    return "00:00", "23:59"

def run():
    print("🔥 Iniciando Atualização (Modo Colheitadeira + Horários)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Emula um celular Android alto para carregar bastante coisa
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
                # Extrai dados visíveis
                dados_tela = page.evaluate("""() => {
                    const dados = [];
                    const cats = document.querySelectorAll('.infinite-products');
                    
                    cats.forEach(cat => {
                        const titleEl = cat.querySelector('.category-view-handler h2');
                        if (!titleEl) return;
                        
                        let catName = titleEl.innerText.trim();
                        if (catName.includes('Procurar Resultados')) return;
                        
                        // Extrai Emoji
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
                            
                            // Verifica se tem botão/texto de adicionais (apenas para registro)
                            const temAdicionais = p.innerText.includes('Adicionais');

                            if (nome) {
                                items.push({
                                    name: nome,
                                    description: desc || '',
                                    price: price || 'A consultar',
                                    imageStyle: imgStyle || '',
                                    hasAddons: temAdicionais
                                });
                            }
                        });

                        if (items.length > 0) {
                            dados.push({
                                category: catName, // Nome com horário ainda
                                emoji: emoji,
                                items: items
                            });
                        }
                    });
                    return dados;
                }""")

                # Processa no Python
                for cat in dados_tela:
                    nome_raw = cat['category']
                    
                    if nome_raw not in banco_dados_mestre:
                        # Extrai horário do nome da categoria (Ex: "PIZZA 18:00-21:45")
                        inicio, fim = extrair_horario(nome_raw)
                        
                        # Limpa o nome da categoria removendo o horário
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

                # Scroll e Verificação de Fim
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

            # Montagem Final
            print("📦 Salvando arquivo...")
            cardapio_final = {}
            total_items_count = 0
            
            for key_cat, dados_cat in banco_dados_mestre.items():
                nome_categoria = dados_cat["clean_name"]
                
                items_lista = []
                for nome_item, item_raw in dados_cat["items_dict"].items():
                    items_lista.append({
                        "name": item_raw['name'],
                        "description": item_raw['description'],
                        "price": processar_preco(item_raw['price']),
                        "image": extrair_imagem(item_raw['imageStyle']),
                        "addons": [] # Mantido vazio para compatibilidade
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
