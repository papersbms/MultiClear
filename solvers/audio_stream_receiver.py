import socket
import vosk
import json
import pyaudio

model = vosk.Model(model_path="")
rec = vosk.KaldiRecognizer(model, 44100)

TCP_IP = ""
TCP_PORT = 

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((TCP_IP, TCP_PORT))
sock.listen(1)

def receive_and_recognize():
    print("Waiting connection...")
    conn, addr = sock.accept()
    print(f"connected: {addr}")

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            if rec.AcceptWaveform(data):
                result = rec.Result()
                text = json.loads(result)["text"]
                print(f"Results: {text}")
            else:
                partial = rec.PartialResult()
                print(f"Partial results: {json.loads(partial)['partial']}")
    except Exception as e:
        print(f"Error while receiving data: {e}")
    finally:
        conn.close()

try:
    receive_and_recognize()
except KeyboardInterrupt:
    print("Stop receive...")
finally:
    sock.close()
