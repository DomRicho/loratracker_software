from pyproj import Geod
class Node():
    def __init__(self, id):
        self.id = id
        self.nav = (0, 0, 0)
        self.geod = Geod(ellps="WGS84")

    def add_lora_info(self, info):
        pass

    def set_nav(self, lon, lat, alt):
        self.nav = (lon/1e9, lat/1e9, alt)

    def distance_from(self, node):
        fwd_az, back_az, dis = self.geod.inv(node.nav[0], node.nav[1], self.nav[0], self.nav[1])
        return (dis, fwd_az)
