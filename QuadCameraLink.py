import os
import shutil
import time
import paramiko
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
CAPTURE_ONE_SOURCE_FOLDER = r"C:\Users\Sally\Desktop\CaptureOneOutput"  # Folder where Capture One saves images, to trigger this program
PI_FILE_LOCATION = "/home/pi/Desktop/captured_images/"  # Raspberry Pi folder - you don't need to change this
PC_FILE_LOCATION = r"C:\Users\Sally\Desktop\FilesFromPi"  # Location where you want all the images to be combined (final output)
LIBCAMERA_CMD = "libcamera-still -t 50 --autofocus-mode auto" # This is the command that is used when the pi takes photos, here you can add resolution, brightness etc. See text file .libcamera--help - DO NOT add an -o output file location, that is appended later
PI_USERNAME = "pi" # Pre-configured, no need to change
PI_PASSWORD = "raspberry" # Pre-configured, no need to change
PI_TARGET_IP = "192.168.1.2" # Pre-configured, no need to change

# Logging function
def log(message):
    print(f"{datetime.now()}: {message}")

# Handler for file system events
class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Define the file extensions you want to monitor
        valid_extensions = (".jpg", ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".raf", ".rw2", ".orf", ".pef", ".dng", ".raw")

        # Check if the new file has one of the specified extensions
        if not event.is_directory and event.src_path.lower().endswith(valid_extensions):
            handle_new_image(event.src_path)

def handle_new_image(file_path):
    # Extract file name without extension
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    log(f"Detected new image: {file_name}")

    # Define new folder and file paths
    new_folder_path = os.path.join(PC_FILE_LOCATION, file_name)
    os.makedirs(new_folder_path, exist_ok=True)
    capture_one_file_path = os.path.join(new_folder_path, os.path.basename(file_path))

    log(f"Moving Capture One image to: {capture_one_file_path}")

    # Move and rename the file
    try:
        shutil.move(file_path, capture_one_file_path)
        log(f"Capture One image moved to: {capture_one_file_path}")
    except Exception as e:
        log(f"Error moving Capture One file: {e}")
        return

    # SSH to the Raspberry Pi and capture images
    log("Connecting to Raspberry Pi...")
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(PI_TARGET_IP, port=22, username=PI_USERNAME, password=PI_PASSWORD)

        camera_ids = {
            0: "0x02",
            1: "0x12",
            2: "0x22",
            3: "0x32"
        }

        for camera_id, i2c_value in camera_ids.items():
            i2c_command = f"sudo /usr/sbin/i2cset -y 4 0x24 0x24 {i2c_value}"
            pi_image_filename = f"{file_name}_cam{camera_id}.jpg"
            pi_image_path = os.path.join(PI_FILE_LOCATION, pi_image_filename)
            capture_command = f"{LIBCAMERA_CMD} -o {pi_image_path}"
            
            log(f"Switching to camera {camera_id}...")
            stdin, stdout, stderr = client.exec_command(i2c_command)
            stdout.channel.recv_exit_status()  # Wait for command to complete

            # Check for errors in i2cset command
            i2c_errors = stderr.read().decode()
            if i2c_errors:
                log(f"Error switching to camera {camera_id}: {i2c_errors}")
                continue

            # Add a short delay to ensure the camera switch is complete
            time.sleep(1)

            log(f"Capturing image from camera {camera_id}...")
            stdin, stdout, stderr = client.exec_command(capture_command)
            capture_output = stdout.read().decode()
            capture_errors = stderr.read().decode()

            log(f"Camera {camera_id} capture output: {capture_output}")
            if capture_errors:
                log(f"Camera {camera_id} capture errors: {capture_errors}")

        # SFTP to transfer files from Raspberry Pi to Windows PC
        log("Transferring files from Raspberry Pi to Windows PC...")
        sftp = client.open_sftp()
        try:
            for camera_id in range(4):  # Loop for 4 cameras
                remote_file = os.path.join(PI_FILE_LOCATION, f"{file_name}_cam{camera_id}.jpg")
                local_file = os.path.join(new_folder_path, f"{file_name}_cam{camera_id}.jpg")
                sftp.get(remote_file, local_file)
                log(f"Transferred file {remote_file} to {local_file}")
        except Exception as e:
            log(f"Error transferring files: {e}")
        finally:
            sftp.close()
            client.close()
            log("Disconnected from Raspberry Pi.")
    except Exception as e:
        log(f"SSH connection error: {e}")
        return

    # Restart monitoring
    log("Monitoring directory for new images...")

# Main function to start monitoring
def monitor_directory():
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, path=CAPTURE_ONE_SOURCE_FOLDER, recursive=False)
    observer.start()
    log("Monitoring directory for new images...")

    try:
        while True:
            time.sleep(1)  # Keep the script running
    except KeyboardInterrupt:
        observer.stop()
        log("Stopping directory monitoring.")

    observer.join()

# Start monitoring
monitor_directory()
