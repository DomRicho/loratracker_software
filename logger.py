import csv

class CSVLogger:
    def __init__(self, filename, headers=None, nav_info=None):
        """
        Initialize the CSV logger.

        :param filename: Name of the file to write to.
        :param headers: Optional list of headers to write as the first row.
        """
        self.filename = filename
        self.file = open(self.filename, mode='w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)
        
        if nav_info:
            self.writer.writerow(["gw0_x", "gw0_y", "an0_x", "an0_y", "an1_x", "an1_y", "en0_x", "en0_y"])
            self.writer.writerow(nav_info)
        if headers:
            self.writer.writerow(headers)

    def write_row(self, data):
        """
        Write a row of data to the CSV file.

        :param data: A list or tuple of values to write.
        """
        self.writer.writerow(data)

    def close(self):
        """
        Close and save the CSV file.
        """
        if not self.file.closed:
            self.file.close()
