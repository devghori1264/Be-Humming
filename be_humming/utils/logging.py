#!/usr/bin/env python3

class Log:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"

    @staticmethod
    def info(msg):
        print(f"{Log.OKBLUE}[INFO]{Log.ENDC} {msg}")

    @staticmethod
    def success(msg):
        print(f"{Log.OKGREEN}[SUCCESS]{Log.ENDC} {msg}")

    @staticmethod
    def warn(msg):
        print(f"{Log.WARNING}[WARN]{Log.ENDC} {msg}")

    @staticmethod
    def error(msg):
        print(f"{Log.FAIL}[ERROR]{Log.ENDC} {msg}")

    @staticmethod
    def header(msg):
        print(f"{Log.HEADER}[---- {msg} ----]{Log.ENDC}")