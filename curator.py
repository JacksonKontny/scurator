from ConfigParser import SafeConfigParser

from mongo_steem import SteemVoter
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

    category = parser.get('miner', 'category')
    expiration_minutes = parser.get('miner', 'expiration_minutes')
    sleep_time = parser.get('miner', 'sleep_time')

    post_miner = PostMiner(
        mongo_steem,
        category=category,
        expiration_minutes=expiration_minutes,
        sleep_time=sleep_time)

    voter = parser.get('voter', 'voter')
    steem_voter = SteemVoter(steem=steem, voter=voter)

    vote_limit = parser.get('curator', 'vote_limit')
    run_hours = parser.get('curator', 'run_hours')

    curator = SteemCurator(
        steem=steem,
        post_minter=post_miner,
        steem_voter=steem_voter,
        vote_limit=vote_limit,
        run_hours=run_hours,
    )

    curator.run()

if __name__ == '__main__':
    run()




def run():


if __name__ == '__main__':
    run()
