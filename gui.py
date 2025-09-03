import sys
import serial
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QSplitter, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from ansi2html import Ansi2HTMLConverter


class SerialReader(QObject):
    data_received = pyqtSignal(str)
    cmd_received = pyqtSignal(str)

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
                    if line[0] == '$':
                        self.cmd_received.emit(line)
                    else:
                        self.data_received.emit(line)
        except serial.SerialException as e:
            self.data_received.emit(f"Serial error: {e}")

    def stop(self):
        self.running = False


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure()
        self.ax = fig.add_subplot(111)

        # --- Dark mode styling ---
        self.ax.set_facecolor("#121212")
        fig.patch.set_facecolor("#121212")

        self.ax.grid(color="#444444")  # subtle grid
        self.ax.tick_params(colors="#e0e0e0")
        self.ax.xaxis.label.set_color("#e0e0e0")
        self.ax.yaxis.label.set_color("#e0e0e0")
        self.ax.title.set_color("#e0e0e0")

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
        font = QFont("monospace")

        # Logs (right side, colored)
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setAcceptRichText(True)
        self.text_log.setFont(font)

        # Node Status (bottom of plot)
        self.node_status = QTextEdit()
        self.node_status.setReadOnly(True)
        self.node_status.setFontPointSize(16)
        self.node_status.setFont(font)

        # Splitter for plot + node status
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self.canvas)
        left_splitter.addWidget(self.node_status)
        left_splitter.setSizes([400, 120])

        # Main splitter: (plot+status) | (log)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self.text_log)
        main_splitter.setSizes([1, 1])  # split evenly

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central)


        # Data storage
        self.x_data = []
        self.y_data = []
        self.temp_samples = []
        self.temp_n = 0
        self.temp_avg = 0
        self.humi_samples = []
        self.humi_n = 0
        self.humi_avg = 0
        self.nodes = [["GW0", 0, 0, 0], ["AN0", 0, 0, 0], ["AN1", 0, 0, 0]]
        self.update_node_status()

        # ANSI converter
        self.ansi_conv = Ansi2HTMLConverter(inline=True)

        # Serial reader
        self.serial_reader = SerialReader()
        self.serial_reader.data_received.connect(self.handle_serial_data)
        self.serial_reader.cmd_received.connect(self.handle_cmd)

    def handle_serial_data(self, line):
        # Convert ANSI escape codes -> HTML for log window
        html = self.ansi_conv.convert(line, full=False)
        self.text_log.append(html)

    def handle_cmd(self, line):
        cmd_list = line[1:-3].split(",")
        checksum_recv = int(line[-2:], 16)
        checksum_calc = 0
        for c in line[1:-3]:
            checksum_calc = checksum_calc ^ ord(c)
        if checksum_recv != checksum_calc:
            print("Checksum error")
            return
        if cmd_list[0][3:] == "WTHR":
            if (len(self.temp_samples) == 5): 
                self.temp_samples.pop(0)
            self.temp_samples.append(round(-45.0 + 175.0 * (int(cmd_list[1]) / 65535.0), 1))
            self.temp_avg = sum(self.temp_samples) / len(self.temp_samples)
            if (len(self.humi_samples) == 5): 
                self.humi_samples.pop(0)
            self.humi_samples.append(round(100 * (int(cmd_list[2]) / 65535.0), 1))
            self.humi_avg = sum(self.humi_samples) / len(self.humi_samples)

        self.update_node_status()


    def update_node_status(self):
        self.node_status.clear()
        self.node_status.append(f"{self.temp_avg} C | {self.humi_avg}%")
        for node in self.nodes:
            if node[3] == 0: 
                status = "No Fix"
            if node[3] == 1: 
                status = "Sampling"
            if node[3] == 2: 
                status = "Position Hold"
            self.node_status.append(f"{node[0]} | Position: ({node[1]}, {node[2]}) | Status: {status}")


    def update_plot(self):
        self.canvas.ax.clear()

        # --- Reapply dark styling after clear ---
        self.canvas.ax.set_facecolor("#121212")
        self.canvas.figure.patch.set_facecolor("#121212")
        self.canvas.ax.grid(color="#444444")
        self.canvas.ax.tick_params(colors="#e0e0e0")
        self.canvas.ax.xaxis.label.set_color("#e0e0e0")
        self.canvas.ax.yaxis.label.set_color("#e0e0e0")
        self.canvas.ax.title.set_color("#e0e0e0")

        self.canvas.ax.plot(self.x_data, self.y_data, marker="o", linestyle="-")
        self.canvas.ax.set_title("Coordinate Plot")
        self.canvas.ax.set_xlabel("X")
        self.canvas.ax.set_ylabel("Y")
        self.canvas.draw()


    def closeEvent(self, event):
        self.serial_reader.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # --- Apply dark theme stylesheet ---
    dark_stylesheet = """
        QWidget {
            background-color: #121212;
            color: #e0e0e0;
        }
        QTextEdit, QLabel {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #333333;
        }
    """
    app.setStyleSheet(dark_stylesheet)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
