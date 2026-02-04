from playwright.sync_api import sync_playwright
import json
import re
import sys
import time

URL_SITE = "https://cafe-ipiranga.ola.click/products"

def processar_preco(texto):
    if not texto: return "A consultar"
    # Remove R$, espaços e quebras de linha
    limpo = texto.replace('R$', '').strip()
    return f"R$ {limpo}"

def extrair_imagem(style):
    if not style: return "https://placehold.co/400x300?text=Sem+Imagem"
    # Tenta extrair URL de background-image: url("...")
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
    if match:
        return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def run():
    print("🚀 Iniciando Browser Automation (Playwright)...")
    
    with sync_playwright() as p:
        # Lança um navegador Chromium (headless = invisível)
        browser = p.chromium.launch(headless=True)
        
        # Cria um contexto imitando um celular Android para garantir versão leve do site
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            viewport={'width': 412, 'height': 915}
        )
        
        page = context.new_page()
        
        try:
            print(f"🔄 Navegando para: {URL_SITE}")
            page.goto(URL_SITE, timeout=60000, wait_until="networkidle")
            
            # Espera explícita para garantir que o JavaScript montou os cards
            # Tenta esperar pelo seletor de produto ou categoria
            print("⏳ Aguardando renderização dos produtos...")
            try:
                page.wait_for_selector('.product-card', timeout=15000)
            except:
                print("⚠️ Seletor .product-card não apareceu rápido. Aguardando mais um pouco...")
                time.sleep(5)

            # Rola a página para baixo para carregar 'infinite scroll' se houver
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            # Extração dos dados direto do DOM (o que o usuário vê)
            print("🔍 Extraindo dados da página...")
            
            # Avalia script na página para retornar o JSON estruturado
            # Isso é mais rápido que fazer loops no Python
            cardapio_data = page.evaluate("""() => {
                const cardapio = {};
                
                // Encontra blocos de categorias
                const categories = document.querySelectorAll('.infinite-products');
                
                if (categories.length === 0) {
                    // Fallback: Tenta pegar todos os cards se não achar estrutura de categoria
                    const allCards = document.querySelectorAll('.product-card');
                    if (allCards.length > 0) {
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
                    return null;
                }

                categories.forEach(catBlock => {
                    const titleEl = catBlock.querySelector('.category-view-handler h2');
                    if (!titleEl) return;
                    
                    let catName = titleEl.innerText.trim();
                    if (catName.includes('Procurar Resultados')) return;

                    // Extrai Emoji
                    let emoji = "🍽️";
                    const emojiMatch = catName.match(/^([^\w\s]+)?\s*(.*)/);
                    if (emojiMatch) {
                        if(emojiMatch[1]) emoji = emojiMatch[1];
                        catName = emojiMatch[2];
                    }

                    const items = [];
                    const products = catBlock.querySelectorAll('.product-card');
                    
                    products.forEach(card => {
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

                    if (items.length > 0) {
                        cardapio[catName] = {
                            emoji: emoji,
                            items: items
                        };
                    }
                });
                return cardapio;
            }""")

            if not cardapio_data:
                print("❌ Nenhum dado encontrado na página renderizada.")
                # Debug: Tira um print da tela para ver o que aconteceu (opcional, mas útil localmente)
                # page.screenshot(path="debug_fail.png")
                # print("📸 Screenshot de erro salvo.")
                sys.exit(1)

            # Processamento final no Python (limpeza de strings)
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
            
            # Salva o JSON
            with open('menu.json', 'w', encoding='utf-8') as f:
                json.dump(cardapio_final, f, ensure_ascii=False, indent=4)
            print("✨ Arquivo 'menu.json' salvo.")

        except Exception as e:
            print(f"❌ Erro durante a automação: {e}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
