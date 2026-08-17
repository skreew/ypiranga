import json
import re
import sys
import time
import requests

# ==============================================================================
# ⚙️ ORIGEM DOS DADOS
# ==============================================================================
# Antes este script abria um navegador (Playwright) e rolava a página do
# cardápio até o fim. Isso quebrava de duas formas:
#
#   1. Quando o ola.click mudava o layout, o seletor da foto parava de achar
#      a imagem e todos os itens viravam "Sem Imagem".
#   2. Quando o site demorava a responder, a rolagem terminava cedo e o robô
#      gravava um cardápio pela metade por cima do bom. Isso aconteceu em 24
#      dos 165 commits deste arquivo (15%), incluindo 17 cardápios vazios.
#
# A API pública devolve o cardápio inteiro numa requisição só, sem rolagem e
# sem depender de classe de CSS.
COMPANY_ID = "5f2ce783-e279-49ff-ad44-2ba7b97d6bc0"
URL_API = f"https://api.olaclick.app/ms-products/public/companies/{COMPANY_ID}/categories"

# A API entrega a foto em 800px (PNG de até 1 MB). O cardápio usa a miniatura
# de 150px em webp (4 KB) e o próprio index.html troca para 800px quando o
# cliente abre o item — por isso derivamos a miniatura em vez de usar a URL
# crua, que deixaria a página ~18x mais pesada no celular.
BASE_IMAGEM = "https://assets.olaclick.app/companies/products/images/150/"
SEM_IMAGEM = "https://placehold.co/400x300?text=Sem+Imagem"

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

def processar_preco(variantes):
    """A API devolve o preço como número (9.5). O cardápio espera 'R$ 9,50'."""
    if not variantes:
        return "R$ A consultar"

    ordenadas = sorted(variantes, key=lambda v: v.get('position', 0))
    try:
        valor = float(ordenadas[0].get('price') or 0)
    except (TypeError, ValueError):
        return "R$ A consultar"

    if valor <= 0:
        return "R$ A consultar"

    formatado = f"{valor:,.2f}"                        # 1,234.56
    formatado = formatado.replace(',', '§').replace('.', ',').replace('§', '.')
    return f"R$ {formatado}"                           # R$ 1.234,56

def extrair_imagem(produto):
    """Monta a URL da miniatura a partir do id da foto que a API informa."""
    imagens = sorted(produto.get('images') or [], key=lambda i: i.get('position', 0))
    if not imagens:
        return SEM_IMAGEM

    url = imagens[0].get('image_url') or ''
    match = re.search(r'/images/\d+/([0-9a-f-]{36})\.', url)
    if not match:
        return SEM_IMAGEM
    return f"{BASE_IMAGEM}{match.group(1)}.webp"

def limpar_descricao(texto):
    """
    A API devolve a descrição crua, com as quebras de linha e espaços duplos
    que foram digitados no painel. Lendo pelo navegador esses espaços já vinham
    colapsados — mantemos o mesmo resultado pra não mudar o visual do cardápio.
    """
    return re.sub(r'\s+', ' ', texto or '').strip()

def separar_emoji(nome_categoria):
    """As categorias vêm como '☕️ CAFÉS', '🍹SODA ITALIANA' ou 'LONG NECK'."""
    match = re.match(r'^([^\w\s]+)?\s*(.*)$', nome_categoria, re.UNICODE)
    emoji = "🍽️"
    nome = nome_categoria
    if match:
        if match.group(1): emoji = match.group(1)
        if match.group(2): nome = match.group(2)
    nome = re.sub(r'\d{2}:\d{2}.*', '', nome).strip().replace('-', '').strip()
    return emoji, nome

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

def buscar_cardapio():
    """Busca o cardápio na API, com algumas tentativas em caso de instabilidade."""
    ultimo_erro = None
    for tentativa in range(1, 4):
        try:
            print(f"🔄 Buscando cardápio (tentativa {tentativa}/3)...")
            resposta = requests.get(URL_API, timeout=30)
            if resposta.status_code == 200:
                return resposta.json().get('data', [])
            ultimo_erro = f"HTTP {resposta.status_code}"
            print(f"   ⚠️ Resposta inesperada: {ultimo_erro}")
        except Exception as e:
            ultimo_erro = str(e)
            print(f"   ⚠️ Falha de conexão: {e}")
        if tentativa < 3:
            time.sleep(tentativa * 3)
    raise RuntimeError(f"Não foi possível baixar o cardápio ({ultimo_erro})")

def run():
    print("🔥 Iniciando Atualização (API)...")

    try:
        categorias = buscar_cardapio()

        print("📦 Aplicando regras de adicionais...")
        cardapio_final = {}
        total_items_count = 0

        for cat in sorted(categorias, key=lambda c: c.get('position', 0)):
            if not cat.get('visible', True):
                continue

            produtos = [p for p in (cat.get('products') or []) if p.get('visible', True)]
            if not produtos:
                continue

            emoji, nome_categoria = separar_emoji(cat.get('name', ''))
            inicio, fim = extrair_horario(cat.get('name', ''))

            items_lista = []
            for produto in sorted(produtos, key=lambda p: p.get('position', 0)):
                nome_item = (produto.get('name') or '').strip()
                if not nome_item:
                    continue

                items_lista.append({
                    "name": nome_item,
                    "description": limpar_descricao(produto.get('description')),
                    "price": processar_preco(produto.get('product_variants')),
                    "image": extrair_imagem(produto),
                    "addons": obter_adicionais(nome_categoria, nome_item)
                })

            if items_lista:
                cardapio_final[nome_categoria] = {
                    "emoji": emoji,
                    "schedule": {"start": inicio, "end": fim},
                    "items": items_lista
                }
                total_items_count += len(items_lista)

        com_foto = sum(
            1 for c in cardapio_final.values()
            for i in c['items'] if i['image'] != SEM_IMAGEM
        )
        print(f"📊 Total extraído: {total_items_count} itens ({com_foto} com foto, "
              f"{total_items_count - com_foto} sem).")

        # ======================================================================
        # 🛡️ TRAVA ANTI-CARDÁPIO-INCOMPLETO
        # Um cardápio menor que o atual não pode ser commitado por cima do bom.
        # Antes desta trava, uma leitura parcial virava commit e o cardápio
        # publicado ficava vazio até a execução seguinte.
        # ======================================================================
        anterior = 0
        try:
            with open('menu.json', 'r', encoding='utf-8') as f:
                anterior = sum(len(c.get('items', [])) for c in json.load(f).values())
        except Exception:
            pass

        if total_items_count == 0:
            print("❌ ABORTADO: nenhum item retornado. O menu.json NÃO foi alterado.")
            sys.exit(1)

        if anterior and total_items_count < anterior * 0.8:
            print("")
            print("=" * 60)
            print(f"❌ ABORTADO: vieram apenas {total_items_count} itens, "
                  f"mas o cardápio atual tem {anterior}.")
            print("   O menu.json NÃO foi alterado.")
            print("=" * 60)
            sys.exit(1)

        with open('menu.json', 'w', encoding='utf-8') as f:
            json.dump(cardapio_final, f, ensure_ascii=False, indent=4)
        print("✨ Sucesso. Menu atualizado!")

    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        print("   O menu.json NÃO foi alterado.")
        sys.exit(1)

if __name__ == "__main__":
    run()
