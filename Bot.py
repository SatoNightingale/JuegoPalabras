from random import choice, randint
from itertools import islice
from enum import Enum
import logging

from telegram import (
    Update,
    Bot,
    Chat,
    User,
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

# players = [] # la lista de id's de jugadores
# impostor = -1 # El id del jugador que será el impostor
# jugadas = {} # la lista de palabras jugadas por cada jugador en la ronda actual
# vivos = [] # la lista de id's de jugadores que no han sido eliminados en la ronda
# rondas = [] # la lista de rondas, donde se guarda cada jugada de cada jugador
# game_running = False # si el juego está corriendo o no

class causas_victoria(Enum):
    IMPOSTOR_EXPULSADO = 1 # ganan jugadores
    MIN_JUGADORES = 2      # gana impostor
    IMPOSTOR_ACIERTA = 3   # gana impostor


def main():
    bot = Application.builder().token(TOKEN).build()

    bot.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, nuevo_grupo))
    bot.add_handler(CommandHandler("help", mostrar_ayuda))
    bot.add_handler(CommandHandler("regme", registerplayer))
    bot.add_handler(CommandHandler("unregme", unregisterplayer))
    bot.add_handler(CommandHandler("iniciar", start_game))
    bot.add_handler(CommandHandler("d", jugar_palabra))
    bot.add_handler(CommandHandler("jugadores", listar_jugadores))
    bot.add_handler(CommandHandler("jugadas", listar_rondas))
    bot.add_handler(PollAnswerHandler(recibir_resultados_encuesta))

    bot.run_polling(allowed_updates=Update.ALL_TYPES)

async def nuevo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.username == context.bot.username:
            # Si me acaban de añadir a este grupo, registrar su id
            grupos[update.effective_chat.id] = {
                'players': [],
                'game_running': False
            }
            context.bot_data.update(grupos)
            break

async def mostrar_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(update.effective_chat.id,
                                   """El juego de las palabras
                                    Cómo se juega:
                                        Se juega con al menos tres jugadores, de los cuales uno es el 'impostor'. El bot pone una palabra y se la dice por privado a cada jugador, menos al impostor. Luego, en cada ronda los jugadores deben enviar (con el comando /d) una palabra (y solo una) que esté relacionada con la palabra en juego, y al final de la ronda hay una votación donde los jugadores deben determinar a su juicio quién es el impostor. El jugador que reciba al menos la mitad de los votos se expulsa de la partida, si este resulta ser el impostor la partida termina y este pierde; si no es así, entonces se procede a otra ronda, a menos que queden solo dos jugadores, en cuyo caso el impostor habría ganado. El impostor también puede ganar la partida si dice la palabra en juego.
                                    """
                                   )

async def registerplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not grupos[update.effective_chat.id]['game_running']:
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

    # 'players': [],
    # 'impostor': -1,
    # 'vivos': [],
    # 'palabra': "",
    # 'jugadas': {},
    # 'rondas': [],
    # 'game_running': False

    juego['impostor'] = choice(juego['players'])
    juego['vivos'] = [].copy(juego['players'])

    juego['palabra'] = elegir_palabra()

    juego['jugadas'] = {}
    juego['rondas'] = []

    await susurrar_palabras(chat.id, bot, juego['palabra'])

    await bot.send_message(chat, "Que empiece el juego. Cada uno puede decir su palabra")

    # jugadas.clear()



async def susurrar_palabras(chat_id, bot: Bot, palabra):
    for player in grupos[chat_id]['players']:
        if not player == grupos[chat_id]['impostor']:
            await bot.send_message(player, "La palabra es " + palabra)
        else:
            await bot.send_message(player, "¡Eres el impostor!")

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

            if palabra == grupos[chat_id]['palabra']:
                await desenlace(chat_id, context.bot, causas_victoria.IMPOSTOR_ACIERTA)
            else:
                await revisar_fin_ronda(context, update.effective_chat)
        else:
            await update.message.reply_text("Ya jugaste una palabra en esta ronda")
    elif user.id in grupos[chat_id]['players']:
        await update.message.reply_text("Fuiste eliminado, ya no puedes jugar")
    else:
        await update.message.reply_text("¡No estás jugando!")



async def revisar_fin_ronda(context: ContextTypes.DEFAULT_TYPE, chat: Chat):
    if len(grupos[chat.id]['vivos']) == len(grupos[chat.id]['jugadas'].keys()):
        await context.bot.send_message(chat.id, "La ronda ha terminado. Los jugadores que quedan son:<br>" + await lista_jugadores_html(chat), parse_mode=ParseMode.HTML)

        # registrar las palabras jugadas y limpiar el diccionario para la nueva ronda
        grupos[chat.id]['rondas'].append(grupos[chat.id]['jugadas'].copy())
        grupos[chat.id]['jugadas'].clear()

        await enviar_votacion(context, chat)
        # jugadas.clear()

