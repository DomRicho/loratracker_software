WINDOW_SIZE = 3
class Weather():
    def __init__(self):
        self.temp_samples = []
        self.temp_n = 0
        self.temp_avg = 0

        self.humi_samples = []
        self.humi_n = 0
        self.humi_avg = 0

    def add_sample(self, temp, humi):
        if (len(self.temp_samples) == WINDOW_SIZE): 
            self.temp_samples.pop(0)
        self.temp_samples.append(-45.0 + 175.0 * (temp / 65535.0))
        self.temp_avg = round(sum(self.temp_samples) / len(self.temp_samples), 1)
        if (len(self.humi_samples) == WINDOW_SIZE): 
            self.humi_samples.pop(0)
        self.humi_samples.append(100 * humi / 65535.0)
        self.humi_avg = round(sum(self.humi_samples) / len(self.humi_samples), 1)
