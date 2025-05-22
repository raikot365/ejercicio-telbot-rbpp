from lib.mqtt_as import MQTTClient, config
import asyncio
import ujson
import machine
import dht

from settings import SSID, password, BROKER, PUERTO_MQTTS, MQTT_USR, MQTT_PASS
import network
import time

led_board = machine.Pin("LED", machine.Pin.OUT)

pin_rele = machine.Pin(0, machine.Pin.OUT)

config['user'] = MQTT_USR
config['password'] = MQTT_PASS
config['port'] = PUERTO_MQTTS
config['ssid'] = SSID
config['wifi_pw'] = password
config['server'] = BROKER
config['ssl'] = True

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm = 0xa11140)   # Disable power-save mode
wlan.connect(SSID, password)

max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print('waiting for connection...')
    time.sleep(1)

# Handle connection error
if wlan.status() != 3:
    raise RuntimeError('network connection failed')
else:
    print('connected')
    status = wlan.ifconfig()
    print( 'ip = ' + status[0] )

print('Datos de la red: ', wlan.ifconfig())

# se obtiene el id unico del dispositivo
id = ""
for b in machine.unique_id():
    id += "{:02X}".format(b)

print("ID del dispositivo:", id)
FILE = "datos.json"


async def save(topic, msg):
    '''Función para guardar los mensajes de los topicos subscriptos en el archivo'''
    try:
        # Intentamos leer el JSON existente
        with open(FILE, "r") as f:
            data = ujson.load(f)  # Cargar datos actuales
    except (FileNotFoundError, ValueError):  # Si no existe o está vacío
        data = {
            "rele":0,
            "setpoint":30,
            "periodo":5,
            "modo":0,
        }
        
    for key in data.keys():
        if key == topic:
            if data[key] == msg:
                return
    # Agregamos/Actualizamos el dato en el diccionario

    data[topic] = msg
    # Guardamos el JSON actualizado
    with open(FILE, "w") as f:
        ujson.dump(data, f)

async def upload(topic):
    """ Lee el último dato guardado en el archivo JSON """
    try:
        # Intentamos leer el JSON existente
        with open(FILE, "r") as f:
            data = ujson.load(f)  # Cargar datos actuales
    except (FileNotFoundError, ValueError):  # Si no existe o está vacío
        data = {
            "rele":0,
            "setpoint":30,
            "periodo":5,
            "modo":0,
        }
    value = 0
    for key in data.keys():
        if key == topic:
            value = data[key]
            break
    return value

async def blink():
    '''Función para hacer parpadear el led'''
    print("destellando")
    n = 0
    while n<3:
        led_board.toggle() 
        await asyncio.sleep(0.5) 
        n += 1
    led_board.off()

async def toggle_rele(state):
    '''Función para encender el rele'''
    if(state == str(pin_rele.value())):
        #print("No se cambia el estado del rele")
        return
    if state == "1":
        print("encendiendo rele")
        pin_rele.value(1)  # Encender el rele
    else:
        print("apagando rele")
        pin_rele.value(0)

async def messages(client):  # Respond to incoming messages
    '''Función para recibir mensajes de los topicos subscriptos'''
    modo = await upload("modo")
    async for topic, msg, retained in client.queue:
        topic = topic.decode().split("/")[-1]
        msg = msg.decode()
        print(f"Mensaje recibido: {topic} = {msg}, {type(msg)}")
        if topic == "destello":
            await blink()
        if topic == "rele" and modo == "0":
            #print("llamado a función")
            await toggle_rele(msg)
        if topic is not "destello":
            await save(topic, msg)

async def up(client):  # Respond to connectivity being (re)established
    '''Función para subscribirse a los topicos'''
    while True:
        await client.up.wait()  # Wait on an Event
        client.up.clear()
        for topico in ["setpoint", "periodo", "destello", "modo", "rele"]:
            await client.subscribe(f"{id}/{topico}", 1)

async def mediciones():
    '''Función para obtener las mediciones del sensor'''
    try:
        d = dht.DHT11(machine.Pin(15))
        d.measure()
        return d.temperature(), d.humidity()
    except OSError as e:
        print("Error de lectura del sensor DHT22:", e)
    return 0,0

async def main(client):
    await client.connect()
    for coroutine in (up, messages):
        asyncio.create_task(coroutine(client))
    n = 0
    datos = {
            "temperatura":0,
            "humedad":0,
            "setpoint":30.0,
            "periodo":5.0,
            "modo":0,
        }
    await save("periodo","5")
    # await save("setpoint","30")
    while True:
        periodo = int(await upload("periodo"))
        await asyncio.sleep(periodo)
        # Obtener mediciones del sensor
        temperatura, humedad = await mediciones()
        datos["temperatura"] = temperatura
        datos["humedad"] = humedad 
        for topic in ["setpoint", "periodo", "modo"]:
            datos[topic] = int(await upload(topic))
        
        if datos["modo"] == 1:
            if datos["temperatura"] > datos["setpoint"]:
                await toggle_rele("1")
            else:
                await toggle_rele("0")   

        json_datos = ujson.dumps(datos)
        print(f"Publicando {json_datos}")
        # If WiFi is down the following will pause for the duration.
        await client.publish(id, json_datos, qos = 1)
        n += 1


config["queue_len"] = 1  # Use event interface with default queue size
# MQTTClient.DEBUG = True  # Optional: print diagnostic messages
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    # Don't forget to close the underlying stream!
    client.close()  # Prevent LmacRxBlk:1 errors
