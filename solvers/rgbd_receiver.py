import socket
import struct
import numpy as np
import asyncio
from bleak import BleakClient
import torch
import torch.nn.functional as F
from torchvision.transforms.functional import normalize
from models.isnet import ISNetDIS

# Replace with your ESP32's MAC address and the correct UUID for the GATT characteristic
ESP32_MAC_ADDRESS = ""
CHARACTERISTIC_UUID = ""

# WiFi server configuration (adjust IP and port as needed)
SERVER_IP = ''
SERVER_PORT = 

# Number of frames to trigger Bluetooth sending
FRAMES_BEFORE_TRIGGER = 3

model_path = ""
input_size = [1024, 1024]

net = ISNetDIS()
if torch.cuda.is_available():
    net.load_state_dict(torch.load(model_path))
    net = net.cuda()
else:
    net.load_state_dict(torch.load(model_path, map_location="cpu"))
net.eval()

def DIS(color_image_np):
    with torch.no_grad():
        im = color_image_np
        if len(im.shape) < 3:
            im = im[:, :, np.newaxis]
        im_shp = im.shape[0:2]
        im_tensor = torch.tensor(im, dtype=torch.float32).permute(2, 0, 1)
        im_tensor = F.interpolate(torch.unsqueeze(im_tensor, 0), input_size, mode="bilinear").type(torch.uint8)
        image = torch.divide(im_tensor, 255.0)
        image = normalize(image, [0.5, 0.5, 0.5], [1.0, 1.0, 1.0])

        if torch.cuda.is_available():
            image = image.cuda()
        result = net(image)
        result = torch.squeeze(F.interpolate(result[0][0], im_shp, mode='bilinear'), 0)
        ma = torch.max(result)
        mi = torch.min(result)
        result = (result - mi) / (ma - mi)
        ii = (result * 255).permute(1, 2, 0).cpu().data.numpy().astype(np.uint8)
        result = np.squeeze(ii)
    return result

async def connect_to_esp32():
    """ Establish and maintain connection to ESP32 """
    client = BleakClient(ESP32_MAC_ADDRESS)
    try:
        await client.connect()
        if client.is_connected:
            print(f"Connected to ESP32 at {ESP32_MAC_ADDRESS}")
            return client
        else:
            raise ConnectionError("Failed to connect to ESP32.")
    except Exception as e:
        print(f"Error connecting to ESP32: {e}")
        return None


async def send_bluetooth_signal(client):
    """ Send 'g' to ESP32 via Bluetooth """
    try:
        if client.is_connected:
            await client.write_gatt_char(CHARACTERISTIC_UUID, b'g')
            print("Sent 'g' to ESP32.")
        else:
            print("Bluetooth client is not connected.")
    except Exception as e:
        print(f"Failed to send data to ESP32: {e}")


def recvall(conn, length):
    """ Helper function to receive the specified amount of data over a socket connection """
    data = b''
    while len(data) < length:
        packet = conn.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data


async def receive_rgbd_frames(client):
    """ Function to handle WiFi connection, receive RGBD data, and send 'g' via Bluetooth """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((SERVER_IP, SERVER_PORT))
        server_socket.listen(1)
        print(f"Listening for connections on {SERVER_IP}:{SERVER_PORT}...")

        conn, addr = server_socket.accept()
        print(f"Connection from {addr}")

        frame_count = 0

        try:
            while True:
                # Receive depth image size
                depth_size = struct.unpack('!I', recvall(conn, 4))[0]
                depth_image = np.frombuffer(recvall(conn, depth_size), dtype=np.uint16).reshape(480, 640)

                # Receive color image size
                color_size = struct.unpack('!I', recvall(conn, 4))[0]
                color_image = np.frombuffer(recvall(conn, color_size), dtype=np.uint8).reshape(480, 640, 3)

                # Increment frame count
                frame_count += 1
                print(f"Received frame {frame_count}")

                # After receiving 3 frames, send 'g' via Bluetooth
                if frame_count % FRAMES_BEFORE_TRIGGER == 0:
                    mask = DIS(color_image)
                    depth_image = depth_image.copy()
                    mask_coords = np.where(mask <= 253)
                    depth_image[mask_coords] = 0
                    non_zero_depth_values = depth_image[depth_image > 0]
                    if non_zero_depth_values.size > 0:
                    # if np.any(depth_image > 0):
                        print("3 frames received. Sending Bluetooth signal.")
                        min_depth_value = np.min(non_zero_depth_values)
                        if min_depth_value < 400:
                            print("Min depth: {min_depth_value}", min_depth_value)
                            await send_bluetooth_signal(client)

        except Exception as e:
            print(f"Error during receiving frames: {e}")
        finally:
            conn.close()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    esp32_client = None

    try:
        # First, establish Bluetooth connection
        esp32_client = loop.run_until_complete(connect_to_esp32())

        if esp32_client:
            # Then, start receiving frames and send 'g' when appropriate
            loop.run_until_complete(receive_rgbd_frames(esp32_client))

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Ensure the Bluetooth client is properly disconnected when done
        if esp32_client and esp32_client.is_connected:
            print("Disconnecting from ESP32...")
            loop.run_until_complete(esp32_client.disconnect())
        else:
            print("ESP32 client was not connected.")
