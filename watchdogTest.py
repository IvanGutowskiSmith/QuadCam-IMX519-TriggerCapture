from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        print(f"File created: {event.src_path}")

path = r"C:\CaptureOneOutput"  # Replace with the actual path you're monitoring
event_handler = MyHandler()
observer = Observer()
observer.schedule(event_handler, path=path, recursive=False)
observer.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
