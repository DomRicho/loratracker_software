class Node():
    def __init__(self, id):
        self.id = id
        self.rssi = 0
        self.snr = 0
        self.timestamp = 0
        self.ticks = 0
        self.pos = (0, 0)
        self.nav = (0, 0, 0)
        self.fix_status = 0
        self.poshold = 0

    def add_lora_info(self, info):
        pass

    def add_nav(self, lat, lon, alt):
        self.nav = (lat, lon, alt)
