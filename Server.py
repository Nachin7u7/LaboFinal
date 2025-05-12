from flask import Flask, request, jsonify, Response
from flask_socketio import SocketIO, emit
from datetime import datetime
import math
import matplotlib
matplotlib.use('Agg')  # Configurar backend no interactivo para evitar errores en el servidor
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
socketio = SocketIO(app)

beacon_data = []
node_data = {}

beacon_pos = {
    "beacon_01": (0, 0),
    "beacon_02": (2, 0),
    "beacon_03": (1, 2)  # opcional
}

def rssi_to_distance(rssi, tx_power=-50, n=2.5):
    return 10 ** ((tx_power - rssi) / (10 * n))

def calcular_posicion_estimada(id_movil):
    lecturas = [d for d in beacon_data if d['id_movil'] == id_movil and d['id_beacon'] in beacon_pos]
    if len(lecturas) < 2:
        return None

    puntos = []
    for lectura in lecturas:
        beacon_id = lectura['id_beacon']
        rssi = lectura['rssi']
        x, y = beacon_pos[beacon_id]
        d = rssi_to_distance(rssi)
        puntos.append((x, y, d))

    total_weight = 0
    pos_x = 0
    pos_y = 0
    for x, y, d in puntos:
        if d == 0:
            continue
        weight = 1 / d
        pos_x += x * weight
        pos_y += y * weight
        total_weight += weight

    if total_weight > 0:
        pos_x /= total_weight
        pos_y /= total_weight
        return {'x': round(pos_x, 2), 'y': round(pos_y, 2)}
    return None

@app.route('/triangulacion', methods=['GET'])
def triangulacion():
    resultado = {}

    for id_movil, info_nodo in node_data.items():
        lecturas = [d for d in beacon_data if d['id_movil'] == id_movil and d['id_beacon'] in beacon_pos]

        if len(lecturas) < 2:
            resultado[id_movil] = {'error': 'Se requieren al menos 2 beacons con datos.'}
            continue

        puntos = []
        for lectura in lecturas:
            beacon_id = lectura['id_beacon']
            rssi = lectura['rssi']
            x, y = beacon_pos[beacon_id]
            d = rssi_to_distance(rssi)
            puntos.append((x, y, d))

        # Triangulación básica (promedio ponderado inverso por distancia)
        total_weight = 0
        pos_x = 0
        pos_y = 0

        for x, y, d in puntos:
            if d == 0:
                continue
            weight = 1 / d
            pos_x += x * weight
            pos_y += y * weight
            total_weight += weight

        if total_weight > 0:
            pos_x /= total_weight
            pos_y /= total_weight
        else:
            pos_x, pos_y = None, None

        resultado[id_movil] = {
            'posicion_estimada': {'x': round(pos_x, 2), 'y': round(pos_y, 2)},
            'lecturas': puntos
        }

    return jsonify(resultado)


@app.route('/ubicacion', methods=['GET'])
def estimar_ubicacion():
    zonas = {}

    for id_movil, info_nodo in node_data.items():
        timestamp_nodo = info_nodo['timestamp']

        # Buscar todas las lecturas de ese nodo
        lecturas = [d for d in beacon_data if d['id_movil'] == id_movil]

        if not lecturas:
            zonas[id_movil] = {'zona': None, 'motivo': 'Sin datos RSSI'}
            continue

        # Seleccionar la lectura con mayor RSSI (menos negativo)
        mejor = max(lecturas, key=lambda x: x['rssi'])
        zonas[id_movil] = {
            'zona': mejor['id_beacon'],
            'rssi': mejor['rssi'],
            'timestamp_rssi': mejor['timestamp']
        }

    return jsonify(zonas)

@app.route('/correlacion', methods=['GET'])
def correlacion_rssi_temperatura():
    correlacion = []

    for id_movil, info_nodo in node_data.items():
        timestamp_nodo = info_nodo['timestamp']
        temp_nodo = info_nodo['temperatura']

        rssi_mas_cercano = None
        menor_diferencia = float('inf')

        for dato in beacon_data:
            if dato['id_movil'] == id_movil:
                diff = abs(dato['timestamp'] - timestamp_nodo)
                if diff < menor_diferencia:
                    menor_diferencia = diff
                    rssi_mas_cercano = dato

        correlacion.append({
            'id_movil': id_movil,
            'temperatura': temp_nodo,
            'timestamp_temperatura': timestamp_nodo,
            'rssi': rssi_mas_cercano['rssi'] if rssi_mas_cercano else None,
            'timestamp_rssi': rssi_mas_cercano['timestamp'] if rssi_mas_cercano else None,
            'diferencia_tiempo': menor_diferencia if rssi_mas_cercano else None
        })

    return jsonify(correlacion)

@app.route('/beacon', methods=['POST'])
def receive_beacon_data():
    data = request.json

    required_keys = {'id_beacon', 'id_movil', 'rssi', 'timestamp'}
    if not required_keys.issubset(data):
        return jsonify({'error': 'Datos incompletos'}), 400

    server_clock = max(data['timestamp'], len(beacon_data)) + 1

    for beacon in beacon_data:
        if beacon['id_beacon'] == data['id_beacon']:
            beacon.update(data)
            print(f"[BEACON UPDATED] {data}")
            return jsonify(server_clock), 200

    beacon_data.append(data)
    print(f"[BEACON ADDED] {data}")
    return jsonify(server_clock), 200

