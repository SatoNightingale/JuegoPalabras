from random import choice, randint
from itertools import islice
import logging

from telegram import (
    Update,
    Bot,
    Chat,
    ChatMember, 
    Poll,
)
from telegram.constants import ParseMode
from telegram.ext import(
    Application,
    ContextTypes,
    filters,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
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

# Contiene la información de cada grupo, mapeada según el id de cada chat en el que está el bot
grupos = {}

players = [] # la lista de id's de jugadores
impostor = -1 # El id del jugador que será el impostor
jugadas = {} # la lista de palabras jugadas por cada jugador en la ronda actual
vivos = [] # la lista de id's de jugadores que no han sido eliminados en la ronda
rondas = [] # la lista de rondas, donde se guarda cada jugada de cada jugador
game_running = False # si el juego está corriendo o no

def main():
    bot = Application.builder().token(TOKEN).build()

    bot.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, nuevo_grupo))
    bot.add_handler(CommandHandler("help", mostrar_ayuda))
    bot.add_handler(CommandHandler("regme", registerplayer))
    bot.add_handler(CommandHandler("unregme", unregisterplayer))
    bot.add_handler(CommandHandler("start", start_game))
    bot.add_handler(CommandHandler("p", jugar_palabra))
    bot.add_handler(PollAnswerHandler(recibir_resultados_encuesta))
    # bot.add_handler(ChatMemberHandler())

    bot.run_polling(allowed_updates=Update.ALL_TYPES)

async def nuevo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.username == context.bot.username:
            # Si me acaban de añadir a este grupo, registrar su id
            grupos[update.effective_chat.id] = {
                'players': [],
                'impostor': -1,
                'vivos': [],
                'palabra': "",
                'jugadas': {},
                'rondas': [],
                'game_running': False
            }
            context.bot_data.update(grupos)
            break

async def mostrar_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message()

async def registerplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_running:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if not user_id in grupos[chat_id]['players']:
            grupos[chat_id]['players'].append(update.effective_user.id)
            await context.bot.send_message(chat_id, f"{update.effective_user.mention_html()} ha sido registrado para jugar El juego de las palabras", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("¡Ya estás registrado!")

async def unregisterplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not grupos[chat_id]['game_running']:
        user = update.effective_user

        if user.id in grupos[chat_id]['players']:
            grupos[chat_id]['players'].remove(user.id)
            await context.bot.send_message(chat_id, f"El jugador {user.mention_html()} se ha quitado del juego", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("No estás registrado en el juego. Para registrarte escribe /regme")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not grupos[chat_id]['game_running']:
        user = update.effective_user

        adm = await context.bot.get_chat_member(chat_id, user.id)
        
        if adm.status == ChatMember.ADMINISTRATOR:
            grupos[chat_id]['game_running'] = True
            await inicializar_juego(context.bot, update.effective_chat)
        else:
            await context.bot.send_message(chat_id, "Solo un administrador puede iniciar el juego")


def elegir_palabra() -> str:
    data = open("./words.txt", 'r')
    cantpal = int(data.readline()) # la primera linea te dice la cantidad de palabras
    nlinea = randint(0, cantpal-1)

    palabra = islice(data, nlinea, nlinea + 1).__next__()[:-1]
    
    return palabra

async def inicializar_juego(bot: Bot, chat: Chat):
    juego = grupos[chat.id]

    juego['impostor'] = choice(juego['players'])
    juego['vivos'].copy(juego['players'])

    juego['palabra'] = elegir_palabra()
    await susurrar_palabras(chat.id, bot, juego['palabra'])

    await bot.send_message(chat, "Que empiece el juego. Cada uno puede decir su palabra")

    jugadas.clear()



async def susurrar_palabras(chat_id, bot: Bot, palabra):
    for player in grupos[chat_id]['players']:
        if not player == grupos[chat_id]['impostor']:
            await bot.send_message(player, "La palabra es " + palabra)
        else:
            await bot.send_message(player, "Te jodiste asere, eres el impostor")

async def jugar_palabra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not grupos[update.effective_chat.id]['game_running']:
        await update.message.reply_text("Comando inválido, no se ha iniciado un juego.")
        return

    await update.effective_message.delete()
    user = update.effective_user
    chat_id = update.effective_chat.id

    if user.id in grupos[chat_id]['vivos']: # Si el usuario es uno de los jugadores activos
        if len(context.args) > 1:
            await update.message.reply_text("Solo puedes jugar una palabra")
        elif not user.id in grupos[chat_id]['jugadas']: # si el usuario que envió el mensaje no ha jugado todavía
            palabra = context.args[0]
            grupos[chat_id]['jugadas'][user.id] = palabra
            await context.bot.send_message(chat_id, f"{user.mention_html()} dijo: '{palabra}'", parse_mode=ParseMode.HTML)

            await revisar_fin_ronda(context, update.effective_chat)
        else:
            await update.message.reply_text("Ya jugaste una palabra en esta ronda")
    elif user.id in grupos[chat_id]['players']:
        await update.message.reply_text("Fuiste eliminado, ya no puedes jugar")
    else:
        await update.message.reply_text("¡No estás jugando!")



async def revisar_fin_ronda(context: ContextTypes.DEFAULT_TYPE, chat: Chat):
    if len(grupos[chat.id]['vivos']) == len(grupos[chat.id]['jugadas'].keys()):
        await enviar_votacion(context, chat)
        jugadas.clear()

async def enviar_votacion(context: ContextTypes.DEFAULT_TYPE, chat: Chat):
    miembros = [await chat.get_member(id) for id in grupos[chat.id]['vivos']]
    
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
    if not grupos[update.effective_chat.id]['game_running']:
        return

    resultados = update.poll_answer
    # votos = {id: 0 for id in grupos[update.effective_chat.id]['vivos']}

    # votacion = context.bot_data[resultados.poll_id]
    # try:

    lista_votos = resultados.option_ids

    #TODO: Probar si esto sirve
    votos = {id: lista_votos.count(id) for id in grupos[update.effective_chat.id]['vivos']}

    # for voto in lista_votos:
    #     votos[voto] += 1
    
    # Sacar el jugador más votado
    mas_votado = 0, 0
    for player in votos:
        if votos[player] > mas_votado[1]:
            mas_votado = player, votos[player]
    
    # Si acumula al menos la mitad de los votos, expulsarlo
    if mas_votado[1] > len(votos) / 2:
        chat = update.effective_chat
        grupos[chat.id]['vivos'].remove(mas_votado[0])
        await context.bot.send_message(
            chat, f"El jugador {await chat.get_member(mas_votado[0]).mention_html()} ha sido expulsado del juego",
            parse_mode=ParseMode.HTML
        )

if __name__ == '__main__':
    main()