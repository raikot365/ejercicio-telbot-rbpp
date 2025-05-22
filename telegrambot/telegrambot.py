from telegram import Update, InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
import logging, os, asyncio, traceback, locale
import ssl
import aiomqtt

token=os.environ["TB_TOKEN"]
autorizados=[int(x) for x in os.environ["TB_AUTORIZADOS"].split(',')]



logging.basicConfig(format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s', level=logging.INFO)

async def sin_autorizacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("intento de conexión de: " + str(update.message.from_user.id))
    await context.bot.send_message(chat_id=update.effective_chat.id, text="no autorizado")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("se conectó: " + str(update.message.from_user.id))
    if update.message.from_user.first_name:
        nombre=update.message.from_user.first_name
    else:
        nombre=""
    if update.message.from_user.last_name:
        apellido=update.message.from_user.last_name
    else:
        apellido=""

    kb = [[InlineKeyboardButton("setpoint", callback_data="setpoint")],
          [InlineKeyboardButton("periodo", callback_data="periodo")],
          [InlineKeyboardButton("destello", callback_data="destello")],
          [InlineKeyboardButton("modo", callback_data="modo")],
          [InlineKeyboardButton("rele", callback_data="rele")],]

    reply_markup = InlineKeyboardMarkup(kb)
    await update.message.reply_text("Configuración del envío de datos\n Elige una opción:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    id =  context.bot_data.get("id")
    if query.data == "setpoint":
        context.user_data["topico"] = id+"/"+"setpoint"
        context.user_data["estado"] = 1
        await query.edit_message_text(text="Elegiste la opción setpoint\nIngresa el valor entero del setpoint (0-99):")

    elif query.data == "periodo":
        context.user_data["topico"] = id+"/"+"periodo"
        await query.edit_message_text(text="Elegiste la opción periodo")
        await periodo(update, context)

    elif query.data == "destello":
        context.user_data["topico"] = id+"/"+"destello"
        await query.edit_message_text(text="Elegiste la opción destello")
        await destello(update, context)

    elif query.data == "modo":
        context.user_data["topico"] = id+"/"+"modo"
        await query.edit_message_text(text="Elegiste la opción modo")
        await modo(update, context)

    elif query.data == "rele":
        context.user_data["topico"] = id+"/"+"rele"
        await query.edit_message_text(text="Elegiste la opción rele")
        await rele(update, context)

    elif query.data == "set":
        await set_value(update, context)

    elif query.data == "reset":
        await reset_value(update, context)

    elif query.data in ["1", "3", "5", "10", "15", "30", "60", "300", "600"]:
        await publicar_periodo(update, context, int(query.data))

async def setpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe. valida y publica el valor del setpoint ingresado por el usuario."""
    client = context.bot_data.get("client")
    if context.user_data.get("estado") == 1:
        texto = update.message.text
        try:
            numero = int(texto)
            if 0 <= numero <= 99:
                context.user_data["estado"] = None
                context.user_data["setpoint_value"] = numero
                await client.publish(context.user_data["topico"], str(context.user_data["setpoint_value"]))
                await update.message.reply_text(f"Setpoint publicado, el valor es: {context.user_data['setpoint_value']}")

                return ConversationHandler.END
            else:
                await update.message.reply_text("El valor del setpoint debe estar entre 0 y 99. Intenta de nuevo.")
        except ValueError:
            await update.message.reply_text("Eso no parece un número entero. Por favor, ingresa un valor numérico entero.")
    else:
        pass

async def periodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("1", callback_data="1"), InlineKeyboardButton("3", callback_data="3"), InlineKeyboardButton("5", callback_data="5")],
        [InlineKeyboardButton("10", callback_data="10"), InlineKeyboardButton("15", callback_data="15"), InlineKeyboardButton("30", callback_data="30")],
        [InlineKeyboardButton("60", callback_data="60"), InlineKeyboardButton("300", callback_data="300"), InlineKeyboardButton("600", callback_data="600")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text="Seleccione el periodo de actualización en segundos de los datos:", reply_markup=reply_markup)


async def publicar_periodo(update: Update, context: ContextTypes.DEFAULT_TYPE, value=5):
    """Publica el valor seleccionado en el topico periodo"""
    client = context.bot_data.get("client")
    query = update.callback_query
    await query.answer()

    await client.publish(context.user_data["topico"], str(value))

    topico = context.user_data["topico"]
    await query.edit_message_text(text=f"Se publicó el periodo {value}s en el topico {topico}.")
    return ConversationHandler.END

async def destello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Publica '1' en en el topico destello"""
    client = context.bot_data.get("client")
    query = update.callback_query
    await query.answer()
    await client.publish(context.user_data["topico"], "1")
    topico = context.user_data["topico"]
    await query.edit_message_text(text=f"Se publicó la orden en el topico {topico}.")
    return ConversationHandler.END

async def modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("auto", callback_data="set"),InlineKeyboardButton("manual", callback_data="reset"),]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text="Selecciona el modo de operación del relé:", reply_markup=reply_markup)

async def rele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("on", callback_data="set"),
            InlineKeyboardButton("off", callback_data="reset"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text="Selecciona el estado de funcionamiento del relé:", reply_markup=reply_markup)


async def set_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Publica '1' en el topico correspondiente"""
    client = context.bot_data.get("client")
    query = update.callback_query
    await query.answer()
    topico = context.user_data["topico"]
    await client.publish(topico, "1")
    await query.edit_message_text(text=f"Se publicó la opción 1 en el topicio {topico}.")
    return ConversationHandler.END

async def reset_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Publica '0' en el topico correspondiente"""
    client = context.bot_data.get("client")
    query = update.callback_query
    await query.answer()
    topico = context.user_data["topico"]
    await client.publish(topico, "0")
    await query.edit_message_text(text=f"Se publicó la opción 0 en el topicio {topico}.")
    return ConversationHandler.END

async def acercade(update: Update, context):
    await context.bot.send_message(update.message.chat.id, text="Este bot fue creado para configurar el modo de operación de la raspberry")

async def kill(update: Update, context):
    logging.info(context.args)
    if context.args and context.args[0] == '@e':
        await context.bot.send_animation(update.message.chat.id, "https://user-images.githubusercontent.com/14011726/94132137-7d4fc100-fe7c-11ea-8512-69f90cb65e48.gif")
        await asyncio.sleep(6)
        await context.bot.send_message(update.message.chat.id, text="¡¡¡Ahora estan todos muertos!!!")
    else:
        await context.bot.send_message(update.message.chat.id, text="☠️ ¡¡¡Esto es muy peligroso!!! ☠️")



async def main():

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()
    
    async with aiomqtt.Client(
        os.environ["SERVIDOR"],
        port=int(os.environ["PUERTO_MQTTS"]),
        username=os.environ["MQTT_USR"],
        password=os.environ["MQTT_PASS"],
        tls_context=tls_context,
    ) as client:       

        logging.info(autorizados)
        application = Application.builder().token(token).build()
        application.add_handler(MessageHandler((~filters.User(autorizados)), sin_autorizacion))
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('acercade', acercade))
        application.add_handler(CommandHandler('kill', kill))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, setpoint))

        application.bot_data["id"] = "2C3E045A4F0D2DA0"
        application.bot_data["client"]=client
    
        async with application:
            await application.start()
            await application.updater.start_polling()
            while True:
                try:
                    await asyncio.sleep(1)
                except Exception:
                    await application.updater.stop()
                    await application.stop()
            

if __name__ == '__main__':
    asyncio.run(main())