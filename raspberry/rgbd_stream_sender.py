import pyrealsense2 as rs
import numpy as np
import socket
import struct

def main():
    # Configure the RealSense pipeline
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    pipeline.start(config)

    # TCP socket setup
    server_address = ('192.168.137.1', 8000)  # Replace <receiver_ip> with the receiver's IP address
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(server_address)

    try:
        while True:
            # Wait for a coherent pair of frames: depth and color
            frames = pipeline.wait_for_frames()
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()
            print()
            if not depth_frame or not color_frame:
                continue

            depth_image = np.asanyarray(depth_frame.get_data())
            color_image = np.asanyarray(color_frame.get_data())

            depth_bytes = depth_image.tobytes()
            depth_header = struct.pack('>I', len(depth_bytes))
            sock.sendall(depth_header)
            sock.sendall(depth_bytes)

            color_bytes = color_image.tobytes()
            color_header = struct.pack('>I', len(color_bytes))
            sock.sendall(color_header)
            sock.sendall(color_bytes)

    except ConnectionResetError:
        print("Connection was closed by the remote host.")
    finally:
        pipeline.stop()
        sock.close()

if __name__ == '__main__':
    main()
