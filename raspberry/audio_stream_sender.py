import socket
import pyaudio
import threading
from queue import Queue

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100  
DEVICE_INDEX = 2  

TCP_IP = "192.168.137.1"  
TCP_PORT = 5005

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=DEVICE_INDEX, 
                frames_per_buffer=CHUNK)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((TCP_IP, TCP_PORT))

messages = Queue()

def record_and_send():
    while not messages.empty():
        try:
            data = stream.read(CHUNK)
            sock.sendall(data)
        except OSError as e:
            print(f"Error while reading stream: {e}")
            break

    stream.stop_stream()
    stream.close()
    p.terminate()
    sock.close()

def start_recording():
    messages.put(True)
    threading.Thread(target=record_and_send).start()

start_recording()
