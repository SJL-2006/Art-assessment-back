"""让 PyMySQL 以 MySQLdb 名义工作，Django 的 MySQL 后端即可直接使用（纯 Python 免编译）。"""
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    pass
