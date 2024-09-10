import telebot
import requests
import logging
from datetime import datetime
import time
from threading import Thread

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Configuração do bot e API
API_TOKEN = '6742238431:AAFSamQ_CTu62i7CtpuvqO3PBYu_Sxr0Bp4'
GRAPHQL_URL = 'https://api.melhorrastreio.com.br/graphql'
API_KEY = 'YOUR_API_KEY'
ADMIN_ID = 1856875629  # ID do administrador para estatísticas

# Cria uma instância do bot
bot = telebot.TeleBot(API_TOKEN)

# Armazena informações sobre as encomendas, estados e mensagens enviadas por usuário
encomendas = {}
usuarios_online = set()
mensagens_enviadas = {}  # Para armazenar a última mensagem enviada por usuário

def consultar_rastreio(tracking_code, transportadora):
    headers = {
        'Content-Type': 'application/json',
        'Host': 'api.melhorrastreio.com.br',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
        'Accept': '*/*',
        'Origin': 'https://app.melhorrastreio.com.br',
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    query = {
        "query": """
        mutation searchParcel($tracker: TrackerSearchInput!) {
            result: searchParcel(tracker: $tracker) {
                id
                createdAt
                updatedAt
                lastStatus
                lastSyncTracker
                nextSyncTracker
                pudos {
                    type
                    trackingCode
                }
                trackers {
                    type
                    shippingService
                    trackingCode
                }
                trackingEvents {
                    trackerType
                    trackingCode
                    createdAt
                    translatedEventId
                    description
                    title
                    to
                    from
                    location {
                        zipcode
                        address
                        locality
                        number
                        complement
                        city
                        state
                        country
                    }
                    additionalInfo
                }
                pudoEvents {
                    pudoType
                    trackingCode
                    createdAt
                    translatedEventId
                    description
                    title
                    from
                    to
                    location {
                        zipcode
                        address
                        locality
                        number
                        complement
                        city
                        state
                        country
                    }
                    additionalInfo
                }
            }
        }
        """,
        "variables": {
            "tracker": {
                "trackingCode": tracking_code,
                "type": transportadora
            }
        }
    }

    try:
        response = requests.post(GRAPHQL_URL, json=query, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição à API: {e}")
        return None

def formatar_informacoes(result, incluir_todos_eventos=True):
    last_status = result.get('lastStatus', 'Não disponível')
    tracking_events = result.get('trackingEvents', [])

    if incluir_todos_eventos:
        events_message = "\n\n".join(
            f"📅 {datetime.fromisoformat(event['createdAt'].replace('Z', '')).strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"🔹 {event['title']}\n"
            f"📍 {event['location']['city']}/{event['location']['state']}\n"
            f"📝 {event['description'] or 'Nenhuma descrição'}\n"
            f"🗒️ {event['additionalInfo'] or 'Sem informações adicionais'}"
            f"👺 By: @no_dts\n"
            for event in tracking_events
        )
    else:
        if tracking_events:
            last_event = tracking_events[-1]
            events_message = (f"📅 {datetime.fromisoformat(last_event['createdAt'].replace('Z', '')).strftime('%d/%m/%Y %H:%M:%S')}\n"
                              f"🔹 {last_event['title']}\n"
                              f"📍 {last_event['location']['city']}/{last_event['location']['state']}\n"
                              f"📝 {last_event['description'] or 'Nenhuma descrição'}\n"
                              f"🗒️ {last_event['additionalInfo'] or 'Sem informações adicionais'}")
           
                        
        else:
            events_message = "Nenhum evento de rastreamento disponível."

    return f"📦 Status mais recente: {last_status}\n\n{events_message}"

def enviar_nova_mensagem(chat_id, nova_mensagem):
    """
    Função para enviar uma nova mensagem após apagar a última mensagem enviada pelo bot.
    """
    # Apaga a última mensagem enviada para o usuário, se existir
    if chat_id in mensagens_enviadas:
        try:
            bot.delete_message(chat_id, mensagens_enviadas[chat_id].message_id)
        except Exception as e:
            logger.error(f"Erro ao apagar a mensagem anterior: {e}")

    # Envia a nova mensagem e armazena o ID da mensagem
    mensagem = bot.send_message(chat_id, nova_mensagem)
    mensagens_enviadas[chat_id] = mensagem

@bot.message_handler(commands=['start'])
def start_command(message):
    usuarios_online.add(message.from_user.id)
    enviar_nova_mensagem(
        message.chat.id,
        "👋 Olá! Eu sou o RastreioBot, criado para rastrear informações sobre suas encomendas.\n\n"
        "👺 Dev: @no_dts\n"
        " \n"
        "🚚 Transportadoras disponíveis:\n"
        " 📌 Express, BUSLOG, 1001 Comet CATARINENSE, Correios, jadlog, LATAM CARGO, Loggi, J&T\n"
        " \n"
        "💬 Comandos disponíveis:\n"
        "/rastrear AB012345678BR correios - Rastreie sua encomenda\n"
        "/status AB012345678BR - Veja a última atualização sobre a encomenda\n"
        "/remover_encomenda AB012345678BR - Remova uma encomenda do rastreamento\n"
        "/add_encomenda AB012345678BR correios - Adicione uma nova encomenda ao rastreamento\n\n"
        " \n"
        "🔐 Termos de Uso:\n"
        "Este bot coleta dados de rastreamento e envia notificações para manter você informado sobre suas encomendas.\n"
        "Os dados coletados são utilizados exclusivamente para fornecer informações de rastreamento e não serão compartilhados com terceiros.\n"
        "Ao usar este bot, você concorda com esses termos."
    )

@bot.message_handler(commands=['rastrear'])
def rastrear_command(message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            enviar_nova_mensagem(message.chat.id, "⚠️ Por favor, forneça um código de rastreamento e a transportadora.")
            return

        tracking_code = parts[1]
        transportadora = parts[2]
        response = consultar_rastreio(tracking_code, transportadora)

        if not response or 'data' not in response or 'result' not in response['data']:
            enviar_nova_mensagem(message.chat.id, "⚠️ Não foi possível encontrar informações para o código fornecido.")
            return

        result = response['data']['result']
        formatted_info = formatar_informacoes(result)
        
        # Armazena a encomenda para o usuário
        if message.from_user.id not in encomendas:
            encomendas[message.from_user.id] = {}
        encomendas[message.from_user.id][tracking_code] = {'transportadora': transportadora, 'updatedAt': result['updatedAt']}
        
        enviar_nova_mensagem(message.chat.id, formatted_info)

    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        enviar_nova_mensagem(message.chat.id, "⚠️ Ocorreu um erro inesperado. Por favor, tente novamente.")

@bot.message_handler(commands=['status'])
def status_command(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            enviar_nova_mensagem(message.chat.id, "⚠️ Por favor, forneça um código de rastreamento válido.")
            return

        tracking_code = parts[1]
        user_encomendas = encomendas.get(message.from_user.id, {})
        if tracking_code not in user_encomendas:
            enviar_nova_mensagem(message.chat.id, "⚠️ Este código de rastreamento não está cadastrado.")
            return

        transportadora = user_encomendas[tracking_code]['transportadora']
        response = consultar_rastreio(tracking_code, transportadora)
        if not response or 'data' not in response or 'result' not in response['data']:
            enviar_nova_mensagem(message.chat.id, "⚠️ Não foi possível encontrar informações para o código fornecido.")
            return

        result = response['data']['result']
        formatted_info = formatar_informacoes(result, incluir_todos_eventos=False)
        enviar_nova_mensagem(message.chat.id, formatted_info)

    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        enviar_nova_mensagem(message.chat.id, "⚠️ Ocorreu um erro inesperado. Por favor, tente novamente.")

@bot.message_handler(commands=['remover_encomenda'])
def remover_encomenda_command(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            enviar_nova_mensagem(message.chat.id, "⚠️ Por favor, forneça um código de rastreamento válido.")
            return

        tracking_code = parts[1]
        if tracking_code in encomendas.get(message.from_user.id, {}):
            del encomendas[message.from_user.id][tracking_code]
            enviar_nova_mensagem(message.chat.id, f"✅ Encomenda {tracking_code} removida com sucesso.")
        else:
            enviar_nova_mensagem(message.chat.id, "⚠️ Este código de rastreamento não está cadastrado.")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        enviar_nova_mensagem(message.chat.id, "⚠️ Ocorreu um erro inesperado. Por favor, tente novamente.")

@bot.message_handler(commands=['add_encomenda'])
def add_encomenda_command(message):
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 3:
            enviar_nova_mensagem(message.chat.id, "⚠️ Por favor, forneça um código de rastreamento e a transportadora.")
            return

        tracking_code = parts[1]
        transportadora = parts[2]

        if message.from_user.id not in encomendas:
            encomendas[message.from_user.id] = {}

        encomendas[message.from_user.id][tracking_code] = {'transportadora': transportadora, 'updatedAt': None}
        enviar_nova_mensagem(message.chat.id, f"✅ Encomenda {tracking_code} adicionada para rastreamento.")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        enviar_nova_mensagem(message.chat.id, "⚠️ Ocorreu um erro inesperado. Por favor, tente novamente.")

@bot.message_handler(commands=['adm'])
def adm_command(message):
    if message.from_user.id != ADMIN_ID:
        enviar_nova_mensagem(message.chat.id, "⚠️ Você não tem permissão para usar este comando.")
        return

    try:
        total_usuarios = len(usuarios_online)
        total_encomendas = sum(len(encomendas[user]) for user in encomendas)
        enviar_nova_mensagem(
            message.chat.id,
            f"📊 Estatísticas de Usabilidade:\n\n"
            f"👥 Usuários online: {total_usuarios}\n"
            f"📦 Encomendas sendo rastreadas: {total_encomendas}"
        )
    except Exception as e:
        logger.error(f"Erro ao enviar estatísticas: {e}")
        enviar_nova_mensagem(message.chat.id, "⚠️ Erro ao obter estatísticas.")

def verificar_atualizacoes():
    while True:
        for user_id, user_encomendas in encomendas.items():
            for tracking_code, info in user_encomendas.items():
                transportadora = info['transportadora']
                response = consultar_rastreio(tracking_code, transportadora)

                if response and 'data' in response and 'result' in response['data']:
                    result = response['data']['result']
                    updated_at = result.get('updatedAt')
                    
                    if updated_at and updated_at != info['updatedAt']:
                        formatted_info = formatar_informacoes(result, incluir_todos_eventos=False)
                        enviar_nova_mensagem(user_id, f"🔔 Atualização na sua encomenda {tracking_code}:\n\n{formatted_info}")
                        
                        # Atualiza a data da última atualização
                        encomendas[user_id][tracking_code]['updatedAt'] = updated_at

        time.sleep(60)  # Verifica a cada 60 segundos

def enviar_estatisticas():
    while True:
        total_usuarios = len(usuarios_online)
        total_encomendas = sum(len(encomendas[user]) for user in encomendas)

        try:
            enviar_nova_mensagem(
                ADMIN_ID,
                f"📊 Estatísticas de Usabilidade:\n\n"
                f"👥 Usuários online: {total_usuarios}\n"
                f"📦 Encomendas sendo rastreadas: {total_encomendas}"
            )
        except Exception as e:
            logger.error(f"Erro ao enviar estatísticas: {e}")

        time.sleep(3600)  # Envia a cada 1 hora

if __name__ == "__main__":
    # Inicia as threads para verificar atualizações e enviar estatísticas
    Thread(target=verificar_atualizacoes, daemon=True).start()
    Thread(target=enviar_estatisticas, daemon=True).start()

    # Inicia o bot
    bot.polling(none_stop=True)