async def enviar_votacion(context: ContextTypes.DEFAULT_TYPE, chat: Chat):
    miembros = [await chat.get_member(id) for id in grupos[chat.id]['vivos']]
    
    votacion = await context.bot.send_poll(
        chat.id,
        "¿Quién crees que es el impostor?",
        miembros,
        type=Poll.REGULAR,
        open_period=60
    )

    # info_votacion = {
    #     votacion.poll.id: {
    #         'message_id': votacion.id,
    #         'chat_id': chat.id,
    #         'candidatos': miembros
    #     }
    # }

    # context.bot_data.update(info_votacion)

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

        if mas_votado[0] == grupos[chat.id]['impostor']:
            await desenlace(chat.id, context.bot, causas_victoria.IMPOSTOR_EXPULSADO)
        elif len(grupos[chat.id]['vivos']) < 3:
            await desenlace(chat.id, context.bot, causas_victoria.MIN_JUGADORES)


# Casos de victoria:
# El impostor dice la palabra - impostor
# El impostor es expulsado - jugadores
# Quedan dos jugadores en el juego y uno de ellos es el impostor - impostor
async def desenlace(chat_id, bot: Bot, causa: causas_victoria):
    impostor: User = bot.get_chat_member(chat_id, grupos[chat_id]['impostor'])

    match causa:
        case causas_victoria.IMPOSTOR_EXPULSADO:
            await bot.send_message(chat_id, f"¡El jugador {impostor.mention_html()} fue expulsado y era el impostor! ¡Los demás han ganado! 🥳🥳🥳", parse_mode=ParseMode.HTML)
        case causas_victoria.MIN_JUGADORES:
            await bot.send_message(chat_id, f"¡El jugador expulsado no era el impostor, sino {impostor.mention_html()}! ¡Ha ganado! 🥳🥳🥳", parse_mode=ParseMode.HTML)
        case causas_victoria.IMPOSTOR_ACIERTA:
            await bot.send_message(chat_id, f"{impostor.mention_html()} era el impostor y ha acertado la palabra '{grupos[chat_id]['palabra']}'! ¡Ha ganado! 🥳🥳🥳")
    
    # Limpiar el diccionario del grupo
    juego = grupos[chat_id]
    juego['jugadas'].clear()
    juego['rondas'].clear()
    juego['vivos'].clear()
    juego['impostor'] = -1
    juego['palabra'] = ''
    juego['game_running'] = False


async def lista_jugadores_html(chat: Chat) -> str:
    # for :
    #     nombre_player = 

    #     if player not in grupos[chat.id]['vivos']:
    #         nombre_player = ''.join(['<del>', nombre_player,'</del>'])

    return '<br>'.join([
        await chat.get_member(player).full_name if player in grupos[chat.id]['vivos']
        else '<del><i>' + await chat.get_member(player).full_name + '</i></del>'
        for player in grupos[chat.id]['players']
    ])

async def listar_jugadores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not grupos[update.effective_chat.id]['game_running']:
        update.message.reply_text("Comando inválido, no se ha iniciado un juego")
        return

    chat = update.effective_chat

    list_players = await lista_jugadores_html(chat)
    
    await context.bot.send_message(chat.id, "Los jugadores actualmente en la partida son:<br>" + list_players, parse_mode=ParseMode.HTML)
        
async def listar_rondas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    juego = grupos[chat_id]
    
    if not juego['game_running']:
        update.message.reply_text("Comando inválido, no se ha iniciado un juego")
        return

    num_ronda = 1
    mensaje = ''

    # Cada juego tiene una lista de rondas
    for ronda in juego['rondas']:
        # Cada ronda es una lista de diccionarios
        for jugada in ronda:
            # Cada diccionario mapea un id de usuario y la palabra que dijo
            lista_jugadores = 'Ronda: ' + str(num_ronda) + '<br>' + '<br>'.join([
                await context.bot.get_chat_member(chat_id, player).full_name if player in grupos[chat_id]['vivos']
                else '<del><i>' + await context.bot.get_chat_member(chat_id, player).full_name + '</i></del>'
                for player in jugada
            ])

            num_ronda += 1
            mensaje += lista_jugadores
    
    context.bot.send_message(chat_id, "Las palabras jugadas hasta ahora han sido:<br>" + mensaje, parse_mode=ParseMode.HTML)
            




if __name__ == '__main__':
    main()