import sys
import serial
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QSplitter, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from ansi2html import Ansi2HTMLConverter


class SerialReader(QObject):
    data_received = pyqtSignal(str)

    def __init__(self, port="/dev/ttyAMA0", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.thread = threading.Thread(target=self.read_serial, daemon=True)
        self.thread.start()

    def read_serial(self):
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=1)
            while self.running:
                line = ser.readline().decode(errors="ignore").strip()
                if line:
                    self.data_received.emit(line)
        except serial.SerialException as e:
            self.data_received.emit(f"Serial error: {e}")

    def stop(self):
        self.running = False


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure()
        self.ax = fig.add_subplot(111)
        self.ax.set_title("Coordinate Plot")
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        super().__init__(fig)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Serial Plotter & Logger")

        # Main plot
        self.canvas = MplCanvas(self)

        # Logs (right side, colored)
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setAcceptRichText(True)

        # Node Status (bottom of plot)
        self.node_status = QTextEdit()
        self.node_status.setReadOnly(True)

        # Splitter for plot + node status
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self.canvas)
        left_splitter.addWidget(self.node_status)
        left_splitter.setSizes([400, 120])

        # Main splitter: (plot+status) | (log)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self.text_log)
        main_splitter.setSizes([1, 1])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central)

        # Data storage
        self.x_data = []
        self.y_data = []
        self.node_states = {}  # dict of node_id -> status string

        # ANSI converter
        self.ansi_conv = Ansi2HTMLConverter(inline=True)

        # Serial reader
        self.serial_reader = SerialReader()
        self.serial_reader.data_received.connect(self.handle_serial_data)

    def handle_serial_data(self, line):
        # Convert ANSI escape codes -> HTML for log window
        html = self.ansi_conv.convert(line, full=False)
        self.text_log.append(html)

        # Example: parse node status messages
        # Expect lines like: "NODE1: OK", "NODE2: ERROR", etc.
        if ":" in line:
            parts = line.split(":", 1)
            node = parts[0].strip()
            status = parts[1].strip()
            if node.upper().startswith("NODE"):  # crude filter
                self.node_states[node] = status
                self.update_node_status()

        # Try to parse coordinates in the form "x,y"
        try:
            parts = line.split(",")
            if len(parts) == 2:
                x = float(parts[0].strip())
                y = float(parts[1].strip())
                self.x_data.append(x)
                self.y_data.append(y)
                self.update_plot()
        except ValueError:
            pass  # ignore malformed lines

    def update_plot(self):
        self.canvas.ax.clear()
        self.canvas.ax.plot(self.x_data, self.y_data, marker="o", linestyle="-")
        self.canvas.ax.set_title("Coordinate Plot")
        self.canvas.ax.set_xlabel("X")
        self.canvas.ax.set_ylabel("Y")
        self.canvas.draw()

    def update_node_status(self):
        # Show latest snapshot of node states
        self.node_status.clear()
        for node, status in sorted(self.node_states.items()):
            self.node_status.append(f"{node}: {status}")

    def closeEvent(self, event):
        self.serial_reader.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

