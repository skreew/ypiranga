from playwright.sync_api import sync_playwright
import json
import re
import sys
import time

URL_SITE = "https://cafe-ipiranga.ola.click/products"

def processar_preco(texto):
    if not texto: return "A consultar"
    # Remove R$, 'Adicionais', espaços extras e quebras
    limpo = texto.replace('R$', '').replace('Adicionais', '').strip()
    return f"R$ {limpo}"

def extrair_imagem(style):
    if not style: return "https://placehold.co/400x300?text=Sem+Imagem"
    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
    if match:
        return match.group(1)
    return "https://placehold.co/400x300?text=Sem+Imagem"

def run():
    print("🔥 Iniciando Modo 'Colheitadeira Lenta' (Playwright)...")
    
    with sync_playwright() as p:
        # headless=True para rodar no GitHub, False para ver no seu PC
        browser = p.chromium.launch(headless=True)
        
        # Viewport alto ajuda a carregar mais itens por vez
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            viewport={'width': 390, 'height': 844},
            device_scale_factor=2
        )
        
        page = context.new_page()
        
        try:
            print(f"🔄 Acessando: {URL_SITE}")
            page.goto(URL_SITE, timeout=90000, wait_until="domcontentloaded")
            
            # Espera o primeiro card aparecer
            try:
                page.wait_for_selector('.product-card', timeout=20000)
                print("✅ Site carregou inicial.")
            except:
                print("⚠️ Demorou para carregar, mas vamos tentar continuar.")

            # Dicionário Mestre para guardar tudo sem repetir
            # Chave = Nome do Produto, Valor = Dados Completos
            # Estrutura: { "NomeCategoria": { "emoji": "X", "items": { "NomeProd": {...} } } }
            banco_dados_mestre = {}

            print("🚜 Iniciando rolagem e coleta incremental...")
            
            previous_height = 0
            no_change_count = 0
            
            # Loop de Rolagem Lenta
            while True:
                # 1. Coleta o que está visível na tela AGORA
                dados_tela = page.evaluate("""() => {
                    const dados = [];
                    // Pega blocos de categoria visíveis
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

                        // Itens dentro dessa categoria
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

                # 2. Processa e guarda no Python (Mesclando com o que já temos)
                items_novos_nesta_rodada = 0
                for cat in dados_tela:
                    nome_cat = cat['category']
                    if nome_cat not in banco_dados_mestre:
                        banco_dados_mestre[nome_cat] = {
                            "emoji": cat['emoji'],
                            "items_dict": {} # Usamos dict para evitar duplicatas por nome
                        }
                    
                    for item in cat['items']:
                        nome_item = item['name']
                        # Só adiciona se não existe ou se a descrição atual for maior (melhor qualidade)
                        if nome_item not in banco_dados_mestre[nome_cat]["items_dict"]:
                            banco_dados_mestre[nome_cat]["items_dict"][nome_item] = item
                            items_novos_nesta_rodada += 1

                # 3. Rola a página um pouco para baixo (Scroll Suave)
                # Rola 600 pixels (tamanho de +- 3 produtos)
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(1.5) # Espera o site carregar o novo pedaço

                # 4. Verifica se chegou ao fim
                new_height = page.evaluate("window.scrollY + window.innerHeight")
                total_height = page.evaluate("document.body.scrollHeight")
                
                print(f"   ⬇️  Scroll: {int(new_height)} / {int(total_height)} | Coletados agora: {items_novos_nesta_rodada}")

                if new_height >= total_height:
                    # Tenta esperar mais um pouco pra ver se cresce
                    time.sleep(3)
                    new_total = page.evaluate("document.body.scrollHeight")
                    if new_total == total_height:
                        print("✅ Fim da página alcançado.")
                        break
                
                # Proteção contra loop infinito (máximo 100 rolagens)
                if previous_height == new_height:
                    no_change_count += 1
                    if no_change_count > 5: break
                else:
                    no_change_count = 0
                
                previous_height = new_height

            # --- MONTAGEM DO JSON FINAL ---
            print("📦 Processando e organizando dados finais...")
            cardapio_final = {}
            total_items_count = 0
            
            # Converte o dict de volta para lista limpa
            for cat_nome, cat_dados in banco_dados_mestre.items():
                lista_items = []
                # Ordena os itens alfabeticamente ou mantém ordem de inserção (Python 3.7+ mantém)
                for nome_item, item_raw in cat_dados["items_dict"].items():
                    lista_items.append({
                        "name": item_raw['name'],
                        "description": item_raw['description'],
                        "price": processar_preco(item_raw['price']),
                        "image": extrair_imagem(item_raw['imageStyle']),
                        "addons": []
                    })
                
                if lista_items:
                    cardapio_final[cat_nome] = {
                        "emoji": cat_dados['emoji'],
                        "schedule": {"start": "00:00", "end": "23:59"},
                        "items": lista_items
                    }
                    total_items_count += len(lista_items)

            print(f"📊 RELATÓRIO FINAL: {total_items_count} itens em {len(cardapio_final)} categorias.")
            
            if total_items_count < 10:
                print("❌ ALERTA: Poucos itens encontrados. Algo deu errado na rolagem.")
                # Não falha o script para salvar o que achou, mas avisa
            
            with open('menu.json', 'w', encoding='utf-8') as f:
                json.dump(cardapio_final, f, ensure_ascii=False, indent=4)
            print("✨ Arquivo menu.json salvo com sucesso.")

        except Exception as e:
            print(f"❌ Erro fatal: {e}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
