from ConfigParser import SafeConfigParser

from mongo_steem import MongoSteem
from piston.steem import Steem

def run():
    parser = SafeConfigParser()
    parser.read('config.ini')

    nodes = parser.get('steem', 'nodes')
    wif = parser.get('steem', 'wif')

    steem = Steem(node=nodes, wif=wif)

    host_name = parser.get('mongodb', 'host_name')
    db_name = parser.get('mongodb', 'db_name')

    mongo_steem = MongoSteem(steem, host_name=host_name, db_name=db_name)
    mongo_steem.stream_to_mongo()

if __name__ == '__main__':
    run()
