import sys
import math
import serial
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QSplitter, QTextEdit, QPushButton, QLineEdit,
    QComboBox, QFormLayout, QGroupBox, QLabel, QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from ansi2html import Ansi2HTMLConverter
from loratrack_hat import Node
from weather import Weather
from logger import CSVLogger
import time


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

        self.ax.grid(color="#444444")
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
        self.node_status.setFontPointSize(14)
        self.node_status.setFont(font)

        # --- Controls (Start Logging + Inputs) ---
        self.control_panel = QGroupBox("Controls")
        control_layout = QVBoxLayout()

        # --- Row 1: Start/Stop Logging ---
        log_buttons_layout = QHBoxLayout()
        self.log_button = QPushButton("Start Logging")
        self.log_button.clicked.connect(self.start_logging)
        self.log_button_stop = QPushButton("Stop Logging")
        self.log_button_stop.clicked.connect(self.stop_logging)
        log_buttons_layout.addWidget(self.log_button)
        log_buttons_layout.addWidget(self.log_button_stop)
        control_layout.addLayout(log_buttons_layout)

        # --- Row 2: Latitude, Longitude Inputs + Confirm ---
        lat_lon_layout = QHBoxLayout()
        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("Latitude")
        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("Longitude")
        self.latlon_confirm = QPushButton("Confirm Location")
        self.latlon_confirm.clicked.connect(self.confirm_location)  # You should define this method
        lat_lon_layout.addWidget(QLabel("End Node Lat:"))
        lat_lon_layout.addWidget(self.lat_input)
        lat_lon_layout.addWidget(QLabel("Lon:"))
        lat_lon_layout.addWidget(self.lon_input)
        lat_lon_layout.addWidget(self.latlon_confirm)
        control_layout.addLayout(lat_lon_layout)

        # --- Row 3: LoRa Config + Confirm ---
        lora_layout = QHBoxLayout()
        self.bw_dropdown = QComboBox()
        self.bw_dropdown.addItems(["500", "250", "125"])
        self.sf_dropdown = QComboBox()
        self.sf_dropdown.addItems([str(sf) for sf in range(6, 11)])
        self.update_lora = QPushButton("Update LoRa Config")
        self.update_lora.clicked.connect(self.update_lora_cfg)
        lora_layout.addWidget(QLabel("Bandwidth (kHz):"))
        lora_layout.addWidget(self.bw_dropdown)
        lora_layout.addWidget(QLabel("Spreading Factor:"))
        lora_layout.addWidget(self.sf_dropdown)
        lora_layout.addWidget(self.update_lora)
        control_layout.addLayout(lora_layout)

        self.control_panel.setLayout(control_layout)

        # --- Left Side Splitter ---
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self.canvas)

        # --- Container widget to stack controls and node status ---
        bottom_left_container = QWidget()
        bottom_left_layout = QVBoxLayout(bottom_left_container)
        bottom_left_layout.setContentsMargins(0, 0, 0, 0)
        bottom_left_layout.addWidget(self.control_panel)
        bottom_left_layout.addWidget(self.node_status)

        left_splitter.addWidget(bottom_left_container)
        left_splitter.setSizes([1200, 1200])

        # --- Main splitter: (plot+controls+status) | (log) ---
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self.text_log)
        main_splitter.setSizes([1200, 1200])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central)

        # Data storage
        self.weather = Weather()
        self.gw0 = Node("GW0")
        self.an0 = Node("AN0")
        self.an0.nav = (-27, 153)
        self.an1 = Node("AN1")
        self.an0.nav = (-28, 152)
        self.en0 = Node("EN0")
        self.nodes = [self.gw0, self.an0, self.an1, self.en0]
        self.update_node_status()
        self.logger = None;

        # ANSI converter
        self.ansi_conv = Ansi2HTMLConverter(inline=True)

        # Serial reader
        self.serial_reader = SerialReader()
        self.serial_reader.data_received.connect(self.handle_serial_data)
        self.serial_reader.cmd_received.connect(self.handle_cmd)

    def confirm_location(self):
        lat = float(self.lat_input.text())
        lon = float(self.lon_input.text())
        self.en0.nav = (lat, lon, 0)
        self.update_node_status()

    def update_lora_cfg(self):
        bw = self.bw_dropdown.currentText()
        sf = self.sf_dropdown.currentText()
        self.text_log.append(f"setting bandwidth={bw}KHz and sf={sf}")


    def stop_logging(self):
        if (self.logger is not None): 
            self.logger.close()
            self.logger = None
            self.text_log.append(f"<b>Logging stopped</b>")
        else:
            self.text_log.append("<b style='color:orange'>WARNING: No current logging</b>")

    def start_logging(self):
        if self.logger is None:
            self.text_log.append(f"<b>Logging Started</b>")
            self.logger = CSVLogger(
                f"data/dataset_{round(time.time())}_{self.bw_dropdown.currentText()}_{self.sf_dropdown.currentText()}.csv", 
                headers=["packet_id","node_id","toa","rssi","snr","temp","humi"]
            )
        else:
            self.text_log.append("<b style='color:orange'>WARNING: Already Logging</b>")

    def handle_serial_data(self, line):
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
            self.weather.add_sample(int(cmd_list[1]), int(cmd_list[2]))
        elif cmd_list[0][3:] == "LORA":
            if cmd_list[0][:3] == "GW0":
                self.gw0.add_info(cmd_list)
            elif cmd_list[0][:3] == "AN0":
                self.an0.add_info(cmd_list)
            elif cmd_list[0][:3] == "AN1":
                self.an1.add_info(cmd_list)
            else:
                print("invalid node id")
                
        elif cmd_list[0][3:] == "POS":
            if cmd_list[0][:3] == "GW0":
                self.gw0.set_nav(float(cmd_list[1]), float(cmd_list[2]), float(cmd_list[3]))
            elif cmd_list[0][:3] == "AN0":
                self.an0.set_nav(float(cmd_list[1]), float(cmd_list[2]), float(cmd_list[3]))
            elif cmd_list[0][:3] == "AN1":
                self.an1.set_nav(float(cmd_list[1]), float(cmd_list[2]), float(cmd_list[3]))
            else:
                print("invalid node id")
            print(cmd_list)

        elif cmd_list[0][3:] == "TIME":
            print(cmd_list)
        else:
            print("ERROR:", cmd_list)

        self.update_node_status()

    def update_node_status(self):
        self.node_status.clear()
        self.node_status.append(f"{self.weather.temp_avg} C | {self.weather.humi_avg}%")
        x_list = []
        y_list = []
        for node in self.nodes:
            distance, angle = node.distance_from(self.gw0)
            angle = math.radians(angle)
            x = round(distance * math.cos(angle), 1)
            y = round(distance * math.sin(angle), 1)
            x_list.append(x)
            y_list.append(y)
            self.node_status.append(f"{node.id} | Position: ({x}, {y})") 
            self.node_status.append(f"\tRecv: t={node.timestamp}")
        self.update_plot(x_list, y_list)

    def update_plot(self, x, y):
        self.canvas.ax.clear()

        # Reapply dark styling
        self.canvas.ax.set_facecolor("#121212")
        self.canvas.figure.patch.set_facecolor("#121212")
        self.canvas.ax.grid(color="#444444")
        self.canvas.ax.tick_params(colors="#e0e0e0")
        self.canvas.ax.xaxis.label.set_color("#e0e0e0")
        self.canvas.ax.yaxis.label.set_color("#e0e0e0")
        self.canvas.ax.title.set_color("#e0e0e0")

        self.canvas.ax.plot(x, y, marker="o", linestyle="")
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
        QTextEdit, QLabel, QLineEdit, QComboBox, QPushButton {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #333333;
        }
        QPushButton {
            padding: 4px;
        }
    """
    app.setStyleSheet(dark_stylesheet)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
