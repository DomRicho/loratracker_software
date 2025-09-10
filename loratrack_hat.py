from pyproj import Geod
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
        self.geod = Geod(ellps="WGS84")

    def add_lora_info(self, info):
        pass

    def set_nav(self, lat, lon, alt):
        self.nav = (lat, lon, alt)

    def distance_from(self, node):
        fwd_az, back_az, dis = self.geod.inv(self.nav[0], self.nav[1], node.nav[0], node.nav[1])
        print(dis, fwd_az)
        return (dis, fwd_az)
