from playwright.sync_api import sync_playwright
import json
import re
import sys
import time

URL_SITE = "https://cafe-ipiranga.ola.click/products"

def processar_preco(texto):
    if not texto: return "A consultar"
    # Remove R$, espaços e quebras de linha e normaliza
    limpo = texto.replace('R$', '').replace('Adicionais', '').strip()
    return f"R$ {limpo}"

def extrair_imagem(style):
    if not style: return "https://placehold.co/400x300?text=Sem+Imagem"
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
    if match:
        return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def run():
    print("🚀 Iniciando Browser Automation (Playwright)...")
    
    with sync_playwright() as p:
        # Modo headless=True (invisível) para rodar no GitHub Actions
        browser = p.chromium.launch(headless=True)
        
        # Emula um celular Android alto (viewport height maior ajuda a carregar mais coisas)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            viewport={'width': 412, 'height': 915}
        )
        
        page = context.new_page()
        
        try:
            print(f"🔄 Navegando para: {URL_SITE}")
            page.goto(URL_SITE, timeout=90000, wait_until="networkidle")
            
            print("⏳ Iniciando rolagem inteligente para carregar TUDO...")
            
            # --- LÓGICA DE ROLAGEM INFINITA ---
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                # Rola para o fundo da página
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Espera 4 segundos para o site carregar os novos produtos
                print("   ... carregando mais itens ...")
                time.sleep(4)
                
                # Calcula a nova altura da página
                new_height = page.evaluate("document.body.scrollHeight")
                
                # Se a altura não mudou, significa que chegamos ao fim real
                if new_height == last_height:
                    print("✅ Fim da página alcançado.")
                    break
                
                last_height = new_height
            # ----------------------------------

            # Extração dos dados
            print("🔍 Extraindo dados completos da página...")
            
            cardapio_data = page.evaluate("""() => {
                const cardapio = {};
                
                // Tenta pegar pela estrutura de categorias
                const categories = document.querySelectorAll('.infinite-products');
                
                // Se não achar categorias, pega tudo misturado
                if (categories.length === 0) {
                    const allCards = document.querySelectorAll('.product-card');
                    const items = [];
                    allCards.forEach(card => {
                        const titleEl = card.querySelector('.product-card__title');
                        const descEl = card.querySelector('.product-card__description');
                        const priceEl = card.querySelector('.product__price');
                        const imgEl = card.querySelector('.v-image__image');
                        
                        items.push({
                            name: titleEl ? titleEl.innerText.trim() : 'Sem Nome',
                            description: descEl ? descEl.innerText.trim() : '',
                            price: priceEl ? priceEl.innerText.trim() : 'A consultar',
                            imageStyle: imgEl ? imgEl.getAttribute('style') : ''
                        });
                    });
                    return { "Geral": { "emoji": "📋", "items": items } };
                }

                // Processa categoria por categoria
                categories.forEach(catBlock => {
                    const titleEl = catBlock.querySelector('.category-view-handler h2');
                    if (!titleEl) return;
                    
                    let catName = titleEl.innerText.trim();
                    if (catName.includes('Procurar Resultados')) return;

                    // Extrai Emoji do título (ex: "🍕 Pizzas")
                    let emoji = "🍽️";
                    const emojiMatch = catName.match(/^([^\w\s]+)?\s*(.*)/);
                    if (emojiMatch) {
                        if(emojiMatch[1]) emoji = emojiMatch[1];
                        catName = emojiMatch[2] ? emojiMatch[2] : catName;
                    }

                    const items = [];
                    // Pega TODOS os produtos dentro desta categoria
                    const products = catBlock.querySelectorAll('.product-card');
                    
                    products.forEach(card => {
                        const titleEl = card.querySelector('.product-card__title');
                        const descEl = card.querySelector('.product-card__description');
                        const priceEl = card.querySelector('.product__price');
                        const imgEl = card.querySelector('.v-image__image');

                        // Filtra itens vazios ou invisíveis
                        if (!titleEl) return;

                        items.push({
                            name: titleEl.innerText.trim(),
                            description: descEl ? descEl.innerText.trim() : '',
                            price: priceEl ? priceEl.innerText.trim() : 'A consultar',
                            imageStyle: imgEl ? imgEl.getAttribute('style') : ''
                        });
                    });

                    if (items.length > 0) {
                        // Se a categoria já existe (ex: repetida na página), funde os itens
                        if (cardapio[catName]) {
                            cardapio[catName].items = cardapio[catName].items.concat(items);
                        } else {
                            cardapio[catName] = {
                                emoji: emoji,
                                items: items
                            };
                        }
                    }
                });
                return cardapio;
            }""")

            if not cardapio_data:
                print("❌ Erro: Nenhum dado encontrado mesmo após rolagem.")
                sys.exit(1)

            # Processamento final Python
            cardapio_final = {}
            total_items = 0

            for cat_nome, cat_dados in cardapio_data.items():
                items_limpos = []
                for item in cat_dados['items']:
                    items_limpos.append({
                        "name": item['name'],
                        "description": item['description'],
                        "price": processar_preco(item['price']),
                        "image": extrair_imagem(item['imageStyle']),
                        "addons": []
                    })
                
                cardapio_final[cat_nome] = {
                    "emoji": cat_dados['emoji'],
                    "schedule": {"start": "00:00", "end": "23:59"},
                    "items": items_limpos
                }
                total_items += len(items_limpos)

            print(f"📊 Sucesso! {total_items} itens extraídos em {len(cardapio_final)} categorias.")
            
            with open('menu.json', 'w', encoding='utf-8') as f:
                json.dump(cardapio_final, f, ensure_ascii=False, indent=4)
            print("✨ menu.json atualizado.")

        except Exception as e:
            print(f"❌ Erro fatal: {e}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
