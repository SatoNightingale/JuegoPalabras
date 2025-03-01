from random import choice, randint
from itertools import islice
import logging

from telegram import (
    Update,
    Bot,
    Chat,
    ChatMember, 
    Poll
)
from telegram.constants import ParseMode
from telegram.ext import(
    Application,
    ContextTypes,
    CommandHandler,
    PollHandler,
    PollAnswerHandler,
    ChatMemberHandler
)

## Código copiado y pegado del ejemplo
# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)



TOKEN = '7760476240:AAF8Yz-HVPmvLpPKBOxyCxay8HsQMQZgdBA'

players = [] # la lista de id's de jugadores
impostor = -1 # El id del jugador que será el impostor
jugadas = {} # la lista de palabras jugadas por cada jugador en la ronda actual
vivos = [] # la lista de id's de jugadores que no han sido eliminados en la ronda
rondas = [] # la lista de rondas, donde se guarda cada jugada de cada jugador
game_running = False # si el juego está corriendo o no

def main():
    bot = Application.builder().token(TOKEN).build()

    bot.add_handler(CommandHandler("help", mostrar_ayuda))
    bot.add_handler(CommandHandler("regme", registerplayer))
    bot.add_handler(CommandHandler("unregme", unregisterplayer))
    bot.add_handler(CommandHandler("start", start_game))
    bot.add_handler(CommandHandler("p", jugar_palabra))
    bot.add_handler(PollAnswerHandler(recibir_resultados_encuesta))
    # bot.add_handler(ChatMemberHandler())

async def mostrar_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def registerplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_running:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if not user_id in players:
            players.append(update.effective_user.id)
            await context.bot.send_message(chat_id, "Has sido registrado como jugador")
        else:
            await context.bot.send_message(chat_id, "¡Ya estás registrado!")

async def unregisterplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_running:
        user = update.effective_user
        chat_id = update.effective_chat.id

        if user.id in players:
            players.remove(user.id)
            await context.bot.send_message(chat_id, f"El jugador {user.full_name} se ha quitado del juego")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    adm = await context.bot.get_chat_member(chat_id, user.id)
    
    if adm.status == ChatMember.ADMINISTRATOR:
        game_running = True
        await inicializar_juego(context.bot, update.effective_chat)
    else:
        await context.bot.send_message(chat_id, "Solo un administrador puede iniciar el juego")


def elegir_palabra() -> str:
    data = open("./words.txt", 'r')
    cant = int(data.readline())
    nlinea = randint(0, cant-1)

    palabra = islice(data, nlinea, nlinea + 1).__next__()[:-1]
    
    return palabra

async def inicializar_juego(bot: Bot, chat: Chat):
    impostor = choice(players)
    vivos.copy(players)

    await susurrar_palabras(bot, elegir_palabra())

    await bot.send_message(chat, "Ahora cada uno puede decir su palabra")

    jugadas.clear()



async def susurrar_palabras(bot: Bot, palabra):
    for player in players:
        if not player == impostor:
            await bot.send_message(player, "La palabra es " + palabra)
        else:
            await bot.send_message(player, "Te jodiste asere, eres el impostor")

async def jugar_palabra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.delete()
    user = update.effective_user
    chat_id = update.effective_chat.id

    if len(context.args) > 1:
        await context.bot.send_message(chat_id, user.full_name + ", solo puedes jugar una palabra")
    elif not user.id in jugadas: # si el usuario que envió el mensaje no ha jugado todavía
        palabra = context.args[0]
        jugadas[user.id] = palabra
        await context.bot.send_message(chat_id, f"{user.full_name} dijo: '{palabra}'")

        await revisar_fin_ronda(context, update.effective_chat)
    else:
        await context.bot.send_message(chat_id, f"{user.full_name}, ya jugaste una palabra en esta ronda")

async def revisar_fin_ronda(context: ContextTypes.DEFAULT_TYPE, chat: Chat):
    if len(vivos) == len(jugadas.keys()):
        await enviar_votacion(context, chat)
        jugadas.clear()

async def enviar_votacion(context: ContextTypes.DEFAULT_TYPE, chat: Chat):
    miembros = [await chat.get_member(id) for id in vivos]
    
    votacion = await context.bot.send_poll(
        chat.id,
        "¿Quién crees que es el impostor?",
        miembros,
        type=Poll.REGULAR,
        open_period=60
    )

    info_votacion = {
        votacion.poll.id: {
            'message_id': votacion.id,
            'chat_id': chat.id,
            'candidatos': miembros
        }
    }

    context.bot_data.update(info_votacion)

async def recibir_resultados_encuesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resultados = update.poll_answer
    votos = {id: 0 for id in vivos}

    # votacion = context.bot_data[resultados.poll_id]
    # try:

    lista_votos = resultados.option_ids

    for voto in lista_votos:
        votos[voto] += 1
    
    # Sacar el jugador más votado
    mas_votado = 0, 0
    for player in votos:
        if votos[player] > mas_votado[1]:
            mas_votado = player, votos[player]
    
    # Si acumula al menos la mitad de los votos, expulsarlo
    if mas_votado[1] > len(votos) / 2:
        vivos.remove(mas_votado[0])
        chat = update.effective_chat
        await context.bot.send_message(
            chat, f"El jugador {await chat.get_member(mas_votado[0]).mention_html()} ha sido expulsado del juego",
            parse_mode=ParseMode.HTML
        )
    