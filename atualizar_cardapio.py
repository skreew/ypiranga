from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import sys

# URL do cardápio
URL_SITE = "https://cafe-ipiranga.ola.click/products"

def buscar_dados_html_bruto():
    print(f"🔄 Acessando site via HTML: {URL_SITE}")
    
    try:
        # Usa headers de navegador comum para evitar bloqueio 403
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Impersonate chrome110 é crucial para passar pelo Cloudflare/Shields
        response = requests.get(URL_SITE, impersonate="chrome110", headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro: O site retornou status {response.status_code}")
            return None

        content = response.text
        print(f"📡 HTML baixado ({len(content)} caracteres). Procurando dados...")

        # --- ESTRATÉGIA: Regex "Force Brute" ---
        # Como o JSON do Nuxt não é padrão (chaves sem aspas), vamos caçar os objetos diretamente.
        # Procuramos padrões como: name:"X", description:"Y", price:Z
        
        # Regex para capturar objetos de produtos. 
        # Procura por 'name:"..."' seguido de outros campos comuns
        # Esta regex é complexa para lidar com aspas escapadas e diferentes ordens
        regex_produto = r'name\s*:\s*"(.*?)".*?price\s*:\s*([\d\.]+)'
        
        # Encontra todas as correspondências no HTML inteiro (dentro do script Nuxt)
        matches = re.finditer(regex_produto, content, re.DOTALL)
        
        produtos_encontrados = []
        
        for match in matches:
            nome = match.group(1)
            preco_raw = match.group(2)
            
            # Pula itens de sistema ou irrelevantes
            if nome in ["Procurar Resultados", "Search Results"]: continue
            
            # Tenta achar a descrição perto desse match (lookaround)
            # Pegamos um pedaço do texto ao redor para buscar a descrição e imagem
            start_pos = match.start()
            end_pos = match.end() + 500 # Olha 500 chars pra frente
            contexto = content[start_pos:end_pos]
            
            # Busca descrição no contexto
            desc_match = re.search(r'description\s*:\s*"(.*?)"', contexto)
            descricao = desc_match.group(1) if desc_match else ""
            
            # Busca imagem no contexto
            img_match = re.search(r'image\s*:\s*"(.*?)"', contexto)
            imagem = img_match.group(1) if img_match else "https://placehold.co/400x300?text=Sem+Imagem"
            # Corrige URL da imagem se vier relativa ou codificada unicode (\u002F)
            imagem = imagem.encode().decode('unicode_escape')
            
            # Formata preço
            try:
                preco_num = float(preco_raw)
                preco_fmt = f"R$ {preco_num:.2f}".replace('.', ',')
            except:
                preco_fmt = "A consultar"

            # Adiciona à lista
            produtos_encontrados.append({
                "name": nome.encode().decode('unicode_escape'), # Corrige acentos unicode
                "description": descricao.encode().decode('unicode_escape'),
                "price": preco_fmt,
                "image": imagem,
                "addons": []
            })

        if not produtos_encontrados:
            print("⚠️ Nenhum produto encontrado via Regex.")
            # Debug: Mostra se achou o script do Nuxt pelo menos
            if "window.__NUXT__" in content:
                print("   ✅ Script 'window.__NUXT__' detectado, mas a regex falhou.")
                # Tenta imprimir um pedaço do script para ajuste
                start = content.find("window.__NUXT__")
                print(f"   Trecho do script: {content[start:start+200]}...")
            else:
                print("   ❌ Script 'window.__NUXT__' NÃO detectado.")
            return None

        print(f"✅ Encontrados {len(produtos_encontrados)} produtos brutos.")

        # --- Organização em Categorias ---
        # Como perdemos a estrutura de categoria com a regex bruta, vamos agrupar
        # Tentativa simples: Se o nome já existe, ignoramos (remove duplicatas)
        cardapio = {}
        nomes_processados = set()

        # Cria uma categoria única "Cardápio" ou tenta inferir keywords
        # Para ser mais elegante, vamos jogar tudo em "Todos os Itens" por enquanto,
        # pois recuperar a categoria exata exigiria um parser JS muito complexo.
        
        categoria_padrao = "Destaques e Lanches"
        cardapio[categoria_padrao] = {
            "emoji": "🍽️",
            "schedule": {"start": "00:00", "end": "23:59"},
            "items": []
        }

        for prod in produtos_encontrados:
            if prod['name'] in nomes_processados: continue
            nomes_processados.add(prod['name'])
            
            cardapio[categoria_padrao]["items"].append(prod)
        
        return cardapio

    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        return None

if __name__ == "__main__":
    dados = buscar_dados_html_bruto()
    
    if dados and len(dados) > 0:
        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print("\n✨ Sucesso! 'menu.json' atualizado.")
    else:
        # Não falha o workflow se não achar dados, para não ficar mandando email de erro,
        # mas avisa no log. Ou use sys.exit(1) se quiser erro.
        print("\n❌ Falha: Não foi possível atualizar o cardápio.")
        sys.exit(1)