@app.route('/node', methods=['POST'])
def receive_node_data():
    data = request.json

    required_keys = {'id_movil', 'temperatura', 'timestamp'}
    if not required_keys.issubset(data):
        return jsonify({'error': 'Datos incompletos'}), 400

    server_clock = max(data['timestamp'], len(node_data)) + 1

    node_data[data['id_movil']] = {
        'temperatura': data['temperatura'],
        'timestamp': data['timestamp']
    }
    print(f"[NODE] {data}")
    return jsonify(server_clock), 200

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        'ultimos_beacons': beacon_data[-5:],
        'estado_nodos': node_data
    })

@app.route('/visualizacion', methods=['GET'])
def visualizacion():
    id_movil = request.args.get('id_movil')
    if not id_movil or id_movil not in node_data:
        return jsonify({'error': 'ID del móvil no proporcionado o no encontrado'}), 400

    # Obtener lecturas relevantes
    lecturas = [d for d in beacon_data if d['id_movil'] == id_movil and d['id_beacon'] in beacon_pos]
    if len(lecturas) < 2:
        return jsonify({'error': 'Se requieren al menos 2 beacons con datos para estimar la posición.'}), 400

    # Calcular posición estimada
    puntos = []
    beacon_cercano = max(lecturas, key=lambda x: x['rssi'])  # Beacon con mayor RSSI
    fuera_area = any(lectura['rssi'] < -65 for lectura in lecturas)  # Verificar si algún RSSI está por debajo de -65

    for lectura in lecturas:
        beacon_id = lectura['id_beacon']
        rssi = lectura['rssi']
        x, y = beacon_pos[beacon_id]
        d = rssi_to_distance(rssi)
        puntos.append((x, y, d))

    total_weight = 0
    pos_x = 0
    pos_y = 0
    for x, y, d in puntos:
        if d == 0:
            continue
        weight = 1 / d
        pos_x += x * weight
        pos_y += y * weight
        total_weight += weight

    if total_weight > 0:
        pos_x /= total_weight
        pos_y /= total_weight
    else:
        pos_x, pos_y = None, None

    # Ajustar posición si está fuera del área
    if fuera_area:
        beacon_cercano_pos = beacon_pos[beacon_cercano['id_beacon']]
        dx = pos_x - beacon_cercano_pos[0]
        dy = pos_y - beacon_cercano_pos[1]
        distance_scale = 2  # Aproximadamente 2 metros fuera del beacon más cercano
        pos_x = beacon_cercano_pos[0] + dx * distance_scale
        pos_y = beacon_cercano_pos[1] + dy * distance_scale

    # Obtener temperatura del nodo móvil
    temperatura = node_data[id_movil]['temperatura']

    # Crear gráfica
    fig, ax = plt.subplots()

    # Dibujar líneas segmentadas entre los beacons
    beacon_coords = list(beacon_pos.values())
    for i in range(len(beacon_coords)):
        x1, y1 = beacon_coords[i]
        x2, y2 = beacon_coords[(i + 1) % len(beacon_coords)]  # Conectar al siguiente beacon (circular)
        ax.plot([x1, x2], [y1, y2], linestyle='--', color='gray', label='Área de triangulación' if i == 0 else None)

    # Dibujar los beacons
    for beacon_id, (x, y) in beacon_pos.items():
        ax.scatter(x, y, label=beacon_id, color='blue')
        ax.text(x, y, beacon_id, fontsize=9, ha='right')

    # Dibujar el nodo móvil
    if pos_x is not None and pos_y is not None:
        color = 'red' if fuera_area else 'green'
        label = f'ESP32 Móvil (Temp: {temperatura}°C)'
        if fuera_area:
            label += f' - Fuera del área (Cerca de {beacon_cercano["id_beacon"]})'
        ax.scatter(pos_x, pos_y, label=label, color=color)
        ax.text(pos_x, pos_y, f'ESP32\nTemp: {temperatura}°C', fontsize=9, ha='left')

    # Ajustar límites del gráfico si está fuera del área
    if fuera_area:
        ax.set_xlim(min(0, pos_x - 2), max(2, pos_x + 2))
        ax.set_ylim(min(0, pos_y - 2), max(2, pos_y + 2))
    else:
        ax.set_xlim(-1, 3)
        ax.set_ylim(-1, 3)

    ax.set_title('Visualización de Beacons y ESP32 Móvil')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.legend()
    ax.grid()

    # Convertir gráfica a imagen en base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)

    # Crear respuesta HTML con meta-refresh
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="1"> <!-- Refrescar cada 1 segundo -->
        <title>Visualización</title>
    </head>
    <body>
        <h1>Visualización de Beacons y ESP32 Móvil</h1>
        <img src="data:image/png;base64,{img_base64}" alt="Visualización">
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

@socketio.on('connect')
def handle_connect():
    print('[CLIENT CONNECTED]')

@socketio.on('disconnect')
def handle_disconnect():
    print('[CLIENT DISCONNECTED]')

@app.route('/update_position', methods=['POST'])
def update_position():
    id_movil = request.json.get('id_movil')
    if not id_movil or id_movil not in node_data:
        return jsonify({'error': 'ID del móvil no proporcionado o no encontrado'}), 400

    posicion = calcular_posicion_estimada(id_movil)
    if posicion:
        emit('position_update', {'id_movil': id_movil, 'posicion': posicion}, broadcast=True)
        return jsonify({'success': True, 'posicion': posicion}), 200
    return jsonify({'error': 'No se pudo calcular la posición'}), 400

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
