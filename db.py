import os
from urllib.parse import urlparse
import pymysql
from pymysql.cursors import DictCursor

def get_db_connection():
    """
    Retorna uma conexão direta com o MySQL usando variáveis de ambiente.
    Suporta tanto parâmetros individuais (MYSQL_HOST, MYSQL_USER, etc.)
    quanto string única de conexão (DATABASE_URL / MYSQL_URL), padrão no Railway e Render.
    Também suporta conexões SSL seguras comuns em provedores cloud (Aiven, PlanetScale, Railway, etc.).
    """
    db_url = os.getenv('DATABASE_URL') or os.getenv('MYSQL_URL')

    if db_url:
        parsed = urlparse(db_url)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 3306
        user = parsed.username or 'root'
        password = parsed.password or ''
        database = parsed.path.lstrip('/') or 'megavarejo_erp'
    else:
        host = os.getenv('MYSQLHOST') or os.getenv('MYSQL_HOST', 'localhost')
        port = int(os.getenv('MYSQLPORT') or os.getenv('MYSQL_PORT', 3306))
        user = os.getenv('MYSQLUSER') or os.getenv('MYSQL_USER', 'root')
        password = os.getenv('MYSQLPASSWORD') or os.getenv('MYSQL_PASSWORD', '')
        database = os.getenv('MYSQL_DATABASE', 'megavarejo_erp')

    ssl_config = None
    use_ssl = os.getenv('MYSQL_SSL', 'false').lower() in ('true', '1', 't', 'yes')
    if use_ssl:
        ssl_config = {'check_hostname': False}

    connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        ssl=ssl_config,
        connect_timeout=int(os.getenv('MYSQL_CONNECT_TIMEOUT', 10)),
        cursorclass=DictCursor,
        autocommit=False
    )
    return connection
