
# user/password: marvell/123456

chassis = '10.5.210.72'
chassis = '172.17.0.2'
ports = [0, 1]


def pytest_addoption(parser):
    parser.addoption('--chassis', action='store', default=chassis, help='TRex server address')
    parser.addoption('--ports', action='append', default=ports, type=int, metavar='port', nargs='*',
                     help='List of TRex ports to acquire')
