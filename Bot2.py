import random

from telegram import Update, Bot, ChatMember, Poll
from telegram.ext import(
    Application,
    ContextTypes,
    CommandHandler,
    PollHandler,
    PollAnswerHandler,
    ChatMemberHandler
)

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
    bot.add_handler(CommandHandler("start", start_game))
    bot.add_handler(CommandHandler("p", jugar_palabra))
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
            await context.bot.send_message(chat_id, ''.join(["El jugador ", user.full_name, " se ha quitado del juego"]))

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    adm = await context.bot.get_chat_member(chat_id, user.id)
    
    if adm.status == ChatMember.ADMINISTRATOR:
        game_running = True
        await inicializar_juego(context.bot)
    else:
        await context.bot.send_message(chat_id, "Solo un administrador puede iniciar el juego")


def elegir_palabra() -> str:
    pass

async def inicializar_juego(bot: Bot):
    impostor = random.choice(players)
    vivos.copy(players)

    await susurrar_palabras(bot, elegir_palabra())

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
        await context.bot.send_message(chat_id, user.full_name + " dijo: '" + palabra + "'")
    else:
        await context.bot.send_message(chat_id, user.full_name + ", ya jugaste una palabra en esta ronda")

async def enviar_encuesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    votacion = await context.bot.send_poll(
        update.effective_chat.id,
        "¿Quién crees que es el impostor?",
        [await update.effective_chat.get_member(id) for id in vivos],
        type=Poll.REGULAR,
        open_period=60
    )
